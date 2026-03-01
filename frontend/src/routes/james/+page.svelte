<script lang="ts">
  import { PlusIcon } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import { AgentBrowserWindowTile } from "$lib/components/AgentBrowserWindowTile";

</script>

<svelte:head>
  <title>Windows — James</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">
  <header class="relative flex items-center justify-center border-b border-border-subtle bg-surface/50 px-6 py-4">
    <span class="font-semibold text-text">Windows</span>
    <button
      class="absolute right-6 flex items-center justify-center w-8 h-8 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
      aria-label="Add"
    >
      <PlusIcon size={18} />
    </button>
  </header>

  <main class="flex-1 p-6">
    <div class="flex flex-wrap gap-6">
      <AgentBrowserWindowTile status="Done" agentName="James Agent" initialWidth={320} />
      <AgentBrowserWindowTile status="In-Progress" agentName="Kelly Agent" initialWidth={320} />
      <AgentBrowserWindowTile status="Blocked" agentName="Sam Agent" initialWidth={320} />
    </div>
  </main>

  <FloatingChatWidget />
</div>
