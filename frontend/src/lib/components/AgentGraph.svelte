<script lang="ts">
  import type { AgentRun } from './AgentRunPanel.svelte';

  let { runs }: { runs: AgentRun[] } = $props();

  // ── Helpers ──────────────────────────────────────────────────────
  function parseDomain(url: string): { full: string; root: string; sub: string | null } {
    try {
      const hostname = new URL(url).hostname;
      const parts = hostname.split('.');
      const root = parts.length >= 2 ? parts.slice(-2).join('.') : hostname;
      const rawSub = parts.length > 2 ? parts.slice(0, -2).join('.') : null;
      const sub = (rawSub === 'www' || rawSub === 'm') ? null : rawSub;
      return { full: hostname, root, sub };
    } catch {
      const s = url.slice(0, 30);
      return { full: s, root: s, sub: null };
    }
  }

  function domainHue(d: string) {
    let h = 5381;
    for (let i = 0; i < d.length; i++) h = (((h << 5) + h) ^ d.charCodeAt(i)) >>> 0;
    return (h % 260) + 55;
  }
  const dc = (d: string, l = 50, a = 1) => `hsla(${domainHue(d)},58%,${l}%,${a})`;
  function trunc(s: string, n: number) {
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  }

  // ── Layout config ────────────────────────────────────────────────
  const COL_W     = 220;
  const PAD_L     = 70;
  const ROOT_Y    = 90;
  const SUB_GAP   = 60;
  const ROOT_R_MIN = 24;
  const ROOT_R_MAX = 52;
  const SUB_R_MIN  = 10;
  const SUB_R_MAX  = 22;

  // ── Data model ───────────────────────────────────────────────────
  interface SubInfo {
    full: string; root: string; sub: string;
    visits: number; isLive: boolean;
  }
  interface RootInfo {
    root: string;
    totalVisits: number;
    subs: Map<string, SubInfo>;
    isLive: boolean;
  }
  interface SubNode extends SubInfo { cx: number; cy: number; radius: number; }
  interface RootNode extends RootInfo { cx: number; cy: number; radius: number; subNodes: SubNode[]; }
  interface DomainEdge { fromRoot: string; toRoot: string; count: number; active: boolean; }

  // ── Reactive graph ────────────────────────────────────────────────
  const graph = $derived.by(() => {
    const rootMap = new Map<string, RootInfo>();
    const edgeMap = new Map<string, DomainEdge>();

    for (const run of runs) {
      const isRunning = run.status === 'running';
      let prevRoot: string | null = null;

      for (let si = 0; si < run.steps.length; si++) {
        const step = run.steps[si];
        if (!step.url) continue;
        const { root, sub } = parseDomain(step.url);
        const isLastStep = isRunning && si === run.steps.length - 1;

        if (!rootMap.has(root)) rootMap.set(root, { root, totalVisits: 0, subs: new Map(), isLive: false });
        const ri = rootMap.get(root)!;
        ri.totalVisits++;
        if (isLastStep) ri.isLive = true;

        // Only track meaningful subdomains (non-www/m)
        if (sub) {
          if (!ri.subs.has(sub)) ri.subs.set(sub, { full: `${sub}.${root}`, root, sub, visits: 0, isLive: false });
          const sinfo = ri.subs.get(sub)!;
          sinfo.visits++;
          if (isLastStep) sinfo.isLive = true;
        }

        // Cross-domain edges
        if (prevRoot && prevRoot !== root) {
          const key = `${prevRoot}→${root}`;
          if (!edgeMap.has(key)) edgeMap.set(key, { fromRoot: prevRoot, toRoot: root, count: 0, active: false });
          const edge = edgeMap.get(key)!;
          edge.count++;
          if (isLastStep) edge.active = true;
        }
        prevRoot = root;
      }
    }

    const roots = [...rootMap.values()];
    if (roots.length === 0) return { rootNodes: [], edges: [], svgW: 400, svgH: 300 };

    const maxRoot = Math.max(...roots.map(r => r.totalVisits), 1);
    const allSubV = roots.flatMap(r => [...r.subs.values()].map(s => s.visits));
    const maxSub  = Math.max(...allSubV, 1);
    const rootR   = (v: number) => ROOT_R_MIN + (v / maxRoot) * (ROOT_R_MAX - ROOT_R_MIN);
    const subR    = (v: number) => SUB_R_MIN  + (v / maxSub)  * (SUB_R_MAX  - SUB_R_MIN);

    const rootNodes: RootNode[] = [];
    const rootNodeMap = new Map<string, RootNode>();
    let maxH = ROOT_Y;

    for (let i = 0; i < roots.length; i++) {
      const ri = roots[i];
      const cx = PAD_L + i * COL_W + COL_W / 2;
      const r  = rootR(ri.totalVisits);
      const subList = [...ri.subs.values()];
      const subNodes: SubNode[] = [];
      let subY = ROOT_Y + r + SUB_GAP;
      for (const si of subList) {
        const sr = subR(si.visits);
        subNodes.push({ ...si, cx, cy: subY, radius: sr });
        subY += sr * 2 + SUB_GAP;
        maxH = Math.max(maxH, subY);
      }
      const rn: RootNode = { ...ri, cx, cy: ROOT_Y, radius: r, subNodes };
      rootNodes.push(rn);
      rootNodeMap.set(ri.root, rn);
    }

    const edges = [...edgeMap.values()]
      .map(e => ({ ...e, from: rootNodeMap.get(e.fromRoot), to: rootNodeMap.get(e.toRoot) }))
      .filter((e): e is typeof e & { from: RootNode; to: RootNode } => !!e.from && !!e.to);

    const svgW = Math.max(PAD_L + roots.length * COL_W + PAD_L, 400);
    const svgH = maxH + 60;
    return { rootNodes, edges, svgW, svgH };
  });

  // Quadratic arc between root domain nodes (arcs above)
  function edgePath(from: RootNode, to: RootNode): string {
    const x1 = from.cx, y1 = from.cy;
    const x2 = to.cx,   y2 = to.cy;
    const mx = (x1 + x2) / 2;
    const my = Math.min(y1, y2) - 50;
    return `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`;
  }
</script>

{#if graph.rootNodes.length === 0}
  <div style="display:flex; align-items:center; justify-content:center; height:100%;">
    <p style="color:var(--text-faint); font-size:14px;">Network appears when agents browse</p>
  </div>
{:else}
  <div style="overflow:auto; height:100%;">
    <svg width={graph.svgW} height={graph.svgH} style="display:block;">
      <defs>
        <marker id="g-arrow" markerWidth="7" markerHeight="6" refX="6" refY="3" orient="auto">
          <path d="M0,0 L7,3 L0,6 Z" fill="var(--border)" />
        </marker>
        <marker id="g-arrow-live" markerWidth="7" markerHeight="6" refX="6" refY="3" orient="auto">
          <path d="M0,0 L7,3 L0,6 Z" fill="var(--accent)" />
        </marker>
      </defs>

      <!-- Cross-domain navigation edges (arc above domain nodes) -->
      {#each graph.edges as e}
        {@const p = edgePath(e.from, e.to)}
        {@const w = Math.min(1 + e.count * 0.4, 3.5)}
        <path d={p} fill="none"
          stroke={e.active ? 'var(--accent)' : 'var(--border)'}
          stroke-width={e.active ? 2.5 : w}
          stroke-opacity={e.active ? 0.9 : 0.5}
          marker-end={e.active ? 'url(#g-arrow-live)' : 'url(#g-arrow)'}
        />
        {#if e.count > 1}
          {@const mx = (e.from.cx + e.to.cx) / 2}
          {@const my = Math.min(e.from.cy, e.to.cy) - 50}
          <circle cx={mx} cy={my} r="10" fill="var(--surface)" stroke="var(--border-subtle)" stroke-width="1"/>
          <text x={mx} y={my + 3.5} text-anchor="middle" font-size="8" font-family="monospace" fill="var(--text-faint)">{e.count}×</text>
        {/if}
        {#if e.active}
          <circle r="4.5" fill="var(--accent)" opacity="0.9">
            <animateMotion dur="2s" repeatCount="indefinite" path={p} />
          </circle>
        {/if}
      {/each}

      <!-- Root → subdomain connector stubs -->
      {#each graph.rootNodes as rn}
        {#each rn.subNodes as sn}
          <line
            x1={rn.cx} y1={rn.cy + rn.radius}
            x2={sn.cx} y2={sn.cy - sn.radius}
            stroke="var(--border-subtle)" stroke-width="1.5" stroke-dasharray="4 3" opacity="0.5"
          />
        {/each}
      {/each}

      <!-- Root domain nodes -->
      {#each graph.rootNodes as rn}
        <g>
          {#if rn.isLive}
            <circle cx={rn.cx} cy={rn.cy} r={rn.radius + 10} fill="none"
              stroke={dc(rn.root, 55, 0.35)} stroke-width="2">
              <animate attributeName="r"
                values="{rn.radius + 8};{rn.radius + 18};{rn.radius + 8}"
                dur="2s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.6;0.08;0.6" dur="2s" repeatCount="indefinite"/>
            </circle>
          {/if}
          <circle cx={rn.cx} cy={rn.cy} r={rn.radius}
            fill={dc(rn.root, 92)}
            stroke={dc(rn.root, 45)}
            stroke-width="2.5"
          />
          <text x={rn.cx} y={rn.cy - (rn.radius > 34 ? 6 : 0)}
            text-anchor="middle" font-size="12" font-weight="700" font-family="sans-serif"
            fill={dc(rn.root, 20)}
          >{trunc(rn.root, 16)}</text>
          {#if rn.radius > 30}
            <text x={rn.cx} y={rn.cy + 14}
              text-anchor="middle" font-size="9" font-family="monospace"
              fill={dc(rn.root, 38, 0.8)}
            >{rn.totalVisits} step{rn.totalVisits !== 1 ? 's' : ''}</text>
          {/if}
          {#if rn.isLive}
            <circle cx={rn.cx + rn.radius * 0.65} cy={rn.cy - rn.radius * 0.65} r="5.5" fill="var(--accent)">
              <animate attributeName="opacity" values="1;0.2;1" dur="0.9s" repeatCount="indefinite"/>
            </circle>
          {/if}
        </g>
      {/each}

      <!-- Subdomain nodes -->
      {#each graph.rootNodes as rn}
        {#each rn.subNodes as sn}
          <g>
            {#if sn.isLive}
              <circle cx={sn.cx} cy={sn.cy} r={sn.radius + 6} fill="none"
                stroke={dc(sn.root, 55, 0.35)} stroke-width="1.5">
                <animate attributeName="r" values="{sn.radius + 5};{sn.radius + 12};{sn.radius + 5}" dur="1.8s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.6;0.08;0.6" dur="1.8s" repeatCount="indefinite"/>
              </circle>
            {/if}
            <circle cx={sn.cx} cy={sn.cy} r={sn.radius}
              fill={dc(sn.root, 88)}
              stroke={dc(sn.root, 55, 0.7)}
              stroke-width="1.5"
            />
            <text x={sn.cx} y={sn.cy + 3.5}
              text-anchor="middle" font-size="8" font-family="monospace" font-weight="700"
              fill={dc(sn.root, 28)}
            >{sn.visits}</text>
            <text x={sn.cx} y={sn.cy + sn.radius + 13}
              text-anchor="middle" font-size="9" font-family="monospace"
              fill="var(--text-faint)"
            >{trunc(sn.sub, 18)}</text>
          </g>
        {/each}
      {/each}
    </svg>
  </div>
{/if}
