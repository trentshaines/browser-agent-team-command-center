<script lang="ts">
  import { marked } from 'marked';
  import type { Message } from '$lib/api';

  let { message }: { message: Message } = $props();

  const html = $derived(
    message.role === 'assistant' && message.content
      ? marked.parse(message.content, { async: false }) as string
      : null
  );
</script>

{#if message.role === 'user'}
  <div class="flex justify-end mb-4">
    <div class="max-w-[75%] px-4 py-2.5 rounded-2xl bg-[#1e1e1e] text-[#e8e8e8] text-sm whitespace-pre-wrap leading-relaxed">
      {message.content}
    </div>
  </div>
{:else}
  <div class="flex justify-start mb-4">
    <div class="max-w-[85%] text-[#e0e0e0] text-sm">
      {#if message.content}
        <div class="prose">{@html html}</div>
      {:else}
        <div class="flex items-center gap-1.5 text-[#555]">
          <span class="animate-pulse">●</span>
          <span class="animate-pulse" style="animation-delay:0.15s">●</span>
          <span class="animate-pulse" style="animation-delay:0.3s">●</span>
        </div>
      {/if}
    </div>
  </div>
{/if}
