<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { authStore } from '$lib/stores/auth';
  import { sessionsStore } from '$lib/stores/sessions';
  import { PlusIcon, Trash2Icon, BotIcon, LogOutIcon } from 'lucide-svelte';
  import Button from '$lib/components/ui/button.svelte';
  import { cn } from '$lib/utils';

  let deletingId = $state<string | null>(null);
  let creating = $state(false);

  async function newChat() {
    if (creating) return;
    creating = true;
    try {
      const s = await sessionsStore.create();
      goto(`/chat/${s.id}`);
    } finally {
      creating = false;
    }
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

<aside class="flex flex-col h-full w-64 shrink-0 bg-surface border-r border-border-subtle">
  <!-- Header -->
  <div class="flex items-center gap-2 px-4 py-3 border-b border-border-subtle">
    <BotIcon size={18} class="text-accent" />
    <span class="font-semibold text-sm text-text">Browser Agents</span>
  </div>

  <!-- New Chat button -->
  <div class="px-3 pt-3 pb-2">
    <Button
      onclick={newChat}
      disabled={creating}
      class="w-full px-3 py-2"
    >
      <PlusIcon size={15} />
      New Chat
    </Button>
  </div>

  <!-- Session list -->
  <nav class="flex-1 overflow-y-auto px-2 pb-2">
    {#each $sessionsStore as session (session.id)}
      {@const active = page.params.sessionId === session.id}
      <a
        href="/chat/{session.id}"
        class={cn(
          'flex items-center justify-between group px-3 py-2 rounded-lg text-sm mb-0.5 transition-colors',
          active
            ? 'bg-surface-hover text-text'
            : 'text-text-muted hover:bg-surface-hover hover:text-text'
        )}
      >
        <span class="truncate flex-1 mr-2">{session.title}</span>
        <div class="flex items-center gap-1.5 shrink-0">
          <span class="text-xs text-text-faint group-hover:text-text-muted">{formatDate(session.updated_at)}</span>
          <Button
            variant="danger"
            onclick={(e) => deleteSession(e, session.id)}
            disabled={deletingId === session.id}
            class="opacity-0 group-hover:opacity-100 p-0.5 w-auto h-auto rounded transition-opacity"
          >
            <Trash2Icon size={13} />
          </Button>
        </div>
      </a>
    {/each}
    {#if $sessionsStore.length === 0}
      <p class="text-xs text-text-faint px-3 py-4 text-center">No chats yet</p>
    {/if}
  </nav>

  <!-- User footer -->
  <div class="px-3 py-3 border-t border-border-subtle">
    {#if $authStore.user}
      <div class="flex items-center gap-2">
        {#if $authStore.user.profile_image}
          <img src={$authStore.user.profile_image} alt="" class="w-7 h-7 rounded-full" />
        {:else}
          <div class="w-7 h-7 rounded-full bg-border flex items-center justify-center text-xs font-medium text-text">
            {$authStore.user.username[0].toUpperCase()}
          </div>
        {/if}
        <span class="text-sm text-text-muted truncate flex-1">{$authStore.user.username}</span>
<Button
          variant="danger"
          onclick={() => authStore.logout().then(() => goto('/login'))}
          class="p-1 w-auto h-auto rounded"
          title="Logout"
        >
          <LogOutIcon size={15} />
        </Button>
      </div>
    {/if}
  </div>
</aside>
