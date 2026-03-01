<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { authStore } from '$lib/stores/auth';

  let error = $state<string | null>(null);

  onMount(async () => {
    const code = page.url.searchParams.get('code');
    if (!code) {
      error = 'No authorization code received';
      return;
    }

    try {
      const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
      const res = await fetch(`${BASE}/auth/google`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });

      if (!res.ok) throw new Error('Auth failed');

      const data = await res.json();
      await authStore.init();
      goto('/chat', { replaceState: true });
    } catch (e) {
      error = 'Authentication failed. Please try again.';
    }
  });
</script>

<div class="flex items-center justify-center h-screen bg-[#0d0d0d]">
  {#if error}
    <div class="flex flex-col items-center gap-4 text-center px-6">
      <p class="text-red-400 text-sm">{error}</p>
      <a href="/login" class="text-sm text-[#7c6ff7] hover:underline">Back to login</a>
    </div>
  {:else}
    <div class="flex flex-col items-center gap-4">
      <div class="w-6 h-6 border-2 border-[#7c6ff7] border-t-transparent rounded-full animate-spin"></div>
      <p class="text-sm text-[#888]">Signing you in...</p>
    </div>
  {/if}
</div>
