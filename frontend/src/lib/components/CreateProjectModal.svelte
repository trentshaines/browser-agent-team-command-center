<script lang="ts">
  import { fade, scale } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import { sessions as sessionsApi } from '$lib/api';

  let {
    isOpen,
    onClose,
    onLaunch,
  }: {
    isOpen: boolean;
    onClose: () => void;
    /** Called after session creation instead of navigating. Receives session ID and goal prompt. */
    onLaunch: (sessionId: string, goal: string) => void;
  } = $props();

  let projectName = $state('');
  let prompt = $state('');
  let launching = $state(false);
  let nameInputEl = $state<HTMLInputElement | null>(null);

  async function launch() {
    if (!canLaunch) return;
    launching = true;
    try {
      const s = await sessionsApi.create(projectName.trim() || 'New Project');
      onLaunch(s.id, prompt.trim());
    } finally {
      launching = false;
    }
  }

  function reset() {
    projectName = '';
    prompt = '';
    launching = false;
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

  $effect(() => {
    if (!isOpen) {
      const t = setTimeout(reset, 320);
      return () => clearTimeout(t);
    }
  });

  const canLaunch = $derived(projectName.trim().length > 0 && prompt.trim().length > 0);
</script>

{#if isOpen}
  <!-- Backdrop -->
  <div
    transition:fade={{ duration: 220 }}
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm px-4"
    role="presentation"
    onclick={() => { if (!launching) onClose(); }}
  >
    <!-- Card wrapper -->
    <div
      in:scale={{ start: 0.94, duration: 380, easing: quintOut }}
      out:scale={{ start: 0.94, duration: 200 }}
      class="relative w-full max-w-[560px]"
      onclick={(e) => e.stopPropagation()}
    >
      <!-- Glass halo -->
      <div
        class="absolute -inset-2 rounded-[1.5rem] backdrop-blur-xl bg-white/20 border border-white/50 shadow-[0_24px_80px_rgba(0,0,0,0.22),0_8px_24px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.55)]"
        aria-hidden="true"
      ></div>

      <!-- Modal panel -->
      <div
        class="relative rounded-2xl overflow-hidden bg-surface/95 backdrop-blur-2xl border border-white/25 shadow-[0_8px_32px_rgba(0,0,0,0.14)]"
        role="dialog"
        aria-modal="true"
        aria-label="Create new project"
        tabindex="-1"
        onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}
      >
        <!-- Header -->
        <div class="flex items-center gap-3 px-5 pt-5 pb-4">
          <div class="w-9 h-9 rounded-xl bg-accent/15 flex items-center justify-center shrink-0">
            {#if launching}
              <div
                class="w-5 h-5 rounded-full animate-spin [animation-duration:1.2s]"
                style="background: conic-gradient(from 0deg, transparent 0%, #6366f1 70%, transparent 100%)"
              ></div>
            {:else}
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            {/if}
          </div>

          <div class="flex-1 min-w-0">
            <h2 class="text-sm font-semibold text-text">New Project</h2>
            <p class="text-[11px] text-text-faint mt-0.5">Name your project and describe your goal</p>
          </div>

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

        <div class="h-px bg-border/60 mx-5"></div>

        <div class="p-5 flex flex-col gap-4">
            <div class="flex flex-col gap-1.5">
              <label for="project-name" class="text-xs font-medium text-text-muted">Project Name</label>
              <input
                id="project-name"
                bind:this={nameInputEl}
                bind:value={projectName}
                type="text"
                placeholder="e.g. Competitor Research Q1"
                autocomplete="off"
                disabled={launching}
                class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all disabled:opacity-50"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label for="project-prompt" class="text-xs font-medium text-text-muted">What do you want to accomplish?</label>
              <textarea
                id="project-prompt"
                bind:value={prompt}
                rows={4}
                disabled={launching}
                placeholder="Describe your goal in plain language. The orchestrator will spawn browser agents as needed…"
                class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all resize-none leading-relaxed disabled:opacity-50"
              ></textarea>
            </div>

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onclick={onClose}
                disabled={launching}
                class="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-white/30 transition-all disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={launch}
                disabled={!canLaunch || launching}
                class="px-5 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2"
              >
                {#if launching}
                  <div class="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"></div>
                  Launching…
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                  Launch
                {/if}
              </button>
            </div>
          </div>
      </div>
    </div>
  </div>
{/if}
