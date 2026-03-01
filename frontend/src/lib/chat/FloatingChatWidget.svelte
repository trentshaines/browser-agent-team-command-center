<script lang="ts">
  import ChatInput from '$lib/components/ChatInput.svelte';
  import WidgetMessageBubble from './WidgetMessageBubble.svelte';
  import type { WidgetMessage } from './types';

  const WIDGET_MIN_W = 320;
  const WIDGET_MAX_W = 640;
  const WIDGET_MIN_H = 360;
  const WIDGET_MAX_H = 85; // vh

  type TabId = 'chat' | 'history';

  let activeTab = $state<TabId>('chat');
  let widgetW = $state(380);
  let widgetH = $state(520);
  let resizeStart = $state<{ x: number; y: number; w: number; h: number } | null>(null);

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

  function onWidgetResizeDown(e: PointerEvent) {
    e.preventDefault();
    resizeStart = { x: e.clientX, y: e.clientY, w: widgetW, h: widgetH };
    window.addEventListener('pointermove', onWindowResizeMove);
    window.addEventListener('pointerup', onWindowResizeUp);
    window.addEventListener('pointercancel', onWindowResizeUp);
  }

  function onWindowResizeMove(e: PointerEvent) {
    if (!resizeStart) return;
    const dx = e.clientX - resizeStart.x;
    const dy = e.clientY - resizeStart.y;
    widgetW = Math.min(WIDGET_MAX_W, Math.max(WIDGET_MIN_W, resizeStart.w + dx));
    widgetH = Math.min(
      window.innerHeight * (WIDGET_MAX_H / 100),
      Math.max(WIDGET_MIN_H, resizeStart.h - dy)
    );
  }

  function onWindowResizeUp() {
    resizeStart = null;
    window.removeEventListener('pointermove', onWindowResizeMove);
    window.removeEventListener('pointerup', onWindowResizeUp);
    window.removeEventListener('pointercancel', onWindowResizeUp);
  }

  function sendMessage(content: string) {
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    chatMessages = [...chatMessages, userMsg];
    const name = AGENT_NAMES[agentIndex % AGENT_NAMES.length];
    agentIndex += 1;
    const assistantMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `You said: "${content}" — (widget is local-only, no backend.)`,
      created_at: new Date().toISOString(),
      senderName: name,
    };
    chatMessages = [...chatMessages, assistantMsg];
  }
</script>

<div
  class="fixed bottom-6 right-6 flex flex-col rounded-3xl border border-white/60 bg-white/95 shadow-[0_8px_32px_rgba(0,0,0,0.08)] overflow-hidden z-50 backdrop-blur-sm transition-shadow duration-200 hover:shadow-[0_12px_40px_rgba(0,0,0,0.12)]"
  style="width: {widgetW}px; height: {widgetH}px"
>
  <!-- Resize handle at top: drag to resize (window listeners so it works across re-renders) -->
  <div
    role="separator"
    aria-label="Resize chat widget"
    class="shrink-0 flex justify-center py-2 cursor-n-resize touch-none select-none text-border-subtle hover:text-border bg-surface/30 border-b border-border-subtle/50"
    onpointerdown={onWidgetResizeDown}
  >
    <div class="w-10 h-1 rounded-full bg-current/60 hover:bg-current transition-colors"></div>
  </div>

  <!-- Tabs -->
  <header class="shrink-0 border-b border-border-subtle/50 bg-surface/40 px-3 py-2">
    <div class="flex rounded-xl bg-surface-hover/60 p-0.5" role="tablist">
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'chat'}
        class="flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors {activeTab ===
        'chat'
          ? 'bg-white text-text shadow-sm'
          : 'text-text-muted hover:text-text'}"
        onclick={() => (activeTab = 'chat')}
      >
        Chat History
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === 'history'}
        class="flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-colors {activeTab ===
        'history'
          ? 'bg-white text-text shadow-sm'
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
        class="flex-1 min-h-0 overflow-y-auto px-4 py-3 flex flex-col bg-transparent"
      >
        {#each chatMessages as msg (msg.id)}
          <WidgetMessageBubble message={msg} senderName={msg.senderName} />
        {/each}
      </div>
      <div class="shrink-0 min-h-[88px] border-t border-border-subtle/50 bg-surface/30 flex flex-col justify-end pointer-events-auto">
        <ChatInput onsubmit={sendMessage} />
      </div>
    {:else}
      <div
        class="flex-1 overflow-y-auto px-3 py-4 text-sm text-text-muted text-center"
      >
        <p>View Progress</p>
        <p class="mt-2 text-text-faint text-xs">
          Progress and run status will appear here.
        </p>
      </div>
    {/if}
  </div>
</div>
