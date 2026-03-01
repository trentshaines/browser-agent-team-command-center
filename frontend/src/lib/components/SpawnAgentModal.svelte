<script lang="ts">
  import { fade, scale } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';

  let {
    isOpen,
    onClose,
    onSpawn,
  }: {
    isOpen: boolean;
    onClose: () => void;
    onSpawn: (name: string, task: string) => void;
  } = $props();

  let agentName = $state('');
  let task = $state('');
  let nameInputEl = $state<HTMLInputElement | null>(null);

  function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    const name = agentName.trim();
    const taskStr = task.trim();
    if (!name || !taskStr) return;
    onSpawn(name, taskStr);
    agentName = '';
    task = '';
    onClose();
  }

  $effect(() => {
    if (!isOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => nameInputEl?.focus());
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
    };
  });

  const canSubmit = $derived(agentName.trim().length > 0 && task.trim().length > 0);
</script>

{#if isOpen}
  <!-- Backdrop -->
  <div
    transition:fade={{ duration: 200 }}
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm"
    role="presentation"
    onclick={onClose}
  >
    <!-- Card wrapper (scale in/out) -->
    <div
      in:scale={{ start: 0.94, duration: 360, easing: quintOut }}
      out:scale={{ start: 0.94, duration: 180 }}
      class="relative w-[480px] max-w-[calc(100vw-2rem)]"
    >
      <!-- Glass halo — matches AgentExpandedModal -->
      <div
        class="absolute -inset-2 rounded-[1.5rem] backdrop-blur-xl bg-white/20 border border-white/50 shadow-[0_24px_80px_rgba(0,0,0,0.22),0_8px_24px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.55)]"
        aria-hidden="true"
      ></div>

      <!-- Modal panel -->
      <div
        class="relative rounded-2xl overflow-hidden bg-surface/85 backdrop-blur-2xl border border-white/25 shadow-[0_8px_32px_rgba(0,0,0,0.14)]"
        role="dialog"
        aria-modal="true"
        aria-label="Spawn new agent"
        tabindex="-1"
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}
      >
        <!-- Header -->
        <div class="flex items-center gap-3 px-5 pt-5 pb-4">
          <!-- Icon badge -->
          <div class="w-9 h-9 rounded-xl bg-accent/15 flex items-center justify-center shrink-0">
            <!-- Bot icon -->
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent">
              <path d="M12 8V4H8"/>
              <rect width="16" height="12" x="4" y="8" rx="2"/>
              <path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <h2 class="text-sm font-semibold text-text leading-tight">Spawn Agent</h2>
            <p class="text-[11px] text-text-faint mt-0.5">Add a new browser agent to your team</p>
          </div>
          <!-- Close button -->
          <button
            type="button"
            onclick={onClose}
            class="p-1.5 rounded-lg text-text-faint hover:text-text hover:bg-white/30 transition-all"
            aria-label="Close"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <!-- Divider -->
        <div class="h-px bg-border/60 mx-5"></div>

        <!-- Form -->
        <form onsubmit={handleSubmit} class="p-5 flex flex-col gap-4">
          <!-- Agent Name -->
          <div class="flex flex-col gap-1.5">
            <label for="spawn-agent-name" class="text-xs font-medium text-text-muted">
              Agent Name
            </label>
            <input
              id="spawn-agent-name"
              bind:this={nameInputEl}
              bind:value={agentName}
              type="text"
              placeholder="e.g. Research Scout, Data Collector"
              autocomplete="off"
              class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all"
            />
          </div>

          <!-- Task -->
          <div class="flex flex-col gap-1.5">
            <label for="spawn-agent-task" class="text-xs font-medium text-text-muted">
              Task
            </label>
            <textarea
              id="spawn-agent-task"
              bind:value={task}
              rows={4}
              placeholder="Describe what this agent should do…"
              class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all resize-none leading-relaxed"
            ></textarea>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onclick={onClose}
              class="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-white/30 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              class="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-1.5"
            >
              <!-- Arrow right icon -->
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
              Spawn
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
{/if}
