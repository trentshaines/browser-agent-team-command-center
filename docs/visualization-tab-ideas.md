# Visualization Tab Feature Ideas — Browser Agent Swarm Command Center

> Researched 2026-02-28. 5 parallel agent research runs across distinct tab concepts.

---

## Tab 1: Timeline / Gantt

> Swimlane view of agent execution with real-time progress bars.

**Recommended library:** `react-calendar-timeline` (MIT, ~35KB) — `groups`/`items` API maps 1:1 to `agent_runs` schema.

### Features

#### 1. Agent Swimlane View (Core)
One horizontal swimlane per agent, labeled with truncated `session_id` and `task` text (tooltip on hover). Each bar spans `started_at` to `completed_at` (or `Date.now()` if still running).

```js
groups = agents.map(a => ({ id: a.id, title: a.session_id.slice(0,8) + '…', task: a.task }))
items  = agents.map(a => ({
  id: a.id, group: a.id,
  start_time: new Date(a.started_at),
  end_time: a.completed_at ? new Date(a.completed_at) : new Date(),
  title: a.task,
}))
```

#### 2. Live-Extending Progress Bars for Running Agents
Agents with `status === 'running'` have their bar's right edge animated in real-time via a 1-second `useEffect` tick. Pulsing shimmer CSS distinguishes running from completed bars. No additional backend data needed.

#### 3. Status-Based Color Coding with Legend
```js
const STATUS_COLORS = {
  pending:  '#6b7280',
  running:  '#3b82f6',
  complete: '#22c55e',
  error:    '#ef4444',
}
```
Applied via `react-calendar-timeline`'s `itemRenderer` prop.

#### 4. Milestone Markers for Synthesis Start
Vertical dashed line + diamond marker when synthesis begins. Derive `synthesis_started` client-side as `max(completed_at)` across all agents, or add two new SSE events: `synthesis_started` and `synthesis_complete`. Rendered as absolutely-positioned overlays using the library's `timeToPixel` utility.

#### 5. Idle Gap Annotations
Hatched/striped bands highlighting "dead time" between last agent completion and synthesis start. The single most useful debugging signal for swarm performance. Computed client-side — no new backend fields.

```js
const sortedCompletions = agents
  .filter(a => a.completed_at)
  .map(a => new Date(a.completed_at).getTime())
  .sort()
// longestGap = { start: sortedCompletions[n-2], end: sortedCompletions[n-1] }
```

#### 6. Zoom and Pan with Keyboard Shortcuts
`=`/`-` zoom, arrow keys pan, `F` to fit all agents, `T` to jump to now. Built into `react-calendar-timeline` via shift+scroll / alt+scroll. Keyboard bindings call `timelineRef.current?.updateScrollCanvas(...)`.

#### 7. Click-to-Inspect Agent Detail Panel
Click a bar → shadcn/ui `<Sheet>` slides in from right. Shows: full task text, exact timestamps, duration, result content, error message, full `text_delta` transcript. `text_delta` events must be accumulated per-agent in frontend state.

#### 8. Historical Swarm Replay with Time Scrubber
Playback controls (Play/Pause/2x) for completed runs. Scrub slider controls a `playbackTime` state; items are clipped to `min(end_time, playbackTime)`. Requires a new backend route: `GET /api/runs/{id}/events`.

#### 9. Concurrency Sparkline Header
60px-tall Recharts `<AreaChart>` pinned above the timeline showing active-agent-count over time. Computed from `started_at`/`completed_at` into time-bucketed counts. Updates live via SSE.

#### 10. Dependency / Sequencing Arrows
SVG arrows connecting dependent agents. Requires `depends_on: string[]` on agent schema. Rendered as an absolutely-positioned SVG overlay layer, recalculated on scroll/zoom.

### New Backend Requirements
| Addition | Purpose |
|----------|---------|
| `synthesis_started` / `synthesis_complete` SSE events | Milestone markers |
| Per-agent `text_delta` accumulation in frontend | Detail panel transcript |
| `GET /api/runs/{id}/events` history endpoint | Replay scrubber |
| `depends_on: string[]` on agent schema | Dependency arrows |

---

## Tab 2: Live Browser Preview

> Screenshot grid + action overlays showing what agents are doing in real-time.

**Primary hook:** `browser-use` `on_step_end` — exposes `agent.browser_session`, `agent.history.model_thoughts()`, `agent.history.model_actions()`, `agent.history.extracted_content()`.

### Features

#### 1. Screenshot Polling Tile Grid (2×2 / 3×3 / N×N)
In `on_step_end`, capture JPEG via `page.screenshot(type="jpeg", quality=60)`, base64-encode, emit as `agent_screenshot` SSE event. Frontend renders as `<img>` in CSS Grid with `repeat(auto-fill, minmax(300px, 1fr))`. Step-end polling gives ~1–3s cadence naturally.

#### 2. CDP Screencast Streaming (True Live Video ~10fps)
```python
await client.send("Page.startScreencast", {
    "format": "jpeg", "quality": 60,
    "maxWidth": 1280, "maxHeight": 720, "everyNthFrame": 3
})
# Must ack each frame: client.send("Page.screencastFrameAck", {"sessionId": ...})
```
Frontend updates `<img src="data:image/jpeg;base64,...">` via `requestAnimationFrame`. Chromium-only.

#### 3. Active URL Breadcrumb + Favicon per Tile
Read `agent.browser_session.get_browser_state_summary()` → `url`, `title`. Fetch favicon via `https://www.google.com/s2/favicons?domain={netloc}&sz=32`. Parse URL with browser `URL` API into clickable path segment chips.

#### 4. Scroll Position Heatmap Indicator
```python
scroll_data = await page.evaluate("""() => ({
    scrollY: window.scrollY,
    scrollHeight: document.body.scrollHeight,
    viewportHeight: window.innerHeight
})""")
```
Or use `scrollOffsetY` / `deviceHeight` from `Page.screencastFrame` metadata. Renders as a vertical scrubber bar beside each tile.

#### 5. Click and Action Highlight Overlay
Read `agent.history.model_actions()[-1]` for `action_name` and `element_bbox`. Emit as `agent_action` SSE event. Frontend draws CSS-animated ripple circle at proportionally-scaled coordinates over the thumbnail. Fades after 1.5s.

#### 6. Agent "Thought Bubble" Overlay
```python
thoughts = agent.history.model_thoughts()
# AgentBrain has: .thought, .evaluation_previous_goal, .next_goal
```
Rendered as a semi-transparent floating card at the tile bottom. Color-coded: green = "success", yellow = "partial", red = "failed". `text_delta` SSE enables live token streaming before `on_step_end` fires.

#### 7. DOM Extraction Preview Panel
Detect `extract_content` in recent actions, emit `history.extracted_content()[-1]` as `agent_extraction` SSE event. Slide-out panel: JSON tree view if valid JSON, HTML table if tabular (pipe-delimited), plain text otherwise. Badge counter on tile corner.

#### 8. Visited URL Timeline / Breadcrumb Trail
Append `history.urls()[-1]` + `page.title()` + `step_index` on each step. Frontend renders as horizontal scrollable row of favicon+domain chips below the tile. Clicking a chip replays the stored screenshot for that step.

#### 9. Video Recording and Step-by-Step Replay
**Option A (slideshow):** Accumulate base64 JPEGs per agent; emit full list on `agent_complete`. Frontend uses `setInterval` slideshow with scrubber slider.

**Option B (real video):** Pipe `Page.screencastFrame` JPEGs to ffmpeg subprocess over stdin → output `.webm`. Serve via static file endpoint; frontend uses `<video>` element.

#### 10. Multi-Agent Comparison Split View + Diff Overlay
Select two agent tiles → full-width split panel. Draw each thumbnail onto a `<canvas>`. Third canvas with `mix-blend-mode: difference` composites them — pixels diverge where agents are on different pages. Optional JS pixel delta similarity score. Frontend-only; no backend changes.

### Implementation Priority
| Priority | Feature | Effort |
|----------|---------|--------|
| 1 | Screenshot polling tiles | Low |
| 2 | URL breadcrumb + favicon | Low |
| 3 | Thought bubble overlay | Low (SSE exists) |
| 4 | Action overlay | Medium |
| 5 | CDP screencast | Medium-High |

---

## Tab 3: Network Graph / Task Dependency

> Task decomposition trees, URL relationship graphs, and information flow visualization.

**Recommended libraries:** React Flow (animated edges, live updates), Cytoscape.js + dagre (strict DAG layouts), D3.js d3-force (domain clustering, UMAP scatter).

### Features

#### 1. Task Decomposition Tree (Collapsible DAG)
Root = user prompt, children = orchestrator subtasks, leaves = agent runs. Cytoscape.js + `cytoscape-dagre`, top-down. Node color = status, node size = token count. Requires new `TaskNode` table:

```python
class TaskNode:
    id, session_id, parent_task_id, agent_run_id
    description, status, depth, created_at, completed_at, token_count
```

Orchestrator must emit `task_spawned` events with `parent_task_id` at decomposition time.

#### 2. Live Animated Data-Flow Graph
React Flow with `animated: true` edges. Particles travel along edges when agent results feed downstream agents or the synthesizer. Edge thickness = data volume (tokens). Throttle to ≤10 simultaneously animated edges for CPU budget. Requires new `DataFlowEvent` SSE type: `from_agent_run_id`, `to_agent_run_id`, `payload_token_count`.

#### 3. URL/Domain Relationship Graph (Force-Directed Cluster)
D3.js `d3-force` with domain hub nodes (strong centering force) and page URL satellite nodes (weak domain attraction + collision). Edges = agent ↔ URL. Hover shows page title + visiting agent. Requires new `URLVisit` table: `agent_run_id`, `url`, `domain`, `page_title`, `visited_at`, `data_extracted_chars`.

#### 4. Information Synthesis Flow (Sankey Funnel)
D3.js `d3-sankey` or React Flow left-to-right layout. Agent nodes on left → synthesizer node → output. Edge width = `contribution_score` (computed post-synthesis via token overlap or embedding similarity). Requires `SynthesisContribution` table, populated by background job after synthesis.

#### 5. Session Diff View (Two Swarm Runs Side-by-Side)
Two synchronized Cytoscape.js instances. Color coding: white = in both, blue = only in A, orange = only in B, yellow = different outcomes. Diff computed server-side via `difflib.SequenceMatcher`. New endpoint: `GET /api/sessions/{id_a}/diff/{id_b}`.

#### 6. Cross-Session Pattern Graph (Recurring Subtask Heatmap)
Force-directed graph: node size = frequency across sessions, edge weight = co-occurrence count. Background job clusters task descriptions by embedding similarity (cosine > 0.85) into `TaskPattern` records. Slider filters to patterns with N+ occurrences.

#### 7. Agent Interaction Dependency Graph (Critical Path)
Cytoscape.js dagre, left-to-right. Edge labels = wait duration. Critical path highlighted in red (thicker edge). Timeline slider replays agent activation sequence. Requires `AgentRunDependency` table + `queued_at` column on `agent_runs`.

#### 8. URL Visit Timeline + Geographic Heatmap
D3.js swimlane timeline (one lane per agent) + optional D3.js choropleth mapping domains to hosting countries via MaxMind GeoLite2 or `ip-api.com`. Both views synchronized — click domain in graph → highlight in timeline.

#### 9. Failure Propagation Graph
React Flow stepped animation: failed nodes pulse red, propagation flows outward along dependency edges. Sidebar ranks agents by "blast radius" (downstream tasks cancelled + degraded). Requires `AgentRunFailure` with `downstream_cancelled_task_ids`, `downstream_degraded_task_ids`, `blast_radius`.

#### 10. Embedding Space Projection (Task Similarity Landscape)
UMAP/t-SNE scatter plot of all task descriptions projected to 2D. D3.js `d3-zoom` scatterplot with Voronoi cell cluster boundaries (`d3-delaunay`). Lasso-select to inspect cluster. Requires `pgvector` extension + `TaskEmbedding` table with precomputed `umap_x`, `umap_y`. Background UMAP recompute nightly.

### Implementation Priority
| Priority | Feature | Complexity |
|----------|---------|-----------|
| 1 | Task Decomposition Tree | Medium |
| 2 | Agent Dependency Graph | Medium |
| 3 | URL Domain Cluster Graph | Medium |
| 4 | Live Animated Data-Flow | Medium |
| 5 | Failure Propagation Graph | Medium |
| 6 | Session Diff View | Medium |
| 7 | Synthesis Funnel | High |
| 8 | Cross-Session Patterns | High |
| 9 | URL Timeline + Geo | Medium |
| 10 | Embedding Space UMAP | High |

---

## Tab 4: Metrics & Analytics

> Performance dashboards: latency distributions, success rates, cost tracking, throughput.

**Recommended libraries:** Recharts (most charts), D3.js / ECharts (heatmaps), native PostgreSQL `percentile_cont()` aggregates.

### Features

#### 1. Agent Duration Distribution (p50/p95/p99 Latency)
Multi-line Recharts `ComposedChart` (3 lines + bar for run count). No schema changes needed.
```sql
SELECT date_trunc('hour', started_at) AS bucket,
  percentile_cont(0.50) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))) AS p50_sec,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - started_at))) AS p95_sec,
  COUNT(*) AS run_count
FROM agent_runs WHERE status = 'completed' AND started_at >= NOW() - INTERVAL '7 days'
GROUP BY bucket ORDER BY bucket;
```
Pin a horizontal `ReferenceLine` at SLA threshold.

#### 2. Success/Error Rate Over Time + Error Categorization
Stacked area chart (rates over time) + horizontal bar chart (error categories). Error bucketing via SQL CASE on `error` column patterns (timeout, navigation, selector, network). Optional: add `error_category VARCHAR(64)` to `agent_runs` to avoid runtime regex.

#### 3. Concurrent Agent Utilization Heatmap
7×24 grid (day-of-week × hour-of-day), color = peak concurrency. D3.js sequential color scale (white→deep blue) or ECharts `HeatmapChart`. Computed via `generate_series` + window join over `started_at`/`completed_at`. No schema changes.

#### 4. LLM Token Usage and Cost Per Session
Grouped horizontal bar (input vs output tokens) + cost overlay. Requires:
```sql
ALTER TABLE agent_runs ADD COLUMN input_tokens INTEGER, ADD COLUMN output_tokens INTEGER, ADD COLUMN model_id VARCHAR(64);
CREATE TABLE model_pricing (model_id VARCHAR(64) PRIMARY KEY, input_cost_per_1k NUMERIC(10,6), output_cost_per_1k NUMERIC(10,6));
```

#### 5. Throughput — Tasks/Minute with Rolling Average
Recharts `ComposedChart`: bars = raw completions per minute, line = 5-min rolling average via SQL window function `AVG(...) OVER (ROWS BETWEEN 4 PRECEDING AND CURRENT ROW)`. Updates via SSE every 10s.

#### 6. Anomaly Detection — Flagged Slow/Failing Agents
Z-score computed in pure SQL (per-task rolling mean + stddev via window functions). Flagged runs appear as `ReferenceDot` markers on the latency chart + sortable table. No new schema.

#### 7. Task Complexity Score vs Duration Scatter Plot
Recharts `ScatterChart`: X = `LENGTH(task)`, Y = `duration_sec`. Color = status. Client-side linear regression line. Pearson correlation badge. Optional: add `task_complexity_score FLOAT` for richer signals.

#### 8. Swarm Configuration Comparison View
Side-by-side grouped bar chart comparing p50/p95, success rate, avg cost, throughput between two `config_label` groups. Requires `config_label VARCHAR(128)` and `tags TEXT[]` on `sessions`.

#### 9. Session Replay Timeline (Post-Mortem)
Horizontal Gantt chart per session: one bar per agent run, X = wall-clock time relative to session start, Y = run index. Click bar → detail drawer with full task text + result + error. Requires `run_id UUID FK` on `messages` table.

### New Schema Summary
| Table | Column | Type | Purpose |
|-------|--------|------|---------|
| `agent_runs` | `input_tokens` | `INTEGER` | Cost tracking |
| `agent_runs` | `output_tokens` | `INTEGER` | Cost tracking |
| `agent_runs` | `model_id` | `VARCHAR(64)` | Pricing lookup |
| `agent_runs` | `error_category` | `VARCHAR(64)` | Pre-bucketed errors (optional) |
| `sessions` | `config_label` | `VARCHAR(128)` | A/B comparison |
| `sessions` | `tags` | `TEXT[]` | Flexible grouping |
| `messages` | `run_id` | `UUID FK` | Per-run attribution |
| NEW | `model_pricing` | table | Model cost lookup |

---

## Tab 5: Result Explorer

> Smart tables, diff views, JSON explorer, cross-agent data comparison, export.

**Key entry point:** A single `parseAgentResult(rawText: string): ParsedResult` function — tries `JSON.parse`, falls back to JSON extraction from markdown code fences, then treats as `{ text: rawText }`.

**Recommended libraries:** TanStack Table v8 (sortable table), `react-diff-viewer` (text diffs), `json-edit-react` (JSON tree), Fuse.js / MiniSearch (full-text search), Tremor (KPI cards), `react-grid-gallery` (screenshots).

### Progressive Disclosure Layers

| Layer | Features | User Need |
|-------|----------|-----------|
| Quick scan | Fact Cards, Aggregation Widgets | "What did agents find at a glance?" |
| Compare | Field Diff View, Auto-Schema Table, Pivot Unpacker | "How do agents' results differ?" |
| Explore | JSON Tree, Screenshot Gallery, Full-Text Search | "What exactly did an agent see?" |
| Track | Completion Timeline | "Which agents finished when?" |
| Export | Multi-Format Export | "Get data out for downstream use" |

### Features

#### 1. Auto-Schema Table View
Detects overlapping JSON keys across agents, renders a unified TanStack Table v8 with one row per agent. Type-aware sorters (numeric, currency, date, string). Min/max cells highlighted green/red. Export via `tanstack-table-export-to-csv`.

```
┌──────────────┬──────────┬──────────┬────────────┬───────────┐
│ Agent        │ Product  │ Price ▼  │ Rating     │ In Stock  │
├──────────────┼──────────┼──────────┼────────────┼───────────┤
│ agent-amazon │ Widget X │ $12.99   │ 4.5★       │ Yes       │
│ agent-ebay   │ Widget X │ $14.50   │ 4.2★       │ Yes       │
│ agent-walmart│ Widget X │ $11.88 ✓ │ 4.7★       │ No        │
└──────────────┴──────────┴──────────┴────────────┴───────────┘
```

#### 2. Field-Level Comparison Diff View
User selects a field (dot-notation path), sees all agents' values side-by-side. Text fields: `react-diff-viewer` word-level diffs. Numeric fields: recharts bar chart with % deviation from mean.

#### 3. Collapsible JSON Tree Explorer
`json-edit-react` per agent — supports path copying, search highlighting, optional annotation mode. Fallback to `react-json-tree` (lighter). Error boundary shows raw text if JSON parse fails.

#### 4. Multi-Format Export Panel
Download session results as CSV (papaparse), JSON array, Markdown table, or NDJSON. Toggle: flatten nested fields vs JSON-stringify cells. Native `Blob + URL.createObjectURL` — no backend needed.

#### 5. Agent Completion Timeline
Vertical MUI `Timeline` showing when each agent completed, duration bar, and one-line result summary. Reveals which sites were slow or failed and how the dataset built up over time.

```
10:42:01 ●── agent-google    ──────── 4.2s  ✓  { price: $12.99 ... }
10:42:03 ●── agent-amazon   ──────── 6.8s  ✓  { price: $14.50 ... }
10:42:07 ●── agent-walmart  ──────── 2.1s  ✗  Error: rate limited
10:42:11 ●── agent-ebay     ─── 11.4s      ✓  { price: $11.88 ... }
```

#### 6. Numeric Aggregation Widgets
For columns detected as numeric/currency: auto-compute min, max, mean, median, stddev. Tremor `Metric` + `Badge` chips pinned above the table, updated on filter changes (only visible rows).

#### 7. Screenshot Gallery with Lightbox
Detect `screenshot`, `screenshot_url`, `image`, `page_screenshot` keys in result JSON. `react-grid-gallery` thumbnail grid; click opens lightbox with split pane — screenshot left, JSON tree right.

#### 8. Fact Cards — Distilled Key Facts per Agent
Rank fields by variance across agents (high CV = most interesting). Show top 3-5 fields per agent in Tremor `Card`. Filter out fields >200 chars. Icon mapping: `price`→`$`, `rating`→`★`, `date`→calendar.

#### 9. Cross-Result Full-Text Search
Build Fuse.js index on session load — one document per JSON leaf node: `{ agentId, fieldPath, value }`. Results grouped by agent, with match highlight. Append-only re-index as new results arrive.

```
🔍 [prime          ]  3 matches across 2 agents
  agent-amazon · shipping.method: "2-day [Prime] shipping"
  agent-amazon · seller.badges[0]: "[Prime] seller"
  agent-ebay   · description: "Not eligible for [Prime] delivery"
```

#### 10. Smart Result Pivot — Array Unpacker
Detects when result contains a prominent array (e.g., `{ products: [...] }`). "Unpack" toggle treats each array item as a table row instead of each agent. Adds synthetic `_source_agent` column. Re-runs schema detection + aggregation widgets on unpacked data.

```
Pivot: [● By Agent]  [○ By Item (unpacked)]
Unpacking: result.products (12 items across 3 agents)
→ rows: Widget X Pro $19.99, Widget X Basic $9.99, Widget X (used) $7.50 ...
```

### Implementation Order
1 (table) → 4 (export) → 6 (aggregations) → 8 (fact cards) → 3 (JSON tree) → 2 (diff) → 9 (search) → 5 (timeline) → 7 (screenshots) → 10 (pivot)

---

## Cross-Cutting Library Recommendations

| Use Case | Library |
|----------|---------|
| Timeline / swimlane | `react-calendar-timeline` (MIT) |
| DAG / tree layout | `cytoscape.js` + `cytoscape-dagre` |
| Force-directed graphs | `d3-force` |
| Agent pipeline / flow | `react-flow` |
| Standard charts (line, bar, scatter) | `recharts` |
| Heatmaps | `d3.js` or `echarts` |
| Sankey diagrams | `d3-sankey` |
| UMAP/embeddings scatter | `d3-zoom` + `d3-delaunay` |

## Shared Backend Requirements (Across All Tabs)

| Addition | Needed For |
|----------|-----------|
| `on_step_end` hook instrumentation | All live preview features |
| `CDP Page.startScreencast` per agent | Live video streaming |
| `TaskNode` table + orchestrator events | Task decomposition graph |
| `URLVisit` table | Domain graph, geo heatmap |
| `AgentRunDependency` table | Dependency graph, critical path |
| `queued_at` on `agent_runs` | Wait time calculation |
| `input_tokens`, `output_tokens`, `model_id` on `agent_runs` | Cost tracking |
| `config_label`, `tags` on `sessions` | A/B comparison |
| `run_id` FK on `messages` | Per-run attribution |
| `pgvector` extension | Embedding similarity, UMAP |
| `GET /api/runs/{id}/events` endpoint | Timeline replay |
| `GET /api/sessions/{a}/diff/{b}` endpoint | Session diff view |
