<script lang="ts">
  import { onMount } from 'svelte';
  import ChatPanel from './ChatPanel.svelte';
  import ProgressPanel from './ProgressPanel.svelte';
  import type { WidgetMessage } from './types';

  const WIDGET_MIN_W = 320;
  const WIDGET_MAX_W = 640;
  const WIDGET_MIN_H = 360;
  const WIDGET_MAX_H = 85; // vh

  type TabId = 'chat' | 'history';

  let activeTab = $state<TabId>('chat');
  let widgetW = $state(380);
  let widgetH = $state(680);
  let widgetTop = $state(0);
  let widgetLeft = $state(0);

  // Top-edge resize state
  let resizeStart = $state<{ y: number; h: number; top: number } | null>(null);
  // Header drag-to-move state
  let moveStart = $state<{ mx: number; my: number; wx: number; wy: number } | null>(null);

  const AGENT_NAMES = ['Kelly Agent', 'James Agent'] as const;
  let agentIndex = $state(0);

  let chatMessages = $state<WidgetMessage[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Hi! This is the dev chat widget. Type a message below.',
      created_at: new Date().toISOString(),
      senderName: 'Kelly Agent',
    },
  ]);

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

    for (let i = 0; i < fullContent.length; i++) {
      await new Promise<void>(r => setTimeout(r, 18));
      chatMessages = chatMessages.map(m =>
        m.id === msgId ? { ...m, content: fullContent.slice(0, i + 1) } : m
      );
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
          class="flex-1 py-1.5 px-3 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer {activeTab === 'chat' ? 'bg-surface-hover text-text shadow-sm' : 'text-text-muted hover:text-text'}"
          onclick={() => (activeTab = 'chat')}
        >
          Chat History
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'history'}
          class="flex-1 py-1.5 px-3 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer {activeTab === 'history' ? 'bg-surface-hover text-text shadow-sm' : 'text-text-muted hover:text-text'}"
          onclick={() => (activeTab = 'history')}
        >
          View Progress
        </button>
      </div>
    </header>

    <!-- Content -->
    <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
      {#if activeTab === 'chat'}
        <ChatPanel messages={chatMessages} onSend={sendMessage} />
      {:else}
        <ProgressPanel />
      {/if}
    </div>
  </div>
</div>
