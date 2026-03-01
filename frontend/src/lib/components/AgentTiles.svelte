<script lang="ts">
  type AgentFrame = {
    step: number | null;
    url: string | null;
    screenshot: string | null;
    done: boolean;
  };

  let { frames, fullscreen = false }: { frames: Record<string, AgentFrame>; fullscreen?: boolean } = $props();

  const agents = $derived(
    Object.entries(frames).map(([id, f]) => ({ agent_id: id, ...f }))
  );
  const cols = $derived(agents.length <= 1 ? 1 : agents.length <= 4 ? 2 : 3);
</script>

{#if agents.length > 0}
  <div class="{fullscreen ? 'h-full flex flex-col' : 'border-t border-border bg-surface px-4 py-3 shrink-0'}">
    {#if !fullscreen}
      <div class="flex items-center gap-2 mb-2">
        <span class="text-[10px] font-medium text-text-faint uppercase tracking-widest">Browser Agents</span>
        <span class="text-[10px] text-text-faint">({agents.length})</span>
      </div>
    {/if}
    <div
      class="grid gap-3 {fullscreen ? 'flex-1' : ''}"
      style="grid-template-columns: repeat({cols}, minmax(0, 1fr)); {fullscreen ? 'align-content: start' : ''}"
    >
      {#each agents as agent (agent.agent_id)}
        <div class="rounded-xl border border-border overflow-hidden bg-background flex flex-col">
          <!-- Screenshot -->
          <div class="relative bg-[#1a1a1a] {fullscreen ? 'aspect-video' : 'aspect-video'}">
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
            <div class="absolute top-2 right-2">
              {#if agent.done}
                <span class="text-[9px] bg-emerald-500/90 text-white px-1.5 py-0.5 rounded-full font-medium">done</span>
              {:else}
                <span class="text-[9px] bg-violet-500/90 text-white px-1.5 py-0.5 rounded-full font-medium animate-pulse">live</span>
              {/if}
            </div>
            <!-- Step overlay -->
            {#if agent.step !== null}
              <div class="absolute bottom-2 left-2">
                <span class="text-[9px] bg-black/60 text-white px-1.5 py-0.5 rounded font-mono">step {agent.step}</span>
              </div>
            {/if}
          </div>
          <!-- Info bar -->
          <div class="px-3 py-2 flex items-center gap-2 min-w-0 bg-surface">
            {#if agent.url}
              <span class="text-[11px] text-text-muted truncate" title={agent.url}>
                {agent.url.replace(/^https?:\/\//, '').split('/')[0]}
              </span>
            {:else}
              <span class="text-[11px] text-text-faint italic">starting…</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
