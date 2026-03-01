<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { authStore } from '$lib/stores/auth';
  import { auth } from '$lib/api';
  import { BotIcon } from 'lucide-svelte';

  onMount(() => {
    const unsub = authStore.subscribe(({ user, loading }) => {
      if (!loading && user) goto('/chat', { replaceState: true });
    });
    return unsub;
  });
</script>

<div class="flex items-center justify-center h-screen bg-[#0d0d0d]">
  <div class="flex flex-col items-center gap-8 max-w-sm w-full px-6">
    <div class="flex items-center gap-3">
      <BotIcon size={32} class="text-[#7c6ff7]" />
      <h1 class="text-2xl font-semibold text-white">Browser Agents</h1>
    </div>

    <div class="w-full bg-[#111] border border-[#222] rounded-2xl p-8 flex flex-col gap-4">
      <p class="text-sm text-[#888] text-center">Sign in to orchestrate your browser agent team</p>

      <a
        href={auth.googleUrl()}
        class="flex items-center justify-center gap-3 w-full py-2.5 px-4 rounded-xl border border-[#333] bg-[#1a1a1a] hover:bg-[#242424] text-white text-sm font-medium transition-colors"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
          <path d="M9 18c2.43 0 4.467-.806 5.956-2.18L12.048 13.561c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
          <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
          <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
        </svg>
        Continue with Google
      </a>
    </div>
  </div>
</div>
