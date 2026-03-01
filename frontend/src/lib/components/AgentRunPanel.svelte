<script lang="ts">
  export interface AgentStep {
    step: number;
    url?: string;
    action_type?: string;
    thought?: string;
    evaluation?: string;
    success?: boolean;
    extracted_content?: string;
    error?: string;
  }

  export interface AgentRun {
    id: string;
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
      <div class="border border-[#242424] rounded-xl overflow-hidden bg-[#111]">
        <!-- Header -->
        <button
          onclick={() => toggle(run.id, run)}
          class="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-[#181818] transition-colors"
        >
          {#if run.status === 'running'}
            <span class="w-1.5 h-1.5 rounded-full bg-[#7c6ff7] animate-pulse shrink-0"></span>
          {:else if run.status === 'complete'}
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0"></span>
          {:else}
            <span class="w-1.5 h-1.5 rounded-full bg-red-500 shrink-0"></span>
          {/if}

          <span class="text-xs text-[#888] flex-1 truncate min-w-0">
            <span class="text-[#555] mr-1">browser:</span>{run.task}
          </span>

          <span class="text-[10px] text-[#444] shrink-0 ml-2">
            {run.steps.length} step{run.steps.length !== 1 ? 's' : ''}
            {#if run.status === 'complete'} · done{:else if run.status === 'error'} · failed{/if}
          </span>
          <span class="text-[10px] text-[#444] ml-1">{isExpanded(run) ? '▲' : '▼'}</span>
        </button>

        <!-- Steps -->
        {#if isExpanded(run)}
          <div class="border-t border-[#1c1c1c]">
            {#if run.steps.length === 0}
              <div class="px-3 py-2 text-[11px] text-[#555] flex items-center gap-2">
                <span class="inline-block animate-spin">↻</span> Starting browser…
              </div>
            {:else}
              {#each run.steps as step (step.step)}
                <div class="px-3 py-1.5 border-b border-[#1a1a1a] last:border-0">
                  <div class="flex items-center gap-2 text-[11px]">
                    <span class="text-[#393939] w-4 shrink-0 text-right">{step.step}</span>
                    {#if step.action_type}
                      <span class="bg-[#1e1e1e] px-1.5 py-0.5 rounded text-[#666] font-mono shrink-0 text-[10px]">{step.action_type}</span>
                    {/if}
                    {#if step.url}
                      <span class="text-[#5a5af0] truncate min-w-0 text-[10px]">{step.url}</span>
                    {/if}
                    {#if step.success === false}
                      <span class="text-red-500 shrink-0 ml-auto">✗</span>
                    {:else if step.success}
                      <span class="text-emerald-500 shrink-0 ml-auto">✓</span>
                    {/if}
                  </div>
                  {#if step.thought}
                    <p class="text-[11px] text-[#555] pl-6 mt-0.5 leading-relaxed">{step.thought}</p>
                  {/if}
                </div>
              {/each}
            {/if}

            {#if run.result}
              <div class="px-3 py-2 bg-[#0e1a12] border-t border-[#1e2e22] text-[11px]">
                <span class="text-[#4a7a5a] mr-1">↳</span>
                <span class="text-[#7ab88a]">{run.result}</span>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/if}
