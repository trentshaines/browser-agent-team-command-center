<script lang="ts">
  import { SendIcon, SquareIcon } from 'lucide-svelte';

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
    // Reset textarea height
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

<div class="border-t border-[#222] bg-[#0d0d0d] px-4 py-3">
  <div class="max-w-3xl mx-auto">
    <div class="flex items-end gap-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-2xl px-4 py-2 focus-within:border-[#444] transition-colors">
      <textarea
        bind:this={textarea}
        bind:value
        onkeydown={onkeydown}
        oninput={autoresize}
        placeholder="Message the agent team..."
        rows="1"
        disabled={disabled && !streaming}
        class="flex-1 bg-transparent text-sm text-[#e8e8e8] placeholder-[#555] resize-none outline-none py-1 max-h-[200px] leading-relaxed disabled:opacity-50"
      ></textarea>
      {#if streaming && onstop}
        <button
          onclick={onstop}
          class="flex items-center justify-center w-8 h-8 rounded-lg bg-[#333] hover:bg-[#444] text-[#aaa] hover:text-white transition-colors shrink-0 mb-0.5"
          title="Stop"
        >
          <SquareIcon size={14} fill="currentColor" />
        </button>
      {:else}
        <button
          onclick={submit}
          disabled={!value.trim() || disabled}
          class="flex items-center justify-center w-8 h-8 rounded-lg bg-[#7c6ff7] hover:bg-[#6a5fe0] text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0 mb-0.5"
          title="Send"
        >
          <SendIcon size={14} />
        </button>
      {/if}
    </div>
    <p class="text-xs text-[#444] text-center mt-2">Enter to send · Shift+Enter for newline</p>
  </div>
</div>
