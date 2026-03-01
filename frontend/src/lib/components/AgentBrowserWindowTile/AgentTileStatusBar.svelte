<script lang="ts">
  import { cn } from '$lib/utils';
  import { palette } from '$lib/palette';

  /** Display status: e.g. "Done", "In-Progress", "Blocked". Any string allowed. */
  let { status = '—', agentName = '—', class: className = '' }: {
    status?: string;
    agentName?: string;
    class?: string;
  } = $props();

  const statusSlug = $derived(status.toLowerCase().replace(/\s+/g, '-'));

  const spinColor = $derived(
    statusSlug === 'done' ? palette.emerald
    : statusSlug === 'in-progress' ? palette.amber
    : statusSlug === 'blocked' ? palette.red
    : 'var(--text-muted)'
  );

  const textClass = $derived(
    statusSlug === 'done' ? 'text-[var(--status-emerald)]'
    : statusSlug === 'in-progress' ? 'text-[var(--status-amber)]'
    : statusSlug === 'blocked' ? 'text-danger'
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
    class="size-3 shrink-0 rounded-full {statusSlug !== 'done' ? 'animate-spin [animation-duration:1.5s]' : ''}"
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
