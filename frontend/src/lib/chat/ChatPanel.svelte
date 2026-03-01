<script lang="ts">
  import WidgetMessageBubble from './WidgetMessageBubble.svelte';
  import type { WidgetMessage } from './types';

  let {
    messages,
    onSend,
    placeholder = 'Message the team...',
  }: {
    messages: WidgetMessage[];
    onSend?: (content: string) => void;
    placeholder?: string;
  } = $props();

  let inputValue = $state('');
  let inputEl: HTMLInputElement;
  let scrollEl: HTMLDivElement;

  $effect(() => {
    messages; // rerun when messages change
    requestAnimationFrame(() => {
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    });
  });

  function submit() {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    onSend?.(trimmed);
    inputValue = '';
    inputEl?.focus();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }
</script>

<div class="flex-1 min-h-0 flex flex-col overflow-hidden">
  <div
    bind:this={scrollEl}
    class="flex-1 min-h-0 overflow-y-auto px-4 py-3 flex flex-col bg-transparent"
  >
    {#each messages as msg (msg.id)}
      <WidgetMessageBubble message={msg} senderName={msg.senderName} />
    {/each}
  </div>

  {#if onSend}
    <div class="shrink-0 border-t border-border-subtle/50 px-3 py-3">
      <div class="flex items-center gap-2 rounded-2xl bg-surface border border-border-subtle px-4 py-2.5 focus-within:border-border transition-colors">
        <input
          bind:this={inputEl}
          bind:value={inputValue}
          onkeydown={onKeydown}
          type="text"
          {placeholder}
          class="flex-1 bg-transparent text-sm text-text placeholder:text-text-faint outline-none"
        />
      </div>
    </div>
  {/if}
</div>
