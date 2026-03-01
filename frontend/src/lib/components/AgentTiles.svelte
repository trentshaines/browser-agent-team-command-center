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
  }: {
    frames: Record<string, AgentFrame>;
    fullscreen?: boolean;
    messages?: Message[];
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
    {#if !fullscreen}
      <div class="absolute top-2 left-4 flex items-center gap-2 z-10 pointer-events-none">
        <span class="text-[10px] font-medium text-text-faint uppercase tracking-widest">Windows</span>
        <span class="text-[10px] text-text-faint">({agents.length})</span>
      </div>
    {/if}
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
