<script lang="ts">
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';
  import { browser } from '$app/environment';
  import type { Message } from '$lib/api';
  import ThinkingBlock from './ThinkingBlock.svelte';

  let {
    message,
    thinking = '',
    thinkingDone = false,
  }: {
    message: Message;
    thinking?: string;
    thinkingDone?: boolean;
  } = $props();

  const html = $derived(
    message.role === 'assistant' && message.content
      ? (() => {
          const parsed = marked.parse(message.content, { async: false }) as string;
          return browser ? DOMPurify.sanitize(parsed) : parsed;
        })()
      : null
  );
</script>

{#if message.role === 'user'}
  <div class="flex justify-end mb-4">
    <div class="max-w-[75%] px-4 py-2.5 rounded-2xl bg-surface text-text text-sm whitespace-pre-wrap leading-relaxed">
      {message.content}
    </div>
  </div>
{:else}
  <div class="flex justify-start mb-4">
    <div class="max-w-[85%] text-text text-sm w-full">
      <ThinkingBlock content={thinking} done={thinkingDone} />
      {#if message.content}
        <div class="prose">{@html html}</div>
      {:else if !thinking}
        <div class="flex items-center gap-1.5 text-text-faint">
          <span class="animate-pulse">●</span>
          <span class="animate-pulse" style="animation-delay:0.15s">●</span>
          <span class="animate-pulse" style="animation-delay:0.3s">●</span>
        </div>
      {/if}
    </div>
  </div>
{/if}
