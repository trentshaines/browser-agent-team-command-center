<script lang="ts">
  import { cn } from '$lib/utils';

  /** Display status: e.g. "Done", "In-Progress", "Blocked". Any string allowed. */
  let { status = '—', agentName = '—', class: className = '' }: {
    status?: string;
    agentName?: string;
    class?: string;
  } = $props();

  const statusSlug = $derived(status.toLowerCase().replace(/\s+/g, '-'));

  const spinColor = $derived(
    statusSlug === 'done' ? '#10b981'
    : statusSlug === 'in-progress' ? '#f59e0b'
    : statusSlug === 'blocked' ? '#ef4444'
    : '#6b7280'
  );

  const textClass = $derived(
    statusSlug === 'done' ? 'text-emerald-500'
    : statusSlug === 'in-progress' ? 'text-amber-500'
    : statusSlug === 'blocked' ? 'text-red-500'
    : 'text-(--text-muted)'
  );
</script>

<div
  class={cn(
    'flex items-center gap-2 px-3 py-1.5 text-xs font-medium',
    className
  )}
  role="status"
  aria-label="Agent status: {status}; Agent: {agentName}"
>
  <!-- Spinning gradient live indicator -->
  <div
    class="size-3 shrink-0 animate-spin rounded-full [animation-duration:1.5s]"
    style="background: conic-gradient(from 0deg, transparent 0%, {spinColor} 70%, transparent 100%)"
  ></div>

  <!-- Bracketed status -->
  <span class={cn('font-semibold', textClass)} data-status={statusSlug}>
    [{status}]
  </span>

  <!-- Agent name -->
  <span class="truncate text-(--text-muted)" title={agentName}>
    {agentName}
  </span>
</div>
