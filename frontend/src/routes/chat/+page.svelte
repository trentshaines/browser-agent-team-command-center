<script lang="ts">
  import { goto } from '$app/navigation';
  import { sessionsStore } from '$lib/stores/sessions';
  import { BotIcon, ArrowRightIcon } from 'lucide-svelte';

  const examples = [
    'Compare pricing on Vercel, Netlify, and Railway',
    'Find all open GitHub issues for sveltejs/svelte',
    'What are the top 5 HN posts right now?',
    'Summarize the latest news about AI agents',
  ];

  async function startWithPrompt(prompt: string) {
    const s = await sessionsStore.create();
    // Navigate with starter prompt as query param
    goto(`/chat/${s.id}?starter=${encodeURIComponent(prompt)}`);
  }

  async function newChat() {
    const s = await sessionsStore.create();
    goto(`/chat/${s.id}`);
  }
</script>

<div class="flex flex-col items-center justify-center flex-1 px-6 gap-8">
  <div class="flex flex-col items-center gap-3 text-center">
    <BotIcon size={40} class="text-[#7c6ff7]" />
    <h1 class="text-2xl font-semibold text-white">Browser Agent Command Center</h1>
    <p class="text-sm text-[#666] max-w-sm">
      Orchestrate a team of browser agents to research, compare, and extract information from the web.
    </p>
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
    {#each examples as example}
      <button
        onclick={() => startWithPrompt(example)}
        class="text-left px-4 py-3 rounded-xl bg-[#111] border border-[#222] hover:border-[#333] hover:bg-[#161616] text-sm text-[#ccc] hover:text-white transition-all group"
      >
        <div class="flex items-start justify-between gap-2">
          <span>{example}</span>
          <ArrowRightIcon size={14} class="shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 text-[#7c6ff7] transition-opacity" />
        </div>
      </button>
    {/each}
  </div>

  <button
    onclick={newChat}
    class="text-sm text-[#666] hover:text-[#aaa] transition-colors"
  >
    or start an empty chat →
  </button>
</div>
