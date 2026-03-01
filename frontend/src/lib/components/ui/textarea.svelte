<script lang="ts">
  import { cn } from '$lib/utils';

  let {
    value = $bindable(''),
    class: className = '',
    placeholder = '',
    disabled = false,
    rows = 3,
    ...rest
  }: {
    value?: string;
    class?: string;
    placeholder?: string;
    disabled?: boolean;
    rows?: number;
    [key: string]: unknown;
  } = $props();
</script>

<textarea
  {placeholder}
  {disabled}
  {rows}
  bind:value
  class={cn(
    'w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text placeholder:text-text-faint',
    'focus:outline-none focus:border-accent transition-colors resize-none',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    className
  )}
  {...rest}
></textarea>
