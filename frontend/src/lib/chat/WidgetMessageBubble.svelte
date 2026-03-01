<script lang="ts">
  import type { Message } from '$lib/api';

  let {
    message,
    senderName,
  }: {
    message: Message;
    senderName?: string;
  } = $props();

  const displayName = $derived(
    senderName ?? (message.role === 'user' ? 'You' : 'Assistant')
  );

  const timeStr = $derived.by(() => {
    try {
      const d = new Date(message.created_at);
      return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
    } catch {
      return '';
    }
  });

  const nameColorClass = $derived(
    message.role === 'user'
      ? 'text-text font-medium'
      : displayName === 'Kelly Agent'
        ? 'text-[#6366f1] font-medium'
        : displayName === 'James Agent'
          ? 'text-[#dc2626] font-medium'
          : 'text-accent font-medium'
  );
</script>

<div
  class="mb-4 {message.role === 'user'
    ? 'rounded-2xl bg-surface-hover/60 px-3 py-2.5'
    : ''}"
>
  <div class="flex flex-wrap items-baseline gap-2 text-sm">
    <span class={nameColorClass}>{displayName}</span>
    <span class="text-text-faint text-xs shrink-0">{timeStr}</span>
  </div>
  <p class="text-text text-sm mt-1 whitespace-pre-wrap leading-relaxed {message.role === 'user' ? '' : 'pl-0'}">
    {message.content}
  </p>
</div>
