<script lang="ts">
  import { SendIcon, SquareIcon } from 'lucide-svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { cn } from '$lib/utils';

  let {
    onsubmit,
    disabled = false,
    streaming = false,
    onstop,
    onSpawnAgent,
  }: {
    onsubmit: (content: string) => void;
    disabled?: boolean;
    streaming?: boolean;
    onstop?: () => void;
    onSpawnAgent?: () => void;
  } = $props();

  let value = $state('');
  let textarea: HTMLTextAreaElement;
  let _resizeRaf: number | null = null;

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onsubmit(trimmed);
    value = '';
    if (textarea) {
      textarea.style.height = 'auto';
      // Restore focus so user can type the next message immediately
      textarea.focus();
    }
  }

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    } else if (e.key === 'Escape' && streaming && onstop) {
      e.preventDefault();
      onstop();
    }
  }

  function autoresize(e: Event) {
    if (_resizeRaf !== null) return;
    _resizeRaf = requestAnimationFrame(() => {
      _resizeRaf = null;
      const el = e.target as HTMLTextAreaElement;
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    });
  }
</script>

<div class="border-t border-border-subtle bg-background px-4 py-3">
  <div class="max-w-3xl mx-auto transition-shadow duration-200 hover:shadow-lg rounded-2xl">
    <div class="flex items-end gap-2 bg-surface-hover border border-border rounded-2xl px-4 py-3 focus-within:border-accent transition-colors min-h-16">
      <textarea
        bind:this={textarea}
        bind:value
        onkeydown={onkeydown}
        oninput={autoresize}
        placeholder="Message the agent team..."
        rows="2"
        disabled={disabled && !streaming}
        class={cn(
          'flex-1 bg-transparent text-sm text-text placeholder:text-text-faint resize-none outline-none py-1 max-h-[200px] leading-relaxed',
          'disabled:opacity-50 disabled:pointer-events-none'
        )}
      ></textarea>
      {#if streaming && !value.trim() && onstop}
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
          title={streaming ? 'Interrupt and send' : 'Send'}
        >
          <SendIcon size={14} />
        </Button>
      {/if}
    </div>
    <div class="relative flex items-center justify-center mt-2">
      {#if onSpawnAgent}
        <button
          type="button"
          onclick={onSpawnAgent}
          class="absolute left-0 flex items-center gap-1 text-xs text-text-faint hover:text-text transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          Agent
        </button>
      {/if}
      <p class="text-xs text-text-faint">{streaming ? 'Type to interrupt and reprompt · Esc to stop' : 'Enter to send · Shift+Enter for newline'}</p>
    </div>
  </div>
</div>
