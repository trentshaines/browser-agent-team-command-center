<script lang="ts">
  import { SendIcon, SquareIcon } from 'lucide-svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { cn } from '$lib/utils';

  let {
    onsubmit,
    disabled = false,
    streaming = false,
    onstop,
  }: {
    onsubmit: (content: string) => void;
    disabled?: boolean;
    streaming?: boolean;
    onstop?: () => void;
  } = $props();

  let value = $state('');
  let textarea: HTMLTextAreaElement;

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onsubmit(trimmed);
    value = '';
    if (textarea) {
      textarea.style.height = 'auto';
    }
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autoresize(e: Event) {
    const el = e.target as HTMLTextAreaElement;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }
</script>

<div class="border-t border-border-subtle bg-background px-4 py-3">
  <div class="max-w-3xl mx-auto">
    <div class="flex items-end gap-2 bg-surface-hover border border-border rounded-2xl px-4 py-2 focus-within:border-border transition-colors">
      <textarea
        bind:this={textarea}
        bind:value
        onkeydown={onkeydown}
        oninput={autoresize}
        placeholder="Message the agent team..."
        rows="1"
        disabled={disabled && !streaming}
        class={cn(
          'flex-1 bg-transparent text-sm text-text placeholder:text-text-faint resize-none outline-none py-1 max-h-[200px] leading-relaxed',
          'disabled:opacity-50'
        )}
      ></textarea>
      {#if streaming && onstop}
        <Button
          variant="ghost"
          onclick={onstop}
          class="w-8 h-8 rounded-lg shrink-0 mb-0.5 p-0"
          title="Stop"
        >
          <SquareIcon size={14} fill="currentColor" />
        </Button>
      {:else}
        <Button
          onclick={submit}
          disabled={!value.trim() || disabled}
          class="w-8 h-8 rounded-lg shrink-0 mb-0.5 p-0"
          title="Send"
        >
          <SendIcon size={14} />
        </Button>
      {/if}
    </div>
    <p class="text-xs text-text-faint text-center mt-2">Enter to send · Shift+Enter for newline</p>
  </div>
</div>
