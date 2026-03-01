<script lang="ts">
  import type { Message } from '$lib/api';
  import { senderColor } from '$lib/palette';

  let {
    message,
    senderName,
    compact = false,
  }: {
    message: Message;
    senderName?: string;
    compact?: boolean;
  } = $props();

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
</script>

{#if compact}
  <div class="py-0.5 flex items-baseline gap-1.5 text-xs leading-snug">
    <span class="font-semibold shrink-0" style="color: {nameColor()}">{displayName}</span>
    <span class="text-text whitespace-pre-wrap">{message.content}</span>
    <span class="text-text-faint text-[10px] shrink-0 ml-auto">{timeStr}</span>
  </div>
{:else}
  <div class="mb-2">
    <div class="flex items-baseline gap-1.5 text-xs">
      <span class="font-semibold" style="color: {nameColor()}">{displayName}</span>
      <span class="text-text-faint text-[10px] shrink-0">{timeStr}</span>
    </div>
    <p class="text-text text-xs mt-0.5 whitespace-pre-wrap leading-snug">
      {message.content}
    </p>
  </div>
{/if}
