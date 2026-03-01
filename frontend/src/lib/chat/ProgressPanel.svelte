<script lang="ts">
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';

  let {
    agentRuns = [],
    streaming = false,
    orchestratorText = '',
  }: {
    agentRuns?: AgentRun[];
    streaming?: boolean;
    orchestratorText?: string;
  } = $props();

  // Re-tick every second so elapsed labels update
  let now = $state(Date.now());
  $effect(() => {
    const id = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(id);
  });

  // Track the moment each agent first appeared (local only)
  const startTimes = new Map<string, number>();
  $effect(() => {
    for (const run of agentRuns) {
      if (!startTimes.has(run.id)) startTimes.set(run.id, Date.now());
    }
  });

  function elapsed(agentId: string): string {
    void now; // depend on tick
    const t = startTimes.get(agentId);
    if (!t) return '';
    const s = Math.floor((Date.now() - t) / 1000);
    if (s < 60) return `${s}s`;
    return `${Math.floor(s / 60)}m ${s % 60}s`;
  }

  function hostOf(run: AgentRun): string | null {
    const url = run.steps.at(-1)?.url;
    if (!url) return null;
    try { return new URL(url).hostname.replace(/^www\./, ''); }
    catch { return url.replace(/^https?:\/\//, '').split('/')[0]; }
  }

  const runningCount = $derived(agentRuns.filter(r => r.status === 'running').length);
  const doneCount    = $derived(agentRuns.filter(r => r.status === 'complete').length);
  const errorCount   = $derived(agentRuns.filter(r => r.status === 'error').length);

  // Orchestrator summary line
  const orchestratorStatus = $derived(() => {
    if (streaming && runningCount === 0 && agentRuns.length === 0) return 'Planning…';
    if (runningCount > 0) return `Directing ${runningCount} agent${runningCount !== 1 ? 's' : ''}`;
    if (agentRuns.length > 0 && runningCount === 0) return 'Agents complete';
    if (streaming) return 'Responding…';
    return 'Idle';
  });

  // Truncate orchestrator text at a word boundary
  const orchestratorPreview = $derived(() => {
    const t = orchestratorText.trim();
    if (!t || t.length <= 160) return t;
    return t.slice(0, 160).replace(/\s\S*$/, '') + '…';
  });

  const hasActivity = $derived(agentRuns.length > 0 || streaming || orchestratorText.trim().length > 0);
</script>

<div class="flex-1 min-h-0 flex flex-col overflow-hidden">

  <!-- Orchestrator section -->
  <div class="shrink-0 px-4 pt-3 pb-2.5 border-b border-border-subtle/50">
    <div class="flex items-center gap-2 mb-1.5">
      <!-- Bot icon -->
      <div class="w-5 h-5 rounded-md bg-accent/10 flex items-center justify-center shrink-0">
        <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-accent">
          <path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/>
          <path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>
        </svg>
      </div>
      <span class="text-[11px] font-semibold text-text-muted uppercase tracking-wide">Orchestrator</span>
      <!-- Status pill -->
      <span class="ml-auto flex items-center gap-1.5 text-[10px] font-medium {streaming ? 'text-accent' : agentRuns.length > 0 && runningCount === 0 ? 'text-status-emerald' : 'text-text-faint'}">
        {#if streaming}
          <span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0"></span>
        {:else if runningCount > 0}
          <span class="w-1.5 h-1.5 rounded-full bg-accent animate-pulse shrink-0"></span>
        {:else if agentRuns.length > 0}
          <span class="w-1.5 h-1.5 rounded-full bg-status-emerald shrink-0"></span>
        {/if}
        {orchestratorStatus()}
      </span>
    </div>

    {#if orchestratorPreview()}
      <p class="text-[11px] text-text-muted leading-relaxed line-clamp-3">
        {orchestratorPreview()}
        {#if streaming}<span class="inline-block w-0.5 h-3 bg-text-muted/60 align-middle animate-pulse ml-0.5"></span>{/if}
      </p>
    {:else if streaming}
      <div class="flex items-center gap-1.5 text-[11px] text-text-faint italic">
        <span class="w-1 h-1 rounded-full bg-text-faint/50 animate-bounce" style="animation-delay:0ms"></span>
        <span class="w-1 h-1 rounded-full bg-text-faint/50 animate-bounce" style="animation-delay:150ms"></span>
        <span class="w-1 h-1 rounded-full bg-text-faint/50 animate-bounce" style="animation-delay:300ms"></span>
      </div>
    {/if}
  </div>

  {#if agentRuns.length > 0}
    <!-- Summary bar -->
    <div class="shrink-0 px-4 py-2 border-b border-border-subtle/50 flex items-center gap-3">
      {#each [
        { status: 'running',  label: 'Running', dot: 'bg-accent animate-pulse', text: 'text-accent', count: runningCount },
        { status: 'complete', label: 'Done',    dot: 'bg-status-emerald',              text: 'text-status-emerald', count: doneCount },
        { status: 'error',    label: 'Failed',  dot: 'bg-danger',                 text: 'text-danger',    count: errorCount },
      ] as g}
        {#if g.count > 0}
          <div class="flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full {g.dot} shrink-0"></span>
            <span class="text-xs font-semibold {g.text}">{g.count}</span>
            <span class="text-xs text-text-faint">{g.label}</span>
          </div>
          <span class="text-border-subtle text-xs last:hidden">·</span>
        {/if}
      {/each}
      <span class="ml-auto text-[10px] text-text-faint">{agentRuns.length} total</span>
    </div>

    <!-- Agent list -->
    <div class="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-1.5">
      {#each agentRuns as run (run.id)}
        {@const host = hostOf(run)}
        {@const latestAction = run.steps.at(-1)?.action}
        <div class="rounded-xl border border-border-subtle bg-surface overflow-hidden">
          <div class="flex items-start gap-2.5 px-3 py-2.5">
            <!-- Status dot -->
            <div class="shrink-0 mt-1">
              {#if run.status === 'running'}
                <span class="block w-1.5 h-1.5 rounded-full bg-accent animate-pulse"></span>
              {:else if run.status === 'complete'}
                <span class="block w-1.5 h-1.5 rounded-full bg-status-emerald"></span>
              {:else}
                <span class="block w-1.5 h-1.5 rounded-full bg-danger"></span>
              {/if}
            </div>

            <div class="flex-1 min-w-0">
              <!-- Name + elapsed -->
              <div class="flex items-center gap-1.5 mb-0.5">
                <span class="text-xs font-medium text-text truncate">{run.name ?? 'Agent'}</span>
                {#if elapsed(run.id)}
                  <span class="text-[10px] text-text-faint shrink-0">{elapsed(run.id)}</span>
                {/if}
              </div>

              <!-- Task -->
              <p class="text-[11px] text-text-muted leading-snug line-clamp-2 mb-1">{run.task}</p>

              {#if run.status === 'running'}
                <!-- Current URL / action -->
                {#if host || latestAction}
                  <div class="flex items-center gap-1 mb-1.5 text-[10px] text-text-faint">
                    {#if host}
                      <svg xmlns="http://www.w3.org/2000/svg" width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="shrink-0"><circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/><path d="M2 12h20"/></svg>
                      <span class="truncate">{host}</span>
                    {/if}
                    {#if latestAction}
                      <span class="shrink-0 opacity-60">· {latestAction}</span>
                    {/if}
                  </div>
                {/if}
                <!-- Indeterminate progress bar -->
                <div class="flex items-center gap-2">
                  <div class="flex-1 h-1 rounded-full bg-surface-hover overflow-hidden">
                    <div class="h-full w-1/3 rounded-full bg-accent origin-left animate-[progress-shimmer_1.8s_ease-in-out_infinite]"></div>
                  </div>
                  <span class="text-[10px] text-text-faint shrink-0">
                    step {run.steps.length}
                  </span>
                </div>
              {:else if run.status === 'complete'}
                <div class="text-[10px] text-text-faint">{run.steps.length} steps · done</div>
              {:else}
                <div class="text-[10px] text-danger">{run.steps.length} steps · failed</div>
              {/if}
            </div>
          </div>

          <!-- Result / error footer -->
          {#if run.result}
            <div class="px-3 py-1.5 bg-[var(--status-emerald-bg)] border-t border-[var(--status-emerald-border)] text-[10px] text-status-emerald leading-snug">
              <span class="mr-1 text-status-emerald">↳</span>{run.result}
            </div>
          {:else if run.steps.at(-1)?.error}
            <div class="px-3 py-1.5 bg-[var(--status-danger-bg)] border-t border-[var(--status-danger-border)] text-[10px] text-danger leading-snug">
              <span class="mr-1">⚠</span>{run.steps.at(-1)?.error}
            </div>
          {/if}
        </div>
      {/each}
    </div>

  {:else if !hasActivity}
    <!-- Empty state -->
    <div class="flex-1 flex flex-col items-center justify-center gap-2 text-center px-6">
      <div class="w-8 h-8 rounded-xl bg-surface-hover flex items-center justify-center">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-text-faint">
          <path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/>
          <path d="M2 14h2M20 14h2M15 13v2M9 13v2"/>
        </svg>
      </div>
      <p class="text-xs text-text-faint">Agent activity will appear here</p>
    </div>
  {:else}
    <div class="flex-1 flex items-center justify-center">
      <p class="text-xs text-text-faint">Waiting for agents…</p>
    </div>
  {/if}
</div>

<style>
  @keyframes progress-shimmer {
    0%   { transform: translateX(-100%); }
    50%  { transform: translateX(200%); }
    100% { transform: translateX(200%); }
  }
</style>
