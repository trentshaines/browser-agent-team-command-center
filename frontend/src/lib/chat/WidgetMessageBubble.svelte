<script lang="ts">
  import { marked } from 'marked';
  import type { Message } from '$lib/api';
  import { senderColor } from '$lib/palette';
  import type { MessageCategory } from './types';

  let {
    message,
    senderName,
    compact = false,
    category,
  }: {
    message: Message;
    senderName?: string;
    compact?: boolean;
    category?: MessageCategory;
  } = $props();

  const isBlocked = $derived(category === 'blocked');

  const displayName = $derived(
    senderName ?? (message.role === 'user' ? 'You' : 'Orchestrator')
  );

  const timeStr = $derived.by(() => {
    try {
      const d = new Date(message.created_at);
      return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
    } catch {
      return '';
    }
  });

  const nameColor = $derived(() => {
    if (message.role === 'user') return 'var(--text)';
    return senderColor(displayName);
  });

  const renderedHtml = $derived.by(() => {
    if (message.role === 'user') return '';
    return marked.parse(message.content, { async: false, breaks: true }) as string;
  });
</script>

{#if isBlocked}
  <div class="mb-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
    <div class="flex items-center gap-1.5 text-xs">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-red-500 shrink-0"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <span class="font-semibold text-red-400">{displayName} needs help</span>
      <span class="text-text-faint text-[10px] shrink-0 ml-auto">{timeStr}</span>
    </div>
    <p class="text-red-300/90 text-xs mt-1 leading-snug">{message.content}</p>
  </div>
{:else if compact}
  <div class="py-0.5 flex items-baseline gap-1.5 text-xs leading-snug">
    <span class="font-semibold shrink-0" style="color: {nameColor()}">{displayName}</span>
    {#if message.role === 'user'}
      <span class="text-text whitespace-pre-wrap">{message.content}</span>
    {:else}
      <span class="text-text widget-prose">{@html renderedHtml}</span>
    {/if}
    <span class="text-text-faint text-[10px] shrink-0 ml-auto">{timeStr}</span>
  </div>
{:else}
  <div class="mb-2">
    <div class="flex items-baseline gap-1.5 text-xs">
      <span class="font-semibold" style="color: {nameColor()}">{displayName}</span>
      <span class="text-text-faint text-[10px] shrink-0">{timeStr}</span>
    </div>
    {#if message.role === 'user'}
      <p class="text-text text-xs mt-0.5 whitespace-pre-wrap leading-snug">
        {message.content}
      </p>
    {:else}
      <div class="text-text text-xs mt-0.5 leading-snug widget-prose">
        {@html renderedHtml}
      </div>
    {/if}
  </div>
{/if}
