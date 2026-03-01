<script lang="ts">
  import { onMount } from 'svelte';
  import ChatPanel from './ChatPanel.svelte';
  import ProgressPanel from './ProgressPanel.svelte';
  import type { WidgetMessage } from './types';
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';

  const WIDGET_MIN_W = 320;
  const WIDGET_MAX_W = 640;
  const WIDGET_MIN_H = 360;
  const WIDGET_MAX_H = 95; // vh

  type TabId = 'chat' | 'history';

  let activeTab = $state<TabId>('chat');
  let widgetW = $state(380);
  let widgetH = $state(0); // set in onMount based on viewport
  let widgetTop = $state(0);
  let widgetLeft = $state(0);

  // Top-edge resize state
  let resizeStart = $state<{ y: number; h: number; top: number } | null>(null);
  // Header drag-to-move state
  let moveStart = $state<{ mx: number; my: number; wx: number; wy: number } | null>(null);

  let {
    onSpawnAgent,
    messages: externalMessages = undefined,
    streaming = false,
    onSend: externalOnSend = undefined,
    onStop = undefined,
    disabled = false,
    agentRuns = [],
  }: {
    onSpawnAgent?: () => void;
    messages?: WidgetMessage[];
    streaming?: boolean;
    onSend?: (content: string) => void;
    onStop?: () => void;
    disabled?: boolean;
    agentRuns?: AgentRun[];
  } = $props();

  // Fallback mock messages used only when no external messages are provided.
  let mockMessages = $state<WidgetMessage[]>([]);

  const controlled = $derived(externalOnSend !== undefined);
  const displayMessages = $derived(controlled ? (externalMessages ?? []) : mockMessages);
  const handleSend = $derived<((content: string) => void) | undefined>(
    disabled ? undefined : (controlled ? externalOnSend : mockSend)
  );

  // Latest assistant message text — shown as orchestrator summary in ProgressPanel
  const orchestratorText = $derived(
    [...displayMessages].reverse().find(m => m.role === 'assistant')?.content ?? ''
  );

  onMount(() => {
    widgetH = Math.round(window.innerHeight * 0.88);
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
  // Track whether a drag actually moved — if not, let the click through to buttons
  let didDrag = $state(false);

  function onHeaderDown(e: PointerEvent) {
    e.preventDefault();
    didDrag = false;
    moveStart = { mx: e.clientX, my: e.clientY, wx: widgetLeft, wy: widgetTop };
    window.addEventListener('pointermove', onHeaderMove);
    window.addEventListener('pointerup', onHeaderUp);
    window.addEventListener('pointercancel', onHeaderUp);
  }

  function onHeaderMove(e: PointerEvent) {
    if (!moveStart) return;
    const dx = e.clientX - moveStart.mx;
    const dy = e.clientY - moveStart.my;
    if (!didDrag && Math.abs(dx) < 3 && Math.abs(dy) < 3) return;
    didDrag = true;
    widgetLeft = Math.max(0, Math.min(window.innerWidth - widgetW, moveStart.wx + dx));
    widgetTop = Math.max(0, Math.min(window.innerHeight - widgetH, moveStart.wy + dy));
  }

  function onHeaderUp(e: PointerEvent) {
    const wasDrag = didDrag;
    moveStart = null;
    didDrag = false;
    window.removeEventListener('pointermove', onHeaderMove);
    window.removeEventListener('pointerup', onHeaderUp);
    window.removeEventListener('pointercancel', onHeaderUp);
    // If it wasn't a drag, simulate a click on the original target (for tab buttons)
    if (!wasDrag) {
      const target = document.elementFromPoint(e.clientX, e.clientY);
      if (target instanceof HTMLElement) target.click();
    }
  }

  function mockSend(content: string) {
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    mockMessages = [...mockMessages, userMsg];
  }
</script>

<div
  class="fixed z-50 select-none"
  style="top: {widgetTop}px; left: {widgetLeft}px"
>
  <!-- Glass halo — sits behind the widget, bleeds out on all sides -->
  <div class="absolute -inset-2 rounded-[1.5rem] backdrop-blur-xl bg-white/30 border border-white/50 shadow-[0_24px_80px_rgba(0,0,0,0.22),0_8px_24px_rgba(0,0,0,0.12),inset_0_1px_0_rgba(255,255,255,0.55)]" />

  <!-- Widget -->
  <div
    class="relative flex flex-col rounded-2xl overflow-hidden bg-surface border border-white/25 shadow-[0_8px_32px_rgba(0,0,0,0.14)]"
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
      class="shrink-0 border-b border-white/15 px-3 py-2.5 bg-white/5 cursor-grab active:cursor-grabbing touch-none"
      onpointerdown={onHeaderDown}
    >
      <div class="flex items-center gap-1">
        <div class="flex flex-1 rounded-lg bg-white/10 p-0.5 gap-0.5" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'chat'}
            class="flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-all duration-150 cursor-pointer {activeTab === 'chat' ? 'bg-white/30 text-text shadow-sm' : 'text-text-muted hover:text-text hover:bg-white/10'}"
            onclick={() => (activeTab = 'chat')}
          >
            Chat
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'history'}
            class="flex-1 py-1.5 px-3 rounded-md text-xs font-medium transition-all duration-150 cursor-pointer {activeTab === 'history' ? 'bg-white/30 text-text shadow-sm' : 'text-text-muted hover:text-text hover:bg-white/10'}"
            onclick={() => (activeTab = 'history')}
          >
            Progress
          </button>
        </div>
        {#if streaming && onStop}
          <button
            type="button"
            onclick={onStop}
            class="shrink-0 ml-1 p-1.5 rounded-xl text-text-muted hover:text-text hover:bg-white/15 transition-colors"
            aria-label="Stop generating"
            title="Stop generating"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <rect x="4" y="4" width="16" height="16" rx="2"/>
            </svg>
          </button>
        {:else if streaming}
          <div class="shrink-0 ml-2 w-3.5 h-3.5 border-2 border-text-muted/40 border-t-text-muted rounded-full animate-spin"></div>
        {/if}
      </div>
    </header>

    <!-- Content -->
    <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
      {#if activeTab === 'chat'}
        <ChatPanel messages={displayMessages} onSend={handleSend} {onSpawnAgent} />
      {:else}
        <ProgressPanel {agentRuns} {streaming} {orchestratorText} />
      {/if}
    </div>
  </div>
</div>
