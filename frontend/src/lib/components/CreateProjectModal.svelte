<script lang="ts">
  import { fade, scale, slide } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import { planning, type AgentPlan } from '$lib/api';
  import { sessionsStore } from '$lib/stores/sessions';

  let {
    isOpen,
    onClose,
    onLaunch,
  }: {
    isOpen: boolean;
    onClose: () => void;
    /** Called after session creation. Receives session ID, goal, title, and confirmed agents. */
    onLaunch: (sessionId: string, goal: string, agents: AgentPlan[]) => void;
  } = $props();

  // Step: 'prompt' | 'review'
  let step = $state<'prompt' | 'review'>('prompt');
  let prompt = $state('');
  let planning_loading = $state(false);
  let launching = $state(false);
  let planError = $state<string | null>(null);
  let promptInputEl = $state<HTMLTextAreaElement | null>(null);

  // Plan results (editable)
  let title = $state('');
  let agents = $state<AgentPlan[]>([]);

  async function planTeam() {
    if (!prompt.trim()) return;
    planning_loading = true;
    planError = null;
    try {
      const plan = await planning.create(prompt.trim());
      title = plan.title;
      agents = plan.agents;
      step = 'review';
    } catch (e) {
      planError = e instanceof Error ? e.message : 'Failed to generate plan';
    } finally {
      planning_loading = false;
    }
  }

  async function launch() {
    if (agents.length === 0) return;
    launching = true;
    try {
      const s = sessionsStore.create(title.trim() || 'New Project');
      onLaunch(s.id, prompt.trim(), agents);
    } finally {
      launching = false;
    }
  }

  function addAgent() {
    agents = [...agents, { name: '', task: '' }];
  }

  function removeAgent(idx: number) {
    agents = agents.filter((_, i) => i !== idx);
  }

  function updateAgent(idx: number, field: 'name' | 'task', value: string) {
    agents = agents.map((a, i) => i === idx ? { ...a, [field]: value } : a);
  }

  function goBack() {
    step = 'prompt';
    planError = null;
  }

  function reset() {
    step = 'prompt';
    prompt = '';
    title = '';
    agents = [];
    planning_loading = false;
    launching = false;
    planError = null;
  }

  $effect(() => {
    if (!isOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => promptInputEl?.focus());
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

  const canPlan = $derived(prompt.trim().length > 0);
  const canLaunch = $derived(agents.length > 0 && agents.every(a => a.name.trim() && a.task.trim()));
  const busy = $derived(planning_loading || launching);
</script>

{#if isOpen}
  <!-- Backdrop -->
  <div
    transition:fade={{ duration: 220 }}
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm px-4"
    role="presentation"
    onclick={() => { if (!busy) onClose(); }}
  >
    <!-- Card wrapper -->
    <div
      in:scale={{ start: 0.94, duration: 380, easing: quintOut }}
      out:scale={{ start: 0.94, duration: 200 }}
      class="relative w-full max-w-[640px]"
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
            {#if busy}
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
            <h2 class="text-sm font-semibold text-text">
              {step === 'prompt' ? 'New Project' : 'Review Your Team'}
            </h2>
            <p class="text-[11px] text-text-faint mt-0.5">
              {step === 'prompt'
                ? 'Describe what you want to accomplish'
                : 'Edit agents and tasks before launching'}
            </p>
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

        <!-- Step 1: Prompt -->
        {#if step === 'prompt'}
          <div class="p-5 flex flex-col gap-4">
            <div class="flex flex-col gap-1.5">
              <label for="project-prompt" class="text-xs font-medium text-text-muted">What do you want to accomplish?</label>
              <textarea
                id="project-prompt"
                bind:this={promptInputEl}
                bind:value={prompt}
                rows={4}
                disabled={planning_loading}
                placeholder="e.g. Compare prices for AirPods Pro across Amazon, Best Buy, and Walmart"
                class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all resize-none leading-relaxed disabled:opacity-50"
                onkeydown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && canPlan && !planning_loading) planTeam(); }}
              ></textarea>
            </div>

            {#if planError}
              <p class="text-xs text-red-400">{planError}</p>
            {/if}

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onclick={onClose}
                disabled={planning_loading}
                class="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-white/30 transition-all disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={planTeam}
                disabled={!canPlan || planning_loading}
                class="px-5 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2"
              >
                {#if planning_loading}
                  <div class="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"></div>
                  Planning…
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                  Plan Team
                {/if}
              </button>
            </div>
          </div>

        <!-- Step 2: Review -->
        {:else}
          <div class="p-5 flex flex-col gap-4 max-h-[70vh] overflow-y-auto">
            <!-- Title -->
            <div class="flex flex-col gap-1.5">
              <label for="project-title" class="text-xs font-medium text-text-muted">Project Title</label>
              <input
                id="project-title"
                bind:value={title}
                type="text"
                disabled={launching}
                class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all disabled:opacity-50"
              />
            </div>

            <!-- Goal (read-only context) -->
            <div class="flex flex-col gap-1.5">
              <span class="text-xs font-medium text-text-muted">Goal</span>
              <p class="text-sm text-text-faint bg-background/50 rounded-lg px-3 py-2 border border-border/40">{prompt}</p>
            </div>

            <!-- Agent list -->
            <div class="flex flex-col gap-1.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-medium text-text-muted">Agent Team ({agents.length})</span>
                <button
                  type="button"
                  onclick={addAgent}
                  disabled={launching}
                  class="text-xs text-accent hover:underline disabled:opacity-40"
                >
                  + Add agent
                </button>
              </div>

              <div class="flex flex-col gap-2.5">
                {#each agents as agent, idx (idx)}
                  <div class="rounded-lg border border-border bg-background/60 p-3 flex flex-col gap-2 group">
                    <div class="flex items-center gap-2">
                      <div class="w-5 h-5 rounded-full bg-accent/20 text-accent text-[10px] font-bold flex items-center justify-center shrink-0">
                        {idx + 1}
                      </div>
                      <input
                        bind:value={agent.name}
                        oninput={(e) => updateAgent(idx, 'name', e.currentTarget.value)}
                        type="text"
                        placeholder="Agent name"
                        disabled={launching}
                        class="flex-1 px-2 py-1 rounded bg-transparent border border-transparent hover:border-border focus:border-accent/60 text-sm text-text font-medium placeholder:text-text-faint focus:outline-none transition-all disabled:opacity-50"
                      />
                      {#if agents.length > 1}
                        <button
                          type="button"
                          onclick={() => removeAgent(idx)}
                          disabled={launching}
                          class="p-1 rounded text-text-faint hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-0"
                          aria-label="Remove agent"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M18 6 6 18M6 6l12 12"/>
                          </svg>
                        </button>
                      {/if}
                    </div>
                    <textarea
                      bind:value={agent.task}
                      oninput={(e) => updateAgent(idx, 'task', e.currentTarget.value)}
                      rows={2}
                      placeholder="Task description"
                      disabled={launching}
                      class="w-full px-2 py-1.5 rounded bg-transparent border border-transparent hover:border-border focus:border-accent/60 text-xs text-text-muted placeholder:text-text-faint focus:outline-none transition-all resize-none leading-relaxed disabled:opacity-50"
                    ></textarea>
                  </div>
                {/each}
              </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-between pt-1">
              <button
                type="button"
                onclick={goBack}
                disabled={launching}
                class="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-white/30 transition-all disabled:opacity-40"
              >
                Back
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
                  Launch {agents.length} Agent{agents.length !== 1 ? 's' : ''}
                {/if}
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
