<script lang="ts">
  export interface AgentStep {
    step: number;
    url?: string | null;
    action_type?: string;
    thought?: string;
    evaluation?: string;
    success?: boolean;
    extracted_content?: string;
    error?: string;
  }

  export interface AgentRun {
    id: string;
    name?: string;
    task: string;
    status: 'running' | 'complete' | 'error';
    steps: AgentStep[];
    result?: string | null;
    total_steps?: number;
  }

  let { runs }: { runs: AgentRun[] } = $props();

  // Manual expand overrides. Default: running=expanded, done=collapsed.
  let overrides = $state<Map<string, boolean>>(new Map());

  function isExpanded(run: AgentRun): boolean {
    if (overrides.has(run.id)) return overrides.get(run.id)!;
    return run.status === 'running';
  }

  function toggle(id: string, run: AgentRun) {
    overrides = new Map([...overrides, [id, !isExpanded(run)]]);
  }
</script>

{#if runs.length > 0}
  <div class="my-2 space-y-1.5">
    {#each runs as run (run.id)}
      <div class="border border-border-subtle rounded-xl overflow-hidden bg-surface">
        <!-- Header -->
        <button
          onclick={() => toggle(run.id, run)}
          class="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-surface-hover transition-colors"
        >
          {#if run.status === 'running'}
            <span class="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse shrink-0"></span>
          {:else if run.status === 'complete'}
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
          {:else}
            <span class="w-1.5 h-1.5 rounded-full bg-danger shrink-0"></span>
          {/if}

          <span class="text-xs text-text-muted flex-1 truncate min-w-0">
            <span class="text-text-faint mr-1.5 font-medium">{run.name}:</span><span class="text-text-faint">{run.task}</span>
          </span>

          <span class="text-[10px] text-text-faint shrink-0 ml-2">
            {run.steps.length} step{run.steps.length !== 1 ? 's' : ''}
            {#if run.status === 'complete'} · done{:else if run.status === 'error'} · failed{/if}
          </span>
          <span class="text-[10px] text-text-faint opacity-40 ml-1">{isExpanded(run) ? '▲' : '▼'}</span>
        </button>

        <!-- Steps -->
        {#if isExpanded(run)}
          <div class="border-t border-border-subtle">
            {#if run.steps.length === 0}
              <div class="px-3 py-2 text-[11px] text-text-faint flex items-center gap-2">
                <span class="inline-block animate-spin">↻</span> Starting browser…
              </div>
            {:else}
              {#each run.steps as step (step.step)}
                <div class="px-3 py-1.5 border-b border-border-subtle last:border-0">
                  <div class="flex items-center gap-2 text-[11px]">
                    <span class="text-text-faint w-4 shrink-0 text-right opacity-50">{step.step}</span>
                    {#if step.action_type}
                      <span class="bg-surface-hover px-1.5 py-0.5 rounded text-text-muted font-mono shrink-0 text-[10px] border border-border-subtle">{step.action_type}</span>
                    {/if}
                    {#if step.url}
                      <span class="text-accent truncate min-w-0 text-[10px]">{step.url}</span>
                    {/if}
                    {#if step.success === false}
                      <span class="text-danger shrink-0 ml-auto text-[10px]">✗</span>
                    {:else if step.success}
                      <span class="text-emerald-600 shrink-0 ml-auto text-[10px]">✓</span>
                    {/if}
                  </div>
                  {#if step.thought}
                    <p class="text-[11px] text-text-faint pl-6 mt-0.5 leading-relaxed">{step.thought}</p>
                  {/if}
                </div>
              {/each}
            {/if}

            {#if run.result}
              <div class="px-3 py-2 bg-emerald-50 border-t border-emerald-100 text-[11px]">
                <span class="text-emerald-600 mr-1">↳</span>
                <span class="text-emerald-700">{run.result}</span>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
