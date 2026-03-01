<script lang="ts">
  import { fade, scale } from 'svelte/transition';
  import { quintOut, backOut } from 'svelte/easing';
  import { goto } from '$app/navigation';
  import { sessionsStore } from '$lib/stores/sessions';

  type Stage = 'input' | 'planning' | 'ready';

  let { isOpen, onClose }: { isOpen: boolean; onClose: () => void } = $props();

  let stage = $state<Stage>('input');
  let projectName = $state('');
  let prompt = $state('');
  let thinkingText = $state('');
  let agentCount = $state(0);
  let launching = $state(false);
  let nameInputEl = $state<HTMLInputElement | null>(null);

  // TODO: Replace with real LLM-generated agent plan.
  // The backend should accept { prompt } and return a streaming thinking
  // response followed by a structured list of agent tasks.
  // See: TODO.md → "Project Creation Modal"
  const MOCK_AGENTS = [
    {
      id: 1,
      name: 'Researcher',
      task: 'Map the competitive landscape and identify key players',
      color: '#8b5cf6',
      bg: 'bg-violet-500/10',
      ring: 'ring-violet-500/20',
    },
    {
      id: 2,
      name: 'Scraper',
      task: 'Extract pricing, features, and plans from each target site',
      color: '#3b82f6',
      bg: 'bg-blue-500/10',
      ring: 'ring-blue-500/20',
    },
    {
      id: 3,
      name: 'Analyst',
      task: 'Read user reviews and surface key sentiment signals',
      color: '#f59e0b',
      bg: 'bg-amber-500/10',
      ring: 'ring-amber-500/20',
    },
    {
      id: 4,
      name: 'Compiler',
      task: 'Synthesise all findings into a structured, actionable report',
      color: '#10b981',
      bg: 'bg-emerald-500/10',
      ring: 'ring-emerald-500/20',
    },
  ] as const;

  // TODO: Replace with real LLM streaming output. See: TODO.md
  const MOCK_THINKING = `Decomposing your goal into parallelisable workstreams...

→ Identifying which tasks require live web browsing
→ Grouping related subtasks to minimise agent handoffs
→ Assigning clear success criteria to each workstream

Determining optimal agent count and role boundaries...`;

  async function startPlanning() {
    if (!canPlan) return;
    stage = 'planning';
    thinkingText = '';
    agentCount = 0;

    // Stream thinking text character by character
    for (let i = 0; i < MOCK_THINKING.length; i++) {
      await new Promise<void>(r => setTimeout(r, 11));
      thinkingText = MOCK_THINKING.slice(0, i + 1);
    }

    await new Promise<void>(r => setTimeout(r, 480));

    // Spawn agent cards one by one
    for (let i = 0; i < MOCK_AGENTS.length; i++) {
      await new Promise<void>(r => setTimeout(r, 300));
      agentCount = i + 1;
    }

    await new Promise<void>(r => setTimeout(r, 320));
    stage = 'ready';
  }

  async function launch() {
    launching = true;
    try {
      // TODO: Also dispatch rewritten prompt as first message to the session.
      // See: TODO.md → "Project Creation Modal"
      const s = await sessionsStore.create(projectName.trim() || 'New Project');
      onClose();
      goto(`/chat/${s.id}`);
    } finally {
      launching = false;
    }
  }

  function editPrompt() {
    stage = 'input';
    thinkingText = '';
    agentCount = 0;
  }

  function reset() {
    stage = 'input';
    projectName = '';
    prompt = '';
    thinkingText = '';
    agentCount = 0;
    launching = false;
  }

  $effect(() => {
    if (!isOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && stage === 'input') onClose();
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

  const canPlan = $derived(projectName.trim().length > 0 && prompt.trim().length > 0);
</script>

{#if isOpen}
  <!-- Backdrop — only dismissable during input stage -->
  <div
    transition:fade={{ duration: 220 }}
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm px-4"
    role="presentation"
    onclick={() => { if (stage === 'input') onClose(); }}
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
        onkeydown={(e) => { if (e.key === 'Escape' && stage === 'input') onClose(); }}
      >
        <!-- Header -->
        <div class="flex items-center gap-3 px-5 pt-5 pb-4">
          <div class="w-9 h-9 rounded-xl bg-accent/15 flex items-center justify-center shrink-0">
            {#if stage === 'planning'}
              <!-- Conic spinner (matches AgentTileStatusBar) -->
              <div
                class="w-5 h-5 rounded-full animate-spin [animation-duration:1.2s]"
                style="background: conic-gradient(from 0deg, transparent 0%, #6366f1 70%, transparent 100%)"
              ></div>
            {:else if stage === 'ready'}
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="text-accent">
                <path d="M20 6 9 17l-5-5"/>
              </svg>
            {:else}
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
            {/if}
          </div>

          <div class="flex-1 min-w-0">
            {#if stage === 'input'}
              <h2 class="text-sm font-semibold text-text">New Project</h2>
              <p class="text-[11px] text-text-faint mt-0.5">Name your project and describe your goal</p>
            {:else if stage === 'planning'}
              <h2 class="text-sm font-semibold text-text">Planning your project…</h2>
              <p class="text-[11px] text-text-faint mt-0.5">Decomposing into parallel agent workstreams</p>
            {:else}
              <h2 class="text-sm font-semibold text-text">Ready to launch</h2>
              <p class="text-[11px] text-text-faint mt-0.5">{MOCK_AGENTS.length} agents configured · review and confirm</p>
            {/if}
          </div>

          {#if stage === 'input'}
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
          {/if}
        </div>

        <div class="h-px bg-border/60 mx-5"></div>

        <!-- ── Stage: Input ── -->
        {#if stage === 'input'}
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
                class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all"
              />
            </div>

            <div class="flex flex-col gap-1.5">
              <label for="project-prompt" class="text-xs font-medium text-text-muted">What do you want to accomplish?</label>
              <textarea
                id="project-prompt"
                bind:value={prompt}
                rows={4}
                placeholder="Describe your goal in plain language. AI will break it down into agent tasks…"
                class="w-full px-3 py-2 rounded-lg bg-background border border-border text-sm text-text placeholder:text-text-faint focus:outline-none focus:ring-2 focus:ring-accent/30 focus:border-accent/60 transition-all resize-none leading-relaxed"
              ></textarea>
            </div>

            <div class="flex items-center justify-end gap-2 pt-1">
              <button
                type="button"
                onclick={onClose}
                class="px-4 py-2 rounded-lg text-sm text-text-muted hover:text-text hover:bg-white/30 transition-all"
              >
                Cancel
              </button>
              <button
                type="button"
                onclick={startPlanning}
                disabled={!canPlan}
                class="px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9.663 17h4.673M12 3v1m6.364 1.636-.707.707M21 12h-1M4 12H3m3.343-5.657-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                </svg>
                Analyse & Plan
              </button>
            </div>
          </div>

        <!-- ── Stage: Planning ── -->
        {:else if stage === 'planning'}
          <div class="p-5 flex flex-col gap-4">
            <!-- Streaming thinking block -->
            <div class="rounded-xl bg-surface-hover border border-border-subtle px-4 py-3 font-mono text-[11px] text-text-muted leading-relaxed min-h-[96px] whitespace-pre-wrap">
              {thinkingText}<span class="inline-block w-px h-3 bg-accent/70 animate-pulse ml-px align-middle"></span>
            </div>

            <!-- Agent cards spawning in -->
            {#if agentCount > 0}
              <div class="flex flex-col gap-2" in:fade={{ duration: 160 }}>
                <p class="text-[10px] font-medium text-text-faint uppercase tracking-widest">Spawning agents</p>
                <div class="grid grid-cols-2 gap-2">
                  {#each MOCK_AGENTS.slice(0, agentCount) as agent (agent.id)}
                    <div
                      in:scale={{ start: 0.65, duration: 420, easing: backOut }}
                      class="flex items-start gap-2.5 rounded-xl border border-border-subtle p-3 {agent.bg} ring-1 {agent.ring}"
                    >
                      <span
                        class="w-2 h-2 rounded-full shrink-0 mt-[3px] animate-pulse"
                        style="background-color: {agent.color}"
                      ></span>
                      <div class="min-w-0">
                        <p class="text-xs font-semibold text-text">{agent.name}</p>
                        <p class="text-[10px] text-text-muted leading-snug mt-0.5">{agent.task}</p>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>

        <!-- ── Stage: Ready ── -->
        {:else}
          <div class="p-5 flex flex-col gap-4" in:fade={{ duration: 200 }}>
            <!-- Rewritten prompt preview -->
            <div class="rounded-xl bg-surface-hover border border-border-subtle px-4 py-3">
              <p class="text-[10px] font-medium text-text-faint uppercase tracking-widest mb-1.5">Your goal</p>
              <p class="text-xs text-text-muted leading-relaxed">{prompt}</p>
            </div>

            <!-- Agent team -->
            <div>
              <p class="text-[10px] font-medium text-text-faint uppercase tracking-widest mb-2">
                Agent team · {MOCK_AGENTS.length} agents
              </p>
              <div class="grid grid-cols-2 gap-2">
                {#each MOCK_AGENTS as agent (agent.id)}
                  <div class="flex items-start gap-2.5 rounded-xl border border-border-subtle p-3 {agent.bg} ring-1 {agent.ring}">
                    <span
                      class="w-2 h-2 rounded-full shrink-0 mt-[3px]"
                      style="background-color: {agent.color}"
                    ></span>
                    <div class="min-w-0">
                      <p class="text-xs font-semibold text-text">{agent.name}</p>
                      <p class="text-[10px] text-text-muted leading-snug mt-0.5">{agent.task}</p>
                    </div>
                  </div>
                {/each}
              </div>
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-between pt-1 border-t border-border-subtle/60">
              <button
                type="button"
                onclick={editPrompt}
                class="text-sm text-text-faint hover:text-text-muted transition-colors flex items-center gap-1.5"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                Edit prompt
              </button>
              <button
                type="button"
                onclick={launch}
                disabled={launching}
                class="px-5 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] disabled:opacity-60 transition-all flex items-center gap-2"
              >
                {#if launching}
                  <div class="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin"></div>
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                {/if}
                Create Project
              </button>
            </div>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
