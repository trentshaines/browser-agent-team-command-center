<script lang="ts">
  type AgentFrame = {
    step: number | null;
    url: string | null;
    screenshot: string | null;
    done: boolean;
  };

  let { frames }: { frames: Record<string, AgentFrame> } = $props();

  const agents = $derived(
    Object.entries(frames).map(([id, f]) => ({ agent_id: id, ...f }))
  );
  const cols = $derived(agents.length <= 1 ? 1 : agents.length <= 4 ? 2 : 3);
</script>

{#if agents.length > 0}
  <div class="border-t border-border bg-surface px-4 py-3 shrink-0 agent-tiles-panel">
    <div class="flex items-center gap-2 mb-2">
      <span class="text-[10px] font-medium text-text-faint uppercase tracking-widest">Browser Agents</span>
      <span class="text-[10px] text-text-faint">({agents.length})</span>
    </div>
    <div
      class="grid gap-2"
      style="grid-template-columns: repeat({cols}, minmax(0, 1fr))"
    >
      {#each agents as agent (agent.agent_id)}
        <div class="rounded-lg border border-border overflow-hidden bg-background">
          <!-- Screenshot -->
          <div class="relative bg-[#1a1a1a] aspect-video">
            {#if agent.screenshot}
              <img
                src="data:image/jpeg;base64,{agent.screenshot}"
                alt="agent browser"
                class="w-full h-full object-cover"
              />
            {:else}
              <div class="flex items-center justify-center h-full">
                <div class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
              </div>
            {/if}
            <!-- Status badge -->
            <div class="absolute top-1.5 right-1.5">
              {#if agent.done}
                <span class="text-[9px] bg-emerald-500/90 text-white px-1.5 py-0.5 rounded-full font-medium">done</span>
              {:else}
                <span class="text-[9px] bg-violet-500/90 text-white px-1.5 py-0.5 rounded-full font-medium animate-pulse">live</span>
              {/if}
            </div>
          </div>
          <!-- Info bar -->
          <div class="px-2 py-1.5 flex items-center gap-2 min-w-0 bg-surface">
            {#if agent.step !== null}
              <span class="text-[10px] text-text-faint shrink-0">step {agent.step}</span>
            {/if}
            {#if agent.url}
              <span class="text-[10px] text-text-muted truncate" title={agent.url}>
                {agent.url.replace(/^https?:\/\//, '').split('/')[0]}
              </span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
