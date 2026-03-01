<script lang="ts">
  import WidgetMessageBubble from './WidgetMessageBubble.svelte';
  import type { WidgetMessage } from './types';

  let {
    messages,
    onSend,
    placeholder = 'Message the team...',
    onSpawnAgent,
  }: {
    messages: WidgetMessage[];
    onSend?: (content: string) => void;
    placeholder?: string;
    onSpawnAgent?: () => void;
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
    class="flex-1 min-h-0 overflow-y-auto px-3 py-2 flex flex-col bg-transparent"
  >
    {#each messages as msg, i (msg.id)}
      {@const prevSender = i > 0 ? (messages[i - 1].senderName ?? (messages[i - 1].role === 'user' ? 'You' : 'Orchestrator')) : null}
      {@const thisSender = msg.senderName ?? (msg.role === 'user' ? 'You' : 'Orchestrator')}
      {@const sameSender = prevSender === thisSender}
      <WidgetMessageBubble message={msg} senderName={msg.senderName} compact={sameSender} />
    {/each}
  </div>

  {#if onSend}
    <div class="shrink-0 border-t border-border-subtle/50 px-3 py-2">
      <div class="flex items-center gap-2 rounded-xl bg-surface border border-border-subtle px-3 py-2 focus-within:border-border transition-colors">
        {#if onSpawnAgent}
          <button
            type="button"
            onclick={onSpawnAgent}
            class="shrink-0 flex items-center gap-1 text-xs text-text-faint hover:text-text transition-colors pr-2 border-r border-border-subtle"
            aria-label="Spawn new agent"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            Agent
          </button>
        {/if}
        <input
          bind:this={inputEl}
          bind:value={inputValue}
          onkeydown={onKeydown}
          type="text"
          {placeholder}
          class="flex-1 bg-transparent text-xs text-text placeholder:text-text-faint outline-none"
        />
      </div>
    </div>
  {/if}
</div>
