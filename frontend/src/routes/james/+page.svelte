<script lang="ts">
  import { PlusIcon } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import { AgentBrowserWindowTile } from "$lib/components/AgentBrowserWindowTile";
  import SpawnAgentModal from "$lib/components/SpawnAgentModal.svelte";

  type Agent = { name: string; status: string };

  let agents = $state<Agent[]>([
    { name: 'James Agent', status: 'Done' },
    { name: 'Kelly Agent', status: 'In-Progress' },
    { name: 'Sam Agent',   status: 'Blocked' },
  ]);

  let spawnModalOpen = $state(false);

  function handleSpawn(name: string, _task: string) {
    agents = [...agents, { name, status: 'In-Progress' }];
  }
</script>

<svelte:head>
  <title>Windows — James</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">
  <header class="relative flex items-center justify-center border-b border-border-subtle bg-surface/50 px-6 py-4">
    <span class="font-semibold text-text">Windows</span>
    <button
      onclick={() => (spawnModalOpen = true)}
      class="absolute right-6 flex items-center justify-center w-8 h-8 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
      aria-label="Spawn new agent"
    >
      <PlusIcon size={18} />
    </button>
  </header>

  <main class="flex-1 p-6">
    <div class="flex flex-wrap gap-6">
      {#each agents as agent (agent.name)}
        <AgentBrowserWindowTile status={agent.status} agentName={agent.name} initialWidth={320} />
      {/each}
    </div>
  </main>

  <FloatingChatWidget onSpawnAgent={() => (spawnModalOpen = true)} />
</div>

<SpawnAgentModal
  isOpen={spawnModalOpen}
  onClose={() => (spawnModalOpen = false)}
  onSpawn={handleSpawn}
/>
