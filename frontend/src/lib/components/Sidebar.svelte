<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { authStore } from '$lib/stores/auth';
  import { sessionsStore } from '$lib/stores/sessions';
  import { PlusIcon, Trash2Icon, BotIcon, LogOutIcon } from 'lucide-svelte';

  let deletingId = $state<string | null>(null);

  async function newChat() {
    const s = await sessionsStore.create();
    goto(`/chat/${s.id}`);
  }

  async function deleteSession(e: MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    deletingId = id;
    await sessionsStore.delete(id);
    deletingId = null;
    if (page.params.sessionId === id) goto('/chat');
  }

  function formatDate(iso: string) {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 86400000) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diff < 604800000) return d.toLocaleDateString([], { weekday: 'short' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }
</script>

<aside class="flex flex-col h-full w-64 shrink-0 bg-[#111] border-r border-[#222]">
  <!-- Header -->
  <div class="flex items-center gap-2 px-4 py-3 border-b border-[#222]">
    <BotIcon size={18} class="text-[#7c6ff7]" />
    <span class="font-semibold text-sm text-white">Browser Agents</span>
  </div>

  <!-- New Chat button -->
  <div class="px-3 pt-3 pb-2">
    <button
      onclick={newChat}
      class="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-lg bg-[#7c6ff7] hover:bg-[#6a5fe0] text-white transition-colors"
    >
      <PlusIcon size={15} />
      New Chat
    </button>
  </div>

  <!-- Session list -->
  <nav class="flex-1 overflow-y-auto px-2 pb-2">
    {#each $sessionsStore as session (session.id)}
      {@const active = page.params.sessionId === session.id}
      <a
        href="/chat/{session.id}"
        class="flex items-center justify-between group px-3 py-2 rounded-lg text-sm mb-0.5 transition-colors {active ? 'bg-[#1e1e1e] text-white' : 'text-[#aaa] hover:bg-[#181818] hover:text-white'}"
      >
        <span class="truncate flex-1 mr-2">{session.title}</span>
        <div class="flex items-center gap-1.5 shrink-0">
          <span class="text-xs text-[#555] group-hover:text-[#666]">{formatDate(session.updated_at)}</span>
          <button
            onclick={(e) => deleteSession(e, session.id)}
            disabled={deletingId === session.id}
            class="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-red-400 transition-opacity"
          >
            <Trash2Icon size={13} />
          </button>
        </div>
      </a>
    {/each}
    {#if $sessionsStore.length === 0}
      <p class="text-xs text-[#555] px-3 py-4 text-center">No chats yet</p>
    {/if}
  </nav>

  <!-- User footer -->
  <div class="px-3 py-3 border-t border-[#222]">
    {#if $authStore.user}
      <div class="flex items-center gap-2">
        {#if $authStore.user.profile_image}
          <img src={$authStore.user.profile_image} alt="" class="w-7 h-7 rounded-full" />
        {:else}
          <div class="w-7 h-7 rounded-full bg-[#333] flex items-center justify-center text-xs font-medium">
            {$authStore.user.username[0].toUpperCase()}
          </div>
        {/if}
        <span class="text-sm text-[#ccc] truncate flex-1">{$authStore.user.username}</span>
        <button
          onclick={() => authStore.logout().then(() => goto('/login'))}
          class="p-1 rounded hover:text-red-400 text-[#555] transition-colors"
          title="Logout"
        >
          <LogOutIcon size={15} />
        </button>
      </div>
    {/if}
  </div>
</aside>
