<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { authStore } from '$lib/stores/auth';
  import { sessionsStore, sessionsLoading } from '$lib/stores/sessions';
  import { PlusIcon, Trash2Icon, LogOutIcon } from 'lucide-svelte';
  import Button from '$lib/components/ui/button.svelte';
  import CreateProjectModal from '$lib/components/CreateProjectModal.svelte';
  import { cn } from '$lib/utils';

  let deletingId = $state<string | null>(null);
  let confirmDeleteId = $state<string | null>(null);
  let createModalOpen = $state(false);

  async function deleteSession(e: MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    if (confirmDeleteId !== id) {
      confirmDeleteId = id;
      // Auto-dismiss confirm after 3s
      setTimeout(() => { if (confirmDeleteId === id) confirmDeleteId = null; }, 3000);
      return;
    }
    confirmDeleteId = null;
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
    <span class="text-base">🪟</span>
    <span class="font-semibold text-sm text-text">Windows</span>
  </div>

  <!-- New Project button -->
  <div class="px-3 pt-3 pb-2">
    <Button
      onclick={() => (createModalOpen = true)}
      class="w-full px-3 py-2"
      aria-label="New project"
    >
      <PlusIcon size={15} />
      New Project
    </Button>
  </div>

  <CreateProjectModal isOpen={createModalOpen} onClose={() => (createModalOpen = false)} />

  <!-- Session list -->
  <nav class="flex-1 overflow-y-auto px-2 pb-2">
    {#if $sessionsLoading}
      <div class="flex justify-center py-6" role="status" aria-label="Loading chats">
        <div class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" aria-hidden="true"></div>
      </div>
    {/if}
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
          {#if confirmDeleteId === session.id}
            <button
              onclick={(e) => deleteSession(e, session.id)}
              class="text-[10px] text-danger font-medium px-1.5 py-0.5 rounded bg-danger/10 hover:bg-danger/20 transition-colors shrink-0"
            >
              Sure?
            </button>
          {:else}
            <Button
              variant="danger"
              onclick={(e) => deleteSession(e, session.id)}
              disabled={deletingId === session.id}
              class="opacity-0 group-hover:opacity-100 p-0.5 w-auto h-auto rounded transition-opacity"
              aria-label="Delete chat"
            >
              {#if deletingId === session.id}
                <LoaderIcon size={13} class="animate-spin" />
              {:else}
                <Trash2Icon size={13} />
              {/if}
            </Button>
          {/if}
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
