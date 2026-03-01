<script lang="ts">
  import { goto } from "$app/navigation";
  import { onMount } from "svelte";

  onMount(() => {
    goto("/james", { replaceState: true });
  });
</script>

<div class="flex items-center justify-center h-screen bg-background">
  <div
    class="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin"
  ></div>
</div>
