<script lang="ts">
  interface MockAgent {
    id: string;
    name: string;
    task: string;
    status: 'running' | 'complete' | 'error';
    steps: number;
    totalSteps?: number;
    result?: string;
    error?: string;
    startedAt: Date;
  }

  const mockAgents: MockAgent[] = [
    {
      id: '1',
      name: 'Researcher',
      task: 'Find top 5 competitors for AI writing tools',
      status: 'running',
      steps: 7,
      totalSteps: 12,
      startedAt: new Date(Date.now() - 1000 * 60 * 3),
    },
    {
      id: '2',
      name: 'Scraper',
      task: 'Extract pricing data from g2.com',
      status: 'running',
      steps: 3,
      totalSteps: 8,
      startedAt: new Date(Date.now() - 1000 * 60 * 1),
    },
    {
      id: '3',
      name: 'Analyst',
      task: 'Summarise Reddit threads about Notion AI',
      status: 'complete',
      steps: 9,
      result: 'Found 14 relevant threads. Users praise speed but flag limited offline support.',
      startedAt: new Date(Date.now() - 1000 * 60 * 8),
    },
    {
      id: '4',
      name: 'Navigator',
      task: 'Pull feature changelog from Jasper AI docs',
      status: 'complete',
      steps: 5,
      result: 'Extracted 23 changelog entries from Q4 2024.',
      startedAt: new Date(Date.now() - 1000 * 60 * 12),
    },
    {
      id: '5',
      name: 'FormFiller',
      task: 'Sign up for Copy.ai trial account',
      status: 'error',
      steps: 4,
      error: 'CAPTCHA blocked submission on step 4.',
      startedAt: new Date(Date.now() - 1000 * 60 * 5),
    },
  ];

  function elapsedLabel(startedAt: Date): string {
    const s = Math.floor((Date.now() - startedAt.getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ago`;
  }
</script>

<div class="flex-1 min-h-0 flex flex-col overflow-hidden">
  <!-- Summary bar -->
  <div class="shrink-0 px-4 py-2.5 border-b border-border-subtle/50 flex items-center gap-3">
    {#each [
      { status: 'running', label: 'Running', color: 'bg-violet-400', textColor: 'text-violet-600' },
      { status: 'complete', label: 'Done', color: 'bg-emerald-500', textColor: 'text-emerald-600' },
      { status: 'error', label: 'Failed', color: 'bg-red-400', textColor: 'text-red-500' },
    ] as group}
      {@const count = mockAgents.filter(a => a.status === group.status).length}
      <div class="flex items-center gap-1.5">
        <span class="w-1.5 h-1.5 rounded-full {group.color} {group.status === 'running' ? 'animate-pulse' : ''}"></span>
        <span class="text-xs font-semibold {group.textColor}">{count}</span>
        <span class="text-xs text-text-faint">{group.label}</span>
      </div>
      {#if group.status !== 'error'}<span class="text-border-subtle text-xs">·</span>{/if}
    {/each}
    <span class="ml-auto text-[10px] text-text-faint">mock data</span>
  </div>

  <!-- Agent list -->
  <div class="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-1.5">
    {#each mockAgents as agent (agent.id)}
      <div class="rounded-xl border border-border-subtle bg-surface overflow-hidden">
        <div class="flex items-start gap-2.5 px-3 py-2.5">
          <div class="shrink-0 mt-0.5">
            {#if agent.status === 'running'}
              <span class="block w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse mt-0.5"></span>
            {:else if agent.status === 'complete'}
              <span class="block w-1.5 h-1.5 rounded-full bg-emerald-500 mt-0.5"></span>
            {:else}
              <span class="block w-1.5 h-1.5 rounded-full bg-red-400 mt-0.5"></span>
            {/if}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5 mb-0.5">
              <span class="text-xs font-medium text-text">{agent.name}</span>
              <span class="text-[10px] text-text-faint">{elapsedLabel(agent.startedAt)}</span>
            </div>
            <p class="text-[11px] text-text-muted leading-snug truncate">{agent.task}</p>
            {#if agent.status === 'running' && agent.totalSteps}
              <div class="mt-1.5 flex items-center gap-2">
                <div class="flex-1 h-1 rounded-full bg-surface-hover overflow-hidden">
                  <div
                    class="h-full rounded-full bg-violet-400 transition-all duration-500"
                    style="width: {Math.round((agent.steps / agent.totalSteps) * 100)}%"
                  ></div>
                </div>
                <span class="text-[10px] text-text-faint shrink-0">{agent.steps}/{agent.totalSteps} steps</span>
              </div>
            {:else if agent.status === 'complete'}
              <div class="mt-1.5 text-[10px] text-text-faint">{agent.steps} steps · done</div>
            {:else if agent.status === 'error'}
              <div class="mt-1.5 text-[10px] text-text-faint">{agent.steps} steps · failed</div>
            {/if}
          </div>
        </div>
        {#if agent.result}
          <div class="px-3 py-1.5 bg-emerald-50 border-t border-emerald-100 text-[10px] text-emerald-700 leading-snug">
            <span class="mr-1 text-emerald-500">↳</span>{agent.result}
          </div>
        {:else if agent.error}
          <div class="px-3 py-1.5 bg-red-50 border-t border-red-100 text-[10px] text-red-600 leading-snug">
            <span class="mr-1">⚠</span>{agent.error}
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>
