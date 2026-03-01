<script lang="ts">
  import { AgentBrowserWindowTile } from '$lib/components/AgentBrowserWindowTile';
  import type { Message } from '$lib/api';

  type AgentFrame = {
    step: number | null;
    url: string | null;
    screenshot: string | null;
    done: boolean;
  };

  let {
    frames,
    fullscreen = false,
    messages = [],
    onSpawnAgent,
  }: {
    frames: Record<string, AgentFrame>;
    fullscreen?: boolean;
    messages?: Message[];
    onSpawnAgent?: () => void;
  } = $props();

  const agents = $derived(
    Object.entries(frames).map(([id, f]) => ({ agent_id: id, ...f }))
  );

  const TILE_W = 560;
  const CASCADE = 44; // px diagonal offset per tile

  function agentName(agent: { url: string | null; step: number | null }): string {
    if (agent.url) return agent.url.replace(/^https?:\/\//, '').split('/')[0];
    if (agent.step !== null) return `step ${agent.step}`;
    return 'starting…';
  }
</script>

{#if agents.length > 0}
  <div class="{fullscreen ? 'h-full' : 'border-t border-border bg-surface shrink-0 h-64'} relative overflow-hidden">
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
        status={agent.done ? 'Done' : 'In-Progress'}
        agentName={agentName(agent)}
        draggable={true}
        initialWidth={TILE_W}
        initialLeft={24 + i * CASCADE}
        initialTop={fullscreen ? 24 + i * CASCADE : 20 + i * CASCADE}
        {messages}
      />
    {/each}
  </div>
{/if}
