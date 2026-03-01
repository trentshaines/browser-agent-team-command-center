<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { authStore } from '$lib/stores/auth';
  import { sessionsStore } from '$lib/stores/sessions';
  import Sidebar from '$lib/components/Sidebar.svelte';

  let { children } = $props();
  let ready = $state(false);

  onMount(() => {
    const unsub = authStore.subscribe(async ({ user, loading }) => {
      if (loading) return;
      if (!user) {
        goto('/login', { replaceState: true });
        return;
      }
      await sessionsStore.load();
      ready = true;
    });
    return unsub;
  });
</script>

{#if ready}
  <div class="flex h-screen overflow-hidden bg-[#0d0d0d]">
    <Sidebar />
    <main class="flex-1 flex flex-col min-w-0 overflow-hidden">
      {@render children()}
    </main>
  </div>
{:else}
  <div class="flex items-center justify-center h-screen bg-[#0d0d0d]">
    <div class="w-6 h-6 border-2 border-[#7c6ff7] border-t-transparent rounded-full animate-spin"></div>
  </div>
{/if}
