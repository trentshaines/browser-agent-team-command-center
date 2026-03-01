<script lang="ts">
  import { AgentBrowserWindowTile } from '$lib/components/AgentBrowserWindowTile';
  import type { Message } from '$lib/api';
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';

  type AgentFrame = {
    step: number | null;
    url: string | null;
    screenshot: string | null;
    done: boolean;
  };

  let {
    runs = [],
    frames = {},
    fullscreen = false,
    messages = [],
    onSpawnAgent,
    onExpandChange,
    onResumeAgent,
  }: {
    runs?: AgentRun[];
    frames?: Record<string, AgentFrame>;
    fullscreen?: boolean;
    messages?: Message[];
    onSpawnAgent?: () => void;
    onExpandChange?: (expanded: boolean) => void;
    onResumeAgent?: (agentId: string) => void;
  } = $props();

  // Merge agentRuns with frame data — tiles appear as soon as agents spawn,
  // screenshots fill in when agent_frame events arrive.
  const agents = $derived(
    runs.map(run => {
      const frame = frames[run.id];
      return {
        agent_id: run.id,
        name: run.name ?? null,
        task: run.task,
        status: run.status,
        step: frame?.step ?? (run.steps.length > 0 ? run.steps[run.steps.length - 1].step : null),
        url: frame?.url ?? (run.steps.length > 0 ? run.steps[run.steps.length - 1].url ?? null : null),
        screenshot: frame?.screenshot ?? null,
        done: run.status !== 'running' && run.status !== 'paused',
        liveUrl: run.liveUrl ?? null,
        handoffMessage: run.handoffMessage ?? null,
      };
    })
  );

  const TILE_W = 560;
  const CASCADE = 44; // px diagonal offset per tile

  function agentName(agent: { name: string | null; url: string | null; step: number | null }): string {
    if (agent.name) return agent.name;
    if (agent.url) return agent.url.replace(/^https?:\/\//, '').split('/')[0];
    if (agent.step !== null) return `step ${agent.step}`;
    return 'starting…';
  }
</script>

{#if agents.length > 0}
  <!-- Use absolute inset-0 instead of h-full so the wrapper gets real dimensions
       from <main> even for absolutely-positioned tile children -->
  <div class="{fullscreen ? 'absolute inset-0' : 'border-t border-border bg-surface shrink-0 h-64 relative'} overflow-hidden">
    <!-- Windows header / spawn button -->
    <div class="absolute top-2 {fullscreen ? 'right-3' : 'left-4 right-3'} flex items-center gap-2 z-10">
      {#if !fullscreen}
        <span class="text-[10px] font-medium text-text-faint uppercase tracking-widest pointer-events-none">Windows</span>
        <span class="text-[10px] text-text-faint pointer-events-none">({agents.length})</span>
      {/if}
      {#if onSpawnAgent}
        <button
          onclick={onSpawnAgent}
          class="ml-auto flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium text-text-faint hover:text-text hover:bg-white/30 transition-all"
          aria-label="Spawn new agent"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          Agent
        </button>
      {/if}
    </div>

    {#each agents as agent, i (agent.agent_id)}
      <AgentBrowserWindowTile
        src={agent.screenshot ? `data:image/jpeg;base64,${agent.screenshot}` : undefined}
        status={agent.status === 'paused' ? 'Blocked' : agent.done ? 'Done' : 'In-Progress'}
        agentName={agentName(agent)}
        draggable={true}
        initialWidth={TILE_W}
        initialLeft={24 + i * CASCADE}
        initialTop={fullscreen ? 24 + i * CASCADE : 20 + i * CASCADE}
        {messages}
        liveUrl={agent.liveUrl}
        blockedMessage={agent.handoffMessage}
        {onExpandChange}
        onResume={onResumeAgent ? () => onResumeAgent(agent.agent_id) : undefined}
      />
    {/each}
  </div>
{/if}
