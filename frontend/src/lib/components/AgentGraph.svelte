<script lang="ts">
  import type { AgentRun, AgentStep } from './AgentRunPanel.svelte';

  let { runs }: { runs: AgentRun[] } = $props();

  // ── Helpers ──────────────────────────────────────────────────────
  function getDomain(url: string) {
    try { return new URL(url).hostname.replace(/^www\./, ''); }
    catch { return url.slice(0, 20); }
  }
  function getPath(url: string) {
    try {
      const u = new URL(url);
      const s = u.pathname + u.search;
      return s === '/' ? '/' : s;
    } catch { return url; }
  }
  function trunc(s: string, n: number) {
    return s.length > n ? s.slice(0, n - 1) + '…' : s;
  }
  // Deterministic domain hue (avoids red 0–40° which conflicts with error state)
  function domainHue(d: string) {
    let h = 5381;
    for (let i = 0; i < d.length; i++) h = (((h << 5) + h) ^ d.charCodeAt(i)) >>> 0;
    return (h % 260) + 55; // 55–315°
  }
  const dc = (d: string, l = 50, a = 1) => `hsla(${domainHue(d)},58%,${l}%,${a})`;

  // ── Data model ───────────────────────────────────────────────────
  interface StepRecord extends AgentStep {
    agentName: string;
    agentIdx: number;
  }

  interface PageInfo {
    url: string;
    domain: string;
    path: string;
    visits: number;
    firstSeen: number;
    steps: StepRecord[];
    liveAgents: string[];
  }

  interface DomainInfo {
    domain: string;
    totalVisits: number;
    firstSeen: number;
    pages: PageInfo[];
  }

  interface NavEdge {
    fromUrl: string;
    toUrl: string;
    fromDomain: string;
    toDomain: string;
    count: number;
    active: boolean;
  }

  interface DomainNode {
    domain: string;
    info: DomainInfo;
    cx: number; cy: number;
    radius: number;
  }

  interface PageNode {
    url: string;
    domain: string;
    info: PageInfo;
    cx: number; cy: number;
    radius: number;
  }

  // ── Layout config ────────────────────────────────────────────────
  const COL_W     = 230;   // horizontal spacing between domain columns
  const PAD_L     = 60;
  const PAD_T     = 80;
  const DOMAIN_Y  = 80;    // y-center of domain nodes
  const PAGE_GAP  = 68;    // vertical gap between page node centers
  const DOM_R_MIN = 20;
  const DOM_R_MAX = 44;
  const PG_R_MIN  = 9;
  const PG_R_MAX  = 22;

  // ── Reactive graph ────────────────────────────────────────────────
  const graph = $derived.by(() => {
    const domainMap = new Map<string, DomainInfo>();
    const pageMap   = new Map<string, PageInfo>();
    const edgeMap   = new Map<string, NavEdge>();
    let globalStep  = 0;

    for (let ai = 0; ai < runs.length; ai++) {
      const run       = runs[ai];
      const agentName = run.name ?? `Browser ${ai + 1}`;
      let prevUrl: string | null = null;

      for (const step of run.steps) {
        if (!step.url) continue;
        const url    = step.url;
        const domain = getDomain(url);
        const path   = getPath(url);
        globalStep++;

        // Domain
        if (!domainMap.has(domain)) {
          domainMap.set(domain, { domain, totalVisits: 0, firstSeen: globalStep, pages: [] });
        }
        domainMap.get(domain)!.totalVisits++;

        // Page
        if (!pageMap.has(url)) {
          const pi: PageInfo = { url, domain, path, visits: 0, firstSeen: globalStep, steps: [], liveAgents: [] };
          pageMap.set(url, pi);
          domainMap.get(domain)!.pages.push(pi);
        }
        const pg = pageMap.get(url)!;
        pg.visits++;
        pg.steps.push({ agentName, agentIdx: ai, ...step });

        // Navigation edge
        if (prevUrl && prevUrl !== url) {
          const key = `${prevUrl}→${url}`;
          if (!edgeMap.has(key)) {
            edgeMap.set(key, { fromUrl: prevUrl, toUrl: url, fromDomain: getDomain(prevUrl), toDomain: domain, count: 0, active: false });
          }
          edgeMap.get(key)!.count++;
        }
        prevUrl = url;
      }

      // Mark live: last URL of a still-running agent
      if (run.status === 'running' && run.steps.length > 0) {
        const lastStep = run.steps[run.steps.length - 1];
        if (lastStep.url) {
          const pg = pageMap.get(lastStep.url);
          if (pg && !pg.liveAgents.includes(agentName)) pg.liveAgents.push(agentName);
        }
        // Mark last edge as active
        const len = run.steps.length;
        if (len >= 2) {
          const prev2 = run.steps[len - 2];
          const last2 = run.steps[len - 1];
          if (prev2.url && last2.url && prev2.url !== last2.url) {
            const key = `${prev2.url}→${last2.url}`;
            edgeMap.get(key)!.active = true;
          }
        }
      }
    }

    // Sort domains and pages by first appearance
    const domains = [...domainMap.values()].sort((a, b) => a.firstSeen - b.firstSeen);
    for (const d of domains) d.pages.sort((a, b) => a.firstSeen - b.firstSeen);

    // Scale radii
    const maxDom  = Math.max(...domains.map(d => d.totalVisits), 1);
    const maxPage = Math.max(...[...pageMap.values()].map(p => p.visits), 1);
    const domR    = (v: number) => DOM_R_MIN + (v / maxDom)  * (DOM_R_MAX - DOM_R_MIN);
    const pgR     = (v: number) => PG_R_MIN  + (v / maxPage) * (PG_R_MAX  - PG_R_MIN);

    // Compute positions
    const domNodes:  DomainNode[]               = [];
    const pageNodes: PageNode[]                 = [];
    const pnMap     = new Map<string, PageNode>();
    let maxH = DOMAIN_Y;

    for (let di = 0; di < domains.length; di++) {
      const dom = domains[di];
      const cx  = PAD_L + di * COL_W + COL_W / 2;
      const r   = domR(dom.totalVisits);
      domNodes.push({ domain: dom.domain, info: dom, cx, cy: DOMAIN_Y, radius: r });

      let pageY = DOMAIN_Y + r + PAGE_GAP;
      for (const pg of dom.pages) {
        const pr = pgR(pg.visits);
        const pn: PageNode = { url: pg.url, domain: dom.domain, info: pg, cx, cy: pageY, radius: pr };
        pageNodes.push(pn);
        pnMap.set(pg.url, pn);
        pageY += pr * 2 + PAGE_GAP;
        maxH = Math.max(maxH, pageY);
      }
    }

    // Build edges with resolved node refs
    const edges = [...edgeMap.values()]
      .map(e => ({ ...e, from: pnMap.get(e.fromUrl), to: pnMap.get(e.toUrl) }))
      .filter((e): e is typeof e & { from: PageNode; to: PageNode } => !!e.from && !!e.to);

    const svgW = Math.max(PAD_L + domains.length * COL_W + PAD_L, 400);
    const svgH = maxH + 60;
    return { domNodes, pageNodes, edges, pnMap, svgW, svgH };
  });

  // ── Edge path (cubic bezier) ─────────────────────────────────────
  function edgePath(from: PageNode, to: PageNode, count: number): string {
    const x1 = from.cx, y1 = from.cy;
    const x2 = to.cx,   y2 = to.cy;
    if (from.domain === to.domain) {
      // Same domain: loop to the right
      const bulge = 48 + count * 8;
      return `M ${x1} ${y1} C ${x1 + bulge} ${y1} ${x2 + bulge} ${y2} ${x2} ${y2}`;
    }
    // Cross-domain: S-curve through midpoint
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mx} ${y1} ${mx} ${y2} ${x2} ${y2}`;
  }

  // ── Selection ────────────────────────────────────────────────────
  let sel = $state<PageNode | null>(null);
</script>

{#if runs.length === 0}
  <div style="display:flex; align-items:center; justify-content:center; height:100%;">
    <p style="color:var(--text-faint); font-size:14px;">Graph appears when agents run</p>
  </div>
{:else}
  <div style="display:flex; height:100%; min-height:0;">
    <!-- Scrollable graph canvas -->
    <div style="flex:1; overflow:auto; min-width:0;">
      <svg width={graph.svgW} height={graph.svgH} style="display:block;">
        <defs>
          <marker id="g-arrow" markerWidth="7" markerHeight="6" refX="6" refY="3" orient="auto">
            <path d="M0,0 L7,3 L0,6 Z" fill="var(--border)" />
          </marker>
          <marker id="g-arrow-live" markerWidth="7" markerHeight="6" refX="6" refY="3" orient="auto">
            <path d="M0,0 L7,3 L0,6 Z" fill="#8b5cf6" />
          </marker>
        </defs>

        <!-- Domain → page connector stubs -->
        {#each graph.domNodes as dom}
          {#each dom.info.pages as pg}
            {@const pn = graph.pnMap.get(pg.url)}
            {#if pn}
              <line
                x1={dom.cx} y1={dom.cy + dom.radius}
                x2={pn.cx}  y2={pn.cy - pn.radius}
                stroke="var(--border-subtle)" stroke-width="1" stroke-dasharray="3 3" opacity="0.6"
              />
            {/if}
          {/each}
        {/each}

        <!-- Navigation edges -->
        {#each graph.edges as e, i}
          {@const p = edgePath(e.from, e.to, e.count)}
          {@const w = Math.min(1 + e.count * 0.5, 3.5)}
          <!-- Edge line -->
          <path d={p} fill="none"
            stroke={e.active ? '#8b5cf6' : 'var(--border)'}
            stroke-width={e.active ? 2 : w}
            stroke-opacity={e.active ? 0.9 : 0.55}
            marker-end={e.active ? 'url(#g-arrow-live)' : 'url(#g-arrow)'}
          />
          <!-- Repeat count badge (when navigated >1×) -->
          {#if e.count > 1}
            {@const mx = (e.from.cx + e.to.cx) / 2}
            {@const my = (e.from.cy + e.to.cy) / 2}
            <circle cx={mx} cy={my} r="9" fill="var(--surface)" stroke="var(--border-subtle)" stroke-width="1"/>
            <text x={mx} y={my + 3.5} text-anchor="middle"
              font-size="8" font-family="monospace" fill="var(--text-faint)"
            >{e.count}×</text>
          {/if}
          <!-- Live traffic particle -->
          {#if e.active}
            <circle r="4.5" fill="#8b5cf6" opacity="0.9">
              <animateMotion dur="2s" repeatCount="indefinite" path={p} />
            </circle>
            <!-- second particle offset -->
            <circle r="3" fill="#a78bfa" opacity="0.6">
              <animateMotion dur="2s" begin="0.7s" repeatCount="indefinite" path={p} />
            </circle>
          {/if}
        {/each}

        <!-- Domain nodes (large circles, top row) -->
        {#each graph.domNodes as dom}
          <g>
            <circle
              cx={dom.cx} cy={dom.cy} r={dom.radius}
              fill={dc(dom.domain, 93)}
              stroke={dc(dom.domain, 48)}
              stroke-width="2"
            />
            <!-- Domain name -->
            <text x={dom.cx} y={dom.cy - (dom.radius > 28 ? 5 : 0)}
              text-anchor="middle"
              font-size="11" font-family="sans-serif" font-weight="700"
              fill={dc(dom.domain, 22)}
            >{trunc(dom.domain, 16)}</text>
            <!-- Visit total -->
            {#if dom.radius > 24}
              <text x={dom.cx} y={dom.cy + 13}
                text-anchor="middle"
                font-size="9" font-family="monospace"
                fill={dc(dom.domain, 40, 0.85)}
              >{dom.info.totalVisits} steps</text>
            {/if}
            <!-- Page count badge (bottom) -->
            <text x={dom.cx} y={dom.cy + dom.radius + 14}
              text-anchor="middle"
              font-size="9" font-family="monospace"
              fill="var(--text-faint)"
            >{dom.info.pages.length} page{dom.info.pages.length !== 1 ? 's' : ''}</text>
          </g>
        {/each}

        <!-- Page nodes -->
        {#each graph.pageNodes as pn}
          {@const isSel = sel?.url === pn.url}
          {@const isLive = pn.info.liveAgents.length > 0}
          <g role="button" tabindex="0" style="cursor:pointer"
            onclick={() => sel = isSel ? null : pn}
            onkeydown={(e) => e.key === 'Enter' && (sel = isSel ? null : pn)}
          >
            <!-- Live pulse ring -->
            {#if isLive}
              <circle cx={pn.cx} cy={pn.cy} r={pn.radius + 8}
                fill="none"
                stroke={dc(pn.domain, 55, 0.4)}
                stroke-width="2"
              >
                <animate attributeName="r"
                  values="{pn.radius + 6};{pn.radius + 14};{pn.radius + 6}"
                  dur="1.8s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.7;0.1;0.7" dur="1.8s" repeatCount="indefinite"/>
              </circle>
            {/if}

            <!-- Selection ring -->
            {#if isSel}
              <circle cx={pn.cx} cy={pn.cy} r={pn.radius + 5}
                fill="none"
                stroke={dc(pn.domain, 45, 0.7)}
                stroke-width="1.5"
                stroke-dasharray="3 2"
              />
            {/if}

            <!-- Page circle body -->
            <circle
              cx={pn.cx} cy={pn.cy} r={pn.radius}
              fill={dc(pn.domain, 90)}
              stroke={isSel ? dc(pn.domain, 38) : dc(pn.domain, 62, 0.8)}
              stroke-width={isSel ? 2.5 : 1.5}
            />

            <!-- Visit count inside node -->
            <text x={pn.cx} y={pn.cy + 3.5}
              text-anchor="middle"
              font-size="9" font-family="monospace" font-weight="700"
              fill={dc(pn.domain, 28)}
            >{pn.info.visits}</text>

            <!-- Live dot (top-left of circle) -->
            {#if isLive}
              <circle cx={pn.cx - pn.radius * 0.6} cy={pn.cy - pn.radius * 0.6} r="5" fill="#8b5cf6">
                <animate attributeName="opacity" values="1;0.25;1" dur="0.9s" repeatCount="indefinite"/>
              </circle>
            {/if}

            <!-- Path label below node -->
            <text x={pn.cx} y={pn.cy + pn.radius + 13}
              text-anchor="middle"
              font-size="9" font-family="monospace"
              fill={isSel ? dc(pn.domain, 35) : 'var(--text-faint)'}
            >{trunc(pn.info.path, 20)}</text>
          </g>
        {/each}
      </svg>
    </div>

    <!-- Detail sidebar (fixed width, doesn't scroll with graph) -->
    {#if sel}
      {@const info = sel.info}
      <div style="
        width: 272px;
        flex-shrink: 0;
        border-left: 1px solid var(--border);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        background: var(--background);
      ">
        <!-- Header -->
        <div style="
          padding: 10px 12px;
          border-bottom: 1px solid var(--border-subtle);
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 8px;
          background: var(--surface);
        ">
          <div style="min-width:0;">
            <div style="font-size:12px; font-weight:700; color:{dc(sel.domain, 28)}; margin-bottom:2px">
              {sel.domain}
            </div>
            <div style="font-size:9px; font-family:monospace; color:var(--text-faint); word-break:break-all; line-height:1.5">
              {info.path}
            </div>
          </div>
          <button onclick={() => sel = null}
            style="background:none; border:none; cursor:pointer; color:var(--text-faint); padding:2px 4px; flex-shrink:0; font-size:13px; line-height:1; border-radius:4px;"
          >✕</button>
        </div>

        <!-- Stats row -->
        <div style="
          padding: 8px 12px;
          border-bottom: 1px solid var(--border-subtle);
          display: flex;
          gap: 16px;
          align-items: center;
        ">
          <div>
            <div style="font-size:20px; font-weight:700; color:{dc(sel.domain, 28)}; line-height:1">{info.visits}</div>
            <div style="font-size:9px; color:var(--text-faint)">steps</div>
          </div>
          <div>
            <div style="font-size:20px; font-weight:700; color:{dc(sel.domain, 28)}; line-height:1">
              {info.steps.filter(s => s.success === true).length}
            </div>
            <div style="font-size:9px; color:var(--text-faint)">ok</div>
          </div>
          <div>
            <div style="font-size:20px; font-weight:700; color:#dc2626; line-height:1">
              {info.steps.filter(s => s.success === false).length}
            </div>
            <div style="font-size:9px; color:var(--text-faint)">err</div>
          </div>
          {#if info.liveAgents.length > 0}
            <div style="margin-left:auto; display:flex; align-items:center; gap:5px;">
              <span style="width:7px; height:7px; border-radius:50%; background:#8b5cf6; display:inline-block; animation: pulse 1s infinite;"></span>
              <span style="font-size:10px; color:#8b5cf6;">live</span>
            </div>
          {/if}
        </div>

        <!-- URL -->
        <div style="padding:6px 12px; border-bottom:1px solid var(--border-subtle);">
          <p style="font-size:9px; font-family:monospace; color:var(--text-faint); word-break:break-all; margin:0; line-height:1.5">{info.url}</p>
        </div>

        <!-- Steps list -->
        <div style="flex:1; overflow-y:auto; padding:8px 12px; display:flex; flex-direction:column; gap:5px;">
          {#each info.steps as s}
            <div style="
              border: 1px solid var(--border-subtle);
              border-radius: 7px;
              padding: 6px 8px;
              background: var(--surface);
            ">
              <div style="display:flex; align-items:center; gap:5px; flex-wrap:wrap;">
                <span style="font-size:9px; color:var(--text-faint); min-width:16px; text-align:right; font-family:monospace">{s.step}</span>
                <span style="font-size:9px; color:var(--text-faint); font-style:italic">{s.agentName}</span>
                {#if s.action_type}
                  <span style="
                    background: var(--surface-hover);
                    border: 1px solid var(--border-subtle);
                    border-radius: 4px;
                    padding: 1px 5px;
                    font-size: 8px;
                    font-family: monospace;
                    color: var(--text-muted);
                  ">{s.action_type}</span>
                {/if}
                {#if s.success === true}
                  <span style="margin-left:auto; color:#10b981; font-size:11px">✓</span>
                {:else if s.success === false}
                  <span style="margin-left:auto; color:#dc2626; font-size:11px">✗</span>
                {/if}
              </div>
              {#if s.thought}
                <p style="font-size:10px; color:var(--text-faint); margin:4px 0 0; line-height:1.45">{s.thought}</p>
              {/if}
              {#if s.extracted_content}
                <p style="
                  font-size: 9px; font-family: monospace; color: #15803d;
                  margin: 4px 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
                ">{s.extracted_content.slice(0, 90)}</p>
              {/if}
              {#if s.error}
                <p style="font-size:9px; font-family:monospace; color:#dc2626; margin:4px 0 0; line-height:1.4">{s.error}</p>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{/if}
