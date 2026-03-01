<script lang="ts">
  let { content, done = false }: { content: string; done?: boolean } = $props();

  let expanded = $state(true);
  let collapsed = false; // plain var — must NOT be $state or effect cleanup cancels the timeout

  $effect(() => {
    if (done && content && !collapsed) {
      collapsed = true;
      const t = setTimeout(() => { expanded = false; }, 2000);
      return () => clearTimeout(t);
    }
  });
</script>

{#if content}
  <div class="mb-2 border border-border-subtle rounded-lg overflow-hidden">
    <button
      onclick={() => expanded = !expanded}
      class="w-full flex items-center gap-2 px-3 py-1.5 text-left bg-surface hover:bg-surface-hover transition-colors"
    >
      {#if !done}
        <span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0"></span>
      {:else}
        <span class="w-1.5 h-1.5 rounded-full bg-border shrink-0"></span>
      {/if}
      <span class="text-[11px] text-text-faint flex-1 font-mono tracking-wide">
        {done ? 'Thought' : 'Thinking…'}
      </span>
      <span class="text-[10px] text-text-faint opacity-40">{expanded ? '▲' : '▼'}</span>
    </button>

    {#if expanded}
      <div class="px-3 py-2 border-t border-border-subtle text-[11px] text-text-faint leading-relaxed whitespace-pre-wrap font-mono max-h-48 overflow-y-auto bg-surface thinking-scroll">
        {content}
      </div>
    {/if}
  </div>
{/if}
