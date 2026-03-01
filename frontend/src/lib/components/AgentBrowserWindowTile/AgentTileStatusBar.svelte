<script lang="ts">
  import { cn } from '$lib/utils';

  /** Display status: e.g. "Done", "In-Progress", "Blocked". Any string allowed. */
  let { status = '—', agentName = '—', class: className = '' }: {
    status?: string;
    agentName?: string;
    class?: string;
  } = $props();

  const statusSlug = $derived(status.toLowerCase().replace(/\s+/g, '-'));
</script>

<div
  class={cn(
    'flex items-center gap-2 px-3 py-3 text-xs font-medium',
    'border-b border-(--border)/60 bg-black/4',
    className
  )}
  role="status"
  aria-label="Agent status: {status}; Agent: {agentName}"
>
  <span
    class={cn(
      'rounded-full px-2 py-0.5 capitalize',
      statusSlug === 'done' && 'bg-emerald-500/20 text-emerald-800 dark:text-emerald-200',
      statusSlug === 'in-progress' && 'bg-amber-500/20 text-amber-800 dark:text-amber-200',
      statusSlug === 'blocked' && 'bg-red-500/20 text-red-800 dark:text-red-200',
      !['done', 'in-progress', 'blocked'].includes(statusSlug) && 'bg-(--surface-hover) text-(--text-muted)'
    )}
    data-status={statusSlug}
  >
    {status}
  </span>
  <span class="truncate text-(--text-muted)" title={agentName}>
    {agentName}
  </span>
</div>
