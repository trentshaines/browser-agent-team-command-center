<script lang="ts">
  import { cn } from '$lib/utils';
  import type { Snippet } from 'svelte';

  let {
    variant = 'default',
    class: className = '',
    disabled = false,
    onclick,
    type = 'button',
    children,
    ...rest
  }: {
    variant?: 'default' | 'ghost' | 'danger';
    class?: string;
    disabled?: boolean;
    onclick?: (e: MouseEvent) => void;
    type?: 'button' | 'submit' | 'reset';
    children?: Snippet;
    [key: string]: unknown;
  } = $props();

  const base =
    'inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    default: 'bg-accent hover:bg-accent-hover text-white',
    ghost: 'bg-transparent hover:bg-surface-hover text-text-muted hover:text-text',
    danger: 'bg-transparent hover:bg-danger/10 text-text-muted hover:text-danger',
  };
</script>

<button
  {type}
  {disabled}
  {onclick}
  class={cn(base, variants[variant], className)}
  {...rest}
>
  {@render children?.()}
</button>
