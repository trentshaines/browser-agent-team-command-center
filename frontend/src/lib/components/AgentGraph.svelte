<script lang="ts">
  import type { AgentRun, AgentStep } from './AgentRunPanel.svelte';

  let { runs }: { runs: AgentRun[] } = $props();

  // ── Layout constants ────────────────────────────────────────────
  const NW = 160, NH = 58;   // node width / height
  const HGAP = 200;           // horizontal center-to-center
  const LANEH = 130;          // vertical center-to-center between lanes
  const PL = 20, PT = 44, PR = 56, PB = 28;

  // ── Helpers ─────────────────────────────────────────────────────
  function getDomain(url: string) {
    try { return new URL(url).hostname.replace(/^www\./, ''); }
    catch { return url.slice(0, 20); }
  }
  function getPath(url: string) {
    try { const u = new URL(url); return u.pathname + u.search; }
    catch { return ''; }
  }
  function trunc(s: string, n: number) {
    return s.length > n ? s.slice(0, n) + '…' : s;
  }

  // Deterministic domain hue — avoids red (0–30°) to not clash with error state
  function domainHue(d: string) {
    let h = 5381;
    for (let i = 0; i < d.length; i++) h = (((h << 5) + h) ^ d.charCodeAt(i)) >>> 0;
    return (h % 270) + 50; // 50–320°
  }
  // HSL color for a domain at a given lightness/alpha
  const dc = (d: string, l = 50, a = 1) => `hsla(${domainHue(d)},55%,${l}%,${a})`;

  // ── Graph data model ────────────────────────────────────────────
  interface UrlGroup { url: string; domain: string; path: string; steps: AgentStep[]; }
  interface GNode {
    id: string;
    kind: 'task' | 'url' | 'result';
    ai: number; ni: number;
    cx: number; cy: number;
    g?: UrlGroup;
    label?: string;
    status?: string;
  }
  interface GEdge {
    id: string; from: GNode; to: GNode;
    kind: 'seq' | 'shared';
    label?: string;
  }

  const graph = $derived.by(() => {
    const nodes: GNode[] = [], edges: GEdge[] = [];
    let eid = 0;

    for (let ai = 0; ai < runs.length; ai++) {
      const run = runs[ai];
      const cy = PT + ai * LANEH + NH / 2;

      // ── Task node (leftmost) ──
      const task: GNode = {
        id: `${run.id}:T`, kind: 'task',
        ai, ni: 0, cx: PL + NW / 2, cy,
        label: run.task, status: run.status,
      };
      nodes.push(task);

      // ── Group consecutive steps by URL ──
      const groups: UrlGroup[] = [];
      for (const s of run.steps) {
        if (!s.url) continue;
        const last = groups[groups.length - 1];
        if (last && last.url === s.url) last.steps.push(s);
        else groups.push({ url: s.url, domain: getDomain(s.url), path: getPath(s.url), steps: [s] });
      }

      // ── URL nodes ──
      let prev: GNode = task;
      for (let ni = 0; ni < groups.length; ni++) {
        const g = groups[ni];
        const node: GNode = {
          id: `${run.id}:U:${ni}`, kind: 'url',
          ai, ni: ni + 1, cx: PL + (ni + 1) * HGAP + NW / 2, cy, g,
        };
        nodes.push(node);
        edges.push({ id: `e${eid++}`, from: prev, to: node, kind: 'seq', label: g.steps[0]?.action_type ?? undefined });
        prev = node;
      }

      // ── Result node (rightmost) ──
      const res: GNode = {
        id: `${run.id}:R`, kind: 'result',
        ai, ni: groups.length + 1, cx: prev.cx + HGAP, cy,
        label: run.result ?? undefined, status: run.status,
      };
      nodes.push(res);
      edges.push({ id: `e${eid++}`, from: prev, to: res, kind: 'seq' });
    }

    // ── Cross-lane shared-domain arcs ──
    // For each domain visited by 2+ agents, draw a dashed arc between their first visits
    const byDomain = new Map<string, Map<number, GNode>>();
    for (const n of nodes) {
      if (n.kind !== 'url') continue;
      const d = n.g!.domain;
      if (!byDomain.has(d)) byDomain.set(d, new Map());
      const m = byDomain.get(d)!;
      if (!m.has(n.ai)) m.set(n.ai, n); // first occurrence per agent
    }
    for (const [domain, agMap] of byDomain) {
      if (agMap.size < 2) continue;
      const sorted = [...agMap.values()].sort((a, b) => a.ai - b.ai);
      for (let i = 0; i < sorted.length - 1; i++)
        edges.push({ id: `e${eid++}`, from: sorted[i], to: sorted[i + 1], kind: 'shared', label: domain });
    }

    const maxCx = nodes.reduce((m, n) => Math.max(m, n.cx), 0) + NW / 2 + PR;
    const svgW = Math.max(maxCx, 500);
    const svgH = runs.length * LANEH + PT + PB;
    return { nodes, edges, svgW, svgH };
  });

  // ── Edge path helpers ───────────────────────────────────────────
  function seqP(f: GNode, t: GNode) {
    return `M ${f.cx + NW / 2} ${f.cy} L ${t.cx - NW / 2} ${t.cy}`;
  }
  function sharedP(f: GNode, t: GNode) {
    // Cubic bezier curving left of both nodes to show cross-lane connection
    const x1 = f.cx, y1 = f.cy + NH / 2;
    const x2 = t.cx, y2 = t.cy - NH / 2;
    const ctrl = Math.min(x1, x2) - 44;
    return `M ${x1} ${y1} C ${ctrl} ${y1} ${ctrl} ${y2} ${x2} ${y2}`;
  }

  // Action type abbreviations for edge labels
  const ACT: Record<string, string> = {
    go_to_url: 'nav', navigate_to: 'nav', navigate: 'nav',
    click_element: 'click', click: 'click',
    input_text: 'type', type: 'type',
    extract_content: 'extract', scroll_down: 'scroll',
    search: 'search', submit: 'submit',
  };
  function abbrev(a?: string) {
    if (!a) return '';
    return ACT[a] ?? a.replace(/_/g, ' ').slice(0, 9);
  }

  // ── Selected node for detail panel ─────────────────────────────
  let sel = $state<GNode | null>(null);
</script>

{#if runs.length === 0}
  <div class="flex items-center justify-center h-full">
    <p class="text-sm" style="color:var(--text-faint)">Graph appears when agents run</p>
  </div>
{:else}
  <div class="relative h-full" style="overflow: auto;">
    <svg width={graph.svgW} height={graph.svgH} style="display:block; min-width:100%;">
      <defs>
        <marker id="ag-arr" markerWidth="7" markerHeight="5" refX="6.5" refY="2.5" orient="auto">
          <path d="M0,0 L7,2.5 L0,5 Z" fill="var(--border)" />
        </marker>
      </defs>

      <!-- Lane backgrounds + agent name labels -->
      {#each runs as run, ai}
        {@const ly = PT + ai * LANEH - 10}
        <rect
          x={PL / 2} y={ly}
          width={graph.svgW - PL}
          height={LANEH - 4}
          rx="10"
          fill="var(--surface)" opacity="0.65"
        />
        <text x={PL} y={ly + 16}
          font-size="10" font-family="monospace" font-weight="600"
          fill="var(--text-faint)"
        >{run.name ?? `Browser ${ai + 1}`}</text>
      {/each}

      <!-- Shared-domain arcs (behind all nodes) -->
      {#each graph.edges as e (e.id)}
        {#if e.kind === 'shared'}
          <path d={sharedP(e.from, e.to)} fill="none"
            stroke={dc(e.label!, 50, 0.45)} stroke-width="1.5" stroke-dasharray="5 3"
          />
          <!-- Domain label at midpoint of arc -->
          {@const mx = Math.min(e.from.cx, e.to.cx) - 52}
          {@const my = (e.from.cy + e.to.cy) / 2}
          <text x={mx} y={my + 4} text-anchor="middle"
            font-size="9" font-family="monospace"
            fill={dc(e.label!, 40, 0.7)}
          >{e.label}</text>
        {/if}
      {/each}

      <!-- Sequential edges -->
      {#each graph.edges as e (e.id)}
        {#if e.kind === 'seq'}
          <path d={seqP(e.from, e.to)} fill="none"
            stroke="var(--border)" stroke-width="1.5" marker-end="url(#ag-arr)"
          />
          {#if e.label}
            {@const mx = (e.from.cx + NW / 2 + e.to.cx - NW / 2) / 2}
            <text x={mx} y={e.from.cy - 7} text-anchor="middle"
              font-size="9" font-family="monospace" fill="var(--text-faint)"
            >{abbrev(e.label)}</text>
          {/if}
        {/if}
      {/each}

      <!-- Nodes -->
      {#each graph.nodes as n (n.id)}
        {@const x = n.cx - NW / 2}
        {@const y = n.cy - NH / 2}
        {@const isSel = sel?.id === n.id}

        {#if n.kind === 'task'}
          <g role="button" tabindex="0" style="cursor:pointer"
            onclick={() => sel = isSel ? null : n}
            onkeydown={(e) => e.key === 'Enter' && (sel = isSel ? null : n)}
          >
            <rect {x} {y} width={NW} height={NH} rx="8"
              fill="var(--background)"
              stroke="var(--accent)" stroke-width={isSel ? 2.5 : 1.5}
            />
            <!-- Status dot (top right) -->
            {#if n.status === 'running'}
              <circle cx={x + NW - 12} cy={y + 12} r="4" fill="#8b5cf6" opacity="0.9">
                <animate attributeName="opacity" values="0.9;0.3;0.9" dur="1.3s" repeatCount="indefinite"/>
              </circle>
            {:else if n.status === 'complete'}
              <circle cx={x + NW - 12} cy={y + 12} r="4" fill="#10b981"/>
            {:else if n.status === 'error'}
              <circle cx={x + NW - 12} cy={y + 12} r="4" fill="#dc2626"/>
            {/if}
            <text x={x + 9} y={y + 17}
              font-size="9" font-family="monospace" font-weight="700"
              fill="var(--accent)"
            >TASK</text>
            <text x={x + 9} y={y + 33}
              font-size="10" font-family="sans-serif"
              fill="var(--text-muted)"
            >{trunc(n.label ?? '', 21)}</text>
            <text x={x + 9} y={y + 49}
              font-size="9" font-family="sans-serif"
              fill="var(--text-faint)"
            >{trunc((n.label ?? '').slice(21), 23)}</text>
          </g>

        {:else if n.kind === 'url'}
          {@const g = n.g!}
          {@const hasErr = g.steps.some(s => s.success === false)}
          {@const hasOk = g.steps.some(s => s.success === true)}
          {@const hasExtract = g.steps.some(s => !!s.extracted_content)}
          {@const statusDot = hasErr && !hasOk ? '#dc2626' : hasOk ? '#10b981' : 'var(--border)'}
          <g role="button" tabindex="0" style="cursor:pointer"
            onclick={() => sel = isSel ? null : n}
            onkeydown={(e) => e.key === 'Enter' && (sel = isSel ? null : n)}
          >
            <!-- Node body with light domain tint -->
            <rect {x} {y} width={NW} height={NH} rx="8"
              fill={dc(g.domain, 96, 1)}
              stroke={isSel ? dc(g.domain, 45, 1) : dc(g.domain, 75, 0.6)}
              stroke-width={isSel ? 2.5 : 1.5}
            />
            <!-- Domain-colored left accent bar -->
            <rect x={x} y={y} width="4" height={NH} rx="2"
              fill={dc(g.domain, 50, 1)}
            />
            <!-- Success/error dot (top right) -->
            <circle cx={x + NW - 12} cy={y + 12} r="4" fill={statusDot} opacity="0.9"/>
            <!-- Extracted content dot (second from right) -->
            {#if hasExtract}
              <circle cx={x + NW - 24} cy={y + 12} r="3" fill="#10b981" opacity="0.65"/>
            {/if}
            <!-- Domain name -->
            <text x={x + 12} y={y + 18}
              font-size="11" font-family="sans-serif" font-weight="700"
              fill={dc(g.domain, 28, 1)}
            >{trunc(g.domain, 16)}</text>
            <!-- URL path -->
            <text x={x + 12} y={y + 33}
              font-size="9" font-family="monospace"
              fill="var(--text-faint)"
            >{trunc(g.path, 22)}</text>
            <!-- Step count -->
            <text x={x + 12} y={y + 49}
              font-size="9" font-family="monospace"
              fill="var(--text-faint)"
            >{g.steps.length} step{g.steps.length !== 1 ? 's' : ''}{hasExtract ? ' · extracted' : ''}</text>
          </g>

        {:else if n.kind === 'result'}
          {@const isOk = n.status === 'complete'}
          {@const isRun = n.status === 'running'}
          <g role="button" tabindex="0" style="cursor:pointer"
            onclick={() => sel = isSel ? null : n}
            onkeydown={(e) => e.key === 'Enter' && (sel = isSel ? null : n)}
          >
            <rect {x} {y} width={NW} height={NH} rx="8"
              fill={isRun ? 'var(--surface)' : isOk ? '#f0fdf4' : '#fef2f2'}
              stroke={isRun ? 'var(--border-subtle)' : isOk ? '#86efac' : '#fca5a5'}
              stroke-width={isSel ? 2.5 : 1.5}
              stroke-dasharray={isRun ? '4 2' : undefined}
            />
            <text x={x + 9} y={y + 17}
              font-size="9" font-family="monospace" font-weight="700"
              fill={isRun ? 'var(--text-faint)' : isOk ? '#15803d' : '#b91c1c'}
            >{isRun ? 'RUNNING…' : isOk ? 'RESULT' : 'ERROR'}</text>
            {#if n.label}
              <text x={x + 9} y={y + 33}
                font-size="10" font-family="sans-serif"
                fill={isOk ? '#166534' : '#991b1b'}
              >{trunc(n.label, 21)}</text>
              {#if n.label.length > 21}
                <text x={x + 9} y={y + 49}
                  font-size="10" font-family="sans-serif"
                  fill={isOk ? '#16a34a' : '#dc2626'}
                >{trunc(n.label.slice(21), 21)}</text>
              {/if}
            {:else if isRun}
              <text x={x + 9} y={y + 36}
                font-size="10" font-family="monospace"
                fill="var(--text-faint)"
              >in progress…</text>
            {:else}
              <text x={x + 9} y={y + 36}
                font-size="10" font-family="monospace"
                fill="var(--text-faint)"
              >no result</text>
            {/if}
          </g>
        {/if}
      {/each}
    </svg>

    <!-- Detail panel for selected URL node -->
    {#if sel?.kind === 'url'}
      {@const g = sel.g!}
      <div style="
        position: sticky; top: 8px; float: right; margin-right: 8px;
        width: 276px;
        background: var(--background);
        border: 1px solid var(--border);
        border-left: 3px solid {dc(g.domain, 50, 1)};
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.10);
        overflow: hidden;
        z-index: 10;
        margin-top: -100%;
      ">
        <div style="
          padding: 8px 12px;
          border-bottom: 1px solid var(--border-subtle);
          display: flex; align-items: center; gap: 8px; justify-content: space-between;
        ">
          <span style="font-size:12px; font-weight:700; color:{dc(g.domain, 30, 1)}">{g.domain}</span>
          <button onclick={() => sel = null}
            style="font-size:11px; color:var(--text-faint); background:none; border:none; cursor:pointer; padding:2px 6px; border-radius:4px; line-height:1"
          >✕</button>
        </div>
        <div style="padding: 8px 12px;">
          <p style="font-size:9px; font-family:monospace; color:var(--text-faint); word-break:break-all; margin:0 0 8px; line-height:1.5">{g.url}</p>
          <div style="display:flex; flex-direction:column; gap:5px; max-height:320px; overflow-y:auto;">
            {#each g.steps as s}
              <div style="
                border: 1px solid var(--border-subtle);
                border-radius: 7px; padding: 6px 8px;
                background: var(--surface);
              ">
                <div style="display:flex; align-items:center; gap:5px;">
                  <span style="font-size:9px; color:var(--text-faint); min-width:18px; text-align:right; font-family:monospace">{s.step}</span>
                  {#if s.action_type}
                    <span style="
                      background:var(--surface-hover);
                      border: 1px solid var(--border-subtle);
                      border-radius:4px; padding:1px 5px;
                      font-size:9px; font-family:monospace;
                      color:var(--text-muted);
                    ">{s.action_type}</span>
                  {/if}
                  {#if s.success === true}
                    <span style="margin-left:auto; font-size:10px; color:#10b981">✓</span>
                  {:else if s.success === false}
                    <span style="margin-left:auto; font-size:10px; color:#dc2626">✗</span>
                  {/if}
                </div>
                {#if s.thought}
                  <p style="font-size:10px; color:var(--text-faint); margin:4px 0 0; line-height:1.45">{s.thought}</p>
                {/if}
                {#if s.extracted_content}
                  <p style="
                    font-size:9px; font-family:monospace;
                    color:#15803d; margin:4px 0 0;
                    overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
                  ">{s.extracted_content.slice(0, 90)}</p>
                {/if}
                {#if s.error}
                  <p style="font-size:9px; font-family:monospace; color:#dc2626; margin:4px 0 0; line-height:1.4">{s.error}</p>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if}
