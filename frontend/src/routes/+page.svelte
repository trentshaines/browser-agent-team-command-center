<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";
  import { authStore } from "$lib/stores/auth";

  onMount(() => {
    const unsub = authStore.subscribe(({ user, loading }) => {
      if (loading) return;
      if (user) {
        goto("/chat", { replaceState: true });
      } else {
        goto("/login", { replaceState: true });
      }
    });
    return unsub;
  });
</script>

<div class="flex items-center justify-center h-screen bg-background">
  <div
    class="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin"
  ></div>
</div>
