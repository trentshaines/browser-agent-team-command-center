<script lang="ts">
  import { onMount } from 'svelte';
  import WidgetMessageBubble from './WidgetMessageBubble.svelte';
  import type { WidgetMessage } from './types';

  const WIDGET_MIN_W = 320;
  const WIDGET_MAX_W = 640;
  const WIDGET_MIN_H = 360;
  const WIDGET_MAX_H = 85; // vh

  type TabId = 'chat' | 'history';

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
    const m = Math.floor(s / 60);
    return `${m}m ago`;
  }

  let activeTab = $state<TabId>('chat');
  let widgetW = $state(380);
  let widgetH = $state(520);
  let widgetTop = $state(0);
  let widgetLeft = $state(0);

  // Top-edge resize state
  let resizeStart = $state<{ y: number; h: number; top: number } | null>(null);
  // Header drag-to-move state
  let moveStart = $state<{ mx: number; my: number; wx: number; wy: number } | null>(null);

  const AGENT_NAMES = ['Kelly Agent', 'James Agent'] as const;
  let agentIndex = $state(0);

  let inputValue = $state('');
  let inputEl: HTMLInputElement;
  let scrollEl: HTMLDivElement;

  let chatMessages = $state<WidgetMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hi! This is the dev chat widget. Type a message below.',
      created_at: new Date().toISOString(),
      senderName: 'Kelly Agent',
    },
  ]);

  function scrollToBottom() {
    requestAnimationFrame(() => {
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    });
  }

  $effect(() => {
    chatMessages; // track any change — new messages or streaming content updates
    scrollToBottom();
  });

  onMount(() => {
    widgetTop = window.innerHeight - widgetH - 24;
    widgetLeft = window.innerWidth - widgetW - 24;
  });

  // Invisible top-edge: resize height (keeps bottom edge fixed)
  function onTopEdgeDown(e: PointerEvent) {
    e.preventDefault();
    e.stopPropagation();
    resizeStart = { y: e.clientY, h: widgetH, top: widgetTop };
    window.addEventListener('pointermove', onTopEdgeMove);
    window.addEventListener('pointerup', onTopEdgeUp);
    window.addEventListener('pointercancel', onTopEdgeUp);
  }

  function onTopEdgeMove(e: PointerEvent) {
    if (!resizeStart) return;
    const dy = e.clientY - resizeStart.y;
    const newH = Math.min(
      window.innerHeight * (WIDGET_MAX_H / 100),
      Math.max(WIDGET_MIN_H, resizeStart.h - dy)
    );
    widgetTop = Math.max(0, resizeStart.top + (resizeStart.h - newH));
    widgetH = newH;
  }

  function onTopEdgeUp() {
    resizeStart = null;
    window.removeEventListener('pointermove', onTopEdgeMove);
    window.removeEventListener('pointerup', onTopEdgeUp);
    window.removeEventListener('pointercancel', onTopEdgeUp);
  }

  // Header: drag to move widget
  function onHeaderDown(e: PointerEvent) {
    if ((e.target as HTMLElement).closest('button')) return;
    e.preventDefault();
    moveStart = { mx: e.clientX, my: e.clientY, wx: widgetLeft, wy: widgetTop };
    window.addEventListener('pointermove', onHeaderMove);
    window.addEventListener('pointerup', onHeaderUp);
    window.addEventListener('pointercancel', onHeaderUp);
  }

  function onHeaderMove(e: PointerEvent) {
    if (!moveStart) return;
    widgetLeft = Math.max(0, Math.min(window.innerWidth - widgetW, moveStart.wx + (e.clientX - moveStart.mx)));
    widgetTop = Math.max(0, Math.min(window.innerHeight - widgetH, moveStart.wy + (e.clientY - moveStart.my)));
  }

  function onHeaderUp() {
    moveStart = null;
    window.removeEventListener('pointermove', onHeaderMove);
    window.removeEventListener('pointerup', onHeaderUp);
    window.removeEventListener('pointercancel', onHeaderUp);
  }

  async function sendMessage(content: string) {
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    chatMessages = [...chatMessages, userMsg];

    const name = AGENT_NAMES[agentIndex % AGENT_NAMES.length];
    agentIndex += 1;
    const fullContent = `You said: "${content}" — (widget is local-only, no backend.)`;
    const msgId = crypto.randomUUID();

    const assistantMsg: WidgetMessage = {
      id: msgId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      senderName: name,
    };
    chatMessages = [...chatMessages, assistantMsg];

    // Simulate streaming: add one character at a time
    for (let i = 0; i < fullContent.length; i++) {
      await new Promise<void>(r => setTimeout(r, 18));
      chatMessages = chatMessages.map(m =>
        m.id === msgId ? { ...m, content: fullContent.slice(0, i + 1) } : m
      );
    }
  }

  function onInputKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const trimmed = inputValue.trim();
      if (!trimmed) return;
      sendMessage(trimmed);
      inputValue = '';
      inputEl?.focus();
    }
  }
</script>

<div
  class="fixed z-50 select-none"
  style="top: {widgetTop}px; left: {widgetLeft}px"
>
  <!-- Glass border pane — sits behind the widget, bleeds out on all sides -->
  <div class="absolute -inset-3 rounded-[2.25rem] backdrop-blur-xl bg-white/20 border border-white/50 shadow-[0_20px_64px_rgba(0,0,0,0.18)]" />

  <!-- Widget -->
  <div
    class="relative flex flex-col rounded-3xl bg-white/95 overflow-hidden shadow-[0_4px_20px_rgba(0,0,0,0.06)]"
    style="width: {widgetW}px; height: {widgetH}px"
  >
  <!-- Invisible top-edge resize handle -->
  <div
    role="separator"
    aria-label="Resize chat widget"
    class="absolute top-0 left-0 right-0 h-2 cursor-n-resize touch-none z-10"
    onpointerdown={onTopEdgeDown}
  />

  <!-- Tabs / drag handle -->
  <header
    class="shrink-0 border-b border-border-subtle/50 px-3 py-2.5"
    onpointerdown={onHeaderDown}
  >
    <div class="flex rounded-2xl bg-surface p-1 gap-0.5" role="tablist">
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'chat'}
        class="flex-1 py-1.5 px-3 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer {activeTab ===
        'chat'
          ? 'bg-surface-hover text-text shadow-sm'
          : 'text-text-muted hover:text-text'}"
        onclick={() => (activeTab = 'chat')}
      >
        Chat History
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'history'}
        class="flex-1 py-1.5 px-3 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer {activeTab ===
        'history'
          ? 'bg-surface-hover text-text shadow-sm'
          : 'text-text-muted hover:text-text'}"
        onclick={() => (activeTab = 'history')}
      >
        View Progress
      </button>
    </div>
  </header>

  <!-- Content -->
  <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
    {#if activeTab === 'chat'}
      <div
        bind:this={scrollEl}
        class="flex-1 min-h-0 overflow-y-auto px-4 py-3 flex flex-col bg-transparent"
      >
        {#each chatMessages as msg (msg.id)}
          <WidgetMessageBubble message={msg} senderName={msg.senderName} />
        {/each}
      </div>
      <div class="shrink-0 border-t border-border-subtle/50 px-3 py-3">
        <div class="flex items-center gap-2 rounded-2xl bg-surface border border-border-subtle px-4 py-2.5 focus-within:border-border transition-colors">
          <input
            bind:this={inputEl}
            bind:value={inputValue}
            onkeydown={onInputKeydown}
            type="text"
            placeholder="Message the team..."
            class="flex-1 bg-transparent text-sm text-text placeholder:text-text-faint outline-none"
          />
        </div>
      </div>
    {:else}
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
            <!-- Agent row -->
            <div class="flex items-start gap-2.5 px-3 py-2.5">
              <!-- Status indicator -->
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
                <!-- Name + elapsed -->
                <div class="flex items-center gap-1.5 mb-0.5">
                  <span class="text-xs font-medium text-text">{agent.name}</span>
                  <span class="text-[10px] text-text-faint">{elapsedLabel(agent.startedAt)}</span>
                </div>
                <!-- Task -->
                <p class="text-[11px] text-text-muted leading-snug truncate">{agent.task}</p>

                <!-- Progress bar (running only) -->
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

            <!-- Result / error footer -->
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
    {/if}
  </div>
  </div>
</div>
