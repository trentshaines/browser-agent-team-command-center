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
  const cols = $derived(agents.length <= 1 ? 1 : agents.length <= 4 ? 2 : 3);

  function agentName(agent: { url: string | null; step: number | null }): string {
    if (agent.url) return agent.url.replace(/^https?:\/\//, '').split('/')[0];
    if (agent.step !== null) return `step ${agent.step}`;
    return 'starting…';
  }
</script>

{#if agents.length > 0}
  <div class="{fullscreen ? 'h-full flex flex-col' : 'border-t border-border bg-surface px-4 py-3 shrink-0'}">
    {#if !fullscreen}
      <div class="flex items-center gap-2 mb-2">
        <span class="text-[10px] font-medium text-text-faint uppercase tracking-widest">Windows</span>
        <span class="text-[10px] text-text-faint">({agents.length})</span>
      </div>
    {/if}
    <div
      class="grid gap-3 {fullscreen ? 'flex-1' : ''}"
      style="grid-template-columns: repeat({cols}, minmax(0, 1fr)); {fullscreen ? 'align-content: start' : ''}"
    >
      {#each agents as agent (agent.agent_id)}
        <AgentBrowserWindowTile
          src={agent.screenshot ? `data:image/jpeg;base64,${agent.screenshot}` : undefined}
          status={agent.done ? 'Done' : 'In-Progress'}
          agentName={agentName(agent)}
          draggable={true}
          {messages}
        />
      {/each}
    </div>
  </div>
{/if}
