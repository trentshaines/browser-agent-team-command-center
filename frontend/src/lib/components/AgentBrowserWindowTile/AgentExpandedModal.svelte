<script lang="ts">
  import { fade, scale } from 'svelte/transition';
  import { quintOut } from 'svelte/easing';
  import ChatPanel from '$lib/chat/ChatPanel.svelte';
  import ProgressPanel from '$lib/chat/ProgressPanel.svelte';
  import type { Message } from '$lib/api';
  import type { WidgetMessage } from '$lib/chat/types';

  let {
    isOpen,
    src,
    alt,
    agentName,
    status,
    messages,
    modalOrigin = '50% 50%',
    liveUrl = null,
    onClose,
  }: {
    isOpen: boolean;
    src: string;
    alt: string;
    agentName: string;
    status: string;
    messages: Message[];
    modalOrigin?: string;
    liveUrl?: string | null;
    onClose: () => void;
  } = $props();

  type TabId = 'chat' | 'progress';
  let activeTab = $state<TabId>('chat');

  // Map session messages to WidgetMessage format so ChatPanel can display them
  const widgetMessages = $derived<WidgetMessage[]>(
    messages.map(m => ({
      ...m,
      senderName: m.role === 'assistant' ? agentName : undefined,
    }))
  );

  $effect(() => {
    if (!isOpen) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
    };
  });
</script>

{#if isOpen}
  <!-- Backdrop -->
  <div
    transition:fade={{ duration: 280 }}
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/40 backdrop-blur-sm"
    role="presentation"
    onclick={onClose}
  >
    <!-- Glass outer frame (scales in/out from tile origin) -->
    <div
      in:scale={{ start: 0.93, duration: 420, easing: quintOut }}
      out:scale={{ start: 0.93, duration: 220 }}
      class="relative"
      style="transform-origin: {modalOrigin}"
    >
      <!-- Glass halo -->
      <div
        class="absolute -inset-2 rounded-[1.5rem] backdrop-blur-xl bg-white/20 border border-white/50 shadow-[0_24px_80px_rgba(0,0,0,0.20),0_8px_24px_rgba(0,0,0,0.10),inset_0_1px_0_rgba(255,255,255,0.6)]"
        aria-hidden="true"
      ></div>

      <!-- Modal: left = screenshot, right = tabbed chat sidebar -->
      <div
        class="relative flex w-[90vw] h-[85vh] rounded-2xl overflow-hidden shadow-[0_8px_32px_rgba(0,0,0,0.12)]"
        role="dialog"
        aria-modal="true"
        aria-label="Expanded browser view"
        tabindex="-1"
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => { if (e.key === 'Escape') onClose(); }}
      >
        <!-- Left: Browser view (screenshot or live iframe) -->
        <div class="relative flex-[7] min-w-0">
          {#if liveUrl}
            <iframe
              src={liveUrl}
              title="Live browser session"
              class="size-full border-0 absolute inset-0"
              sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
            ></iframe>
          {:else}
            <img {src} {alt} class="size-full object-cover" draggable="false" />
          {/if}

          <!-- Agent info overlay -->
          <div class="absolute bottom-0 inset-x-0 px-4 py-3 bg-gradient-to-t from-black/80 to-transparent flex items-end justify-between pointer-events-none">
            <div class="flex items-center gap-3">
              <span class="text-white/90 text-sm font-medium">{agentName}</span>
              <span class="text-white/60 text-xs">{status}</span>
            </div>
          </div>

        </div>

        <!-- Right: Tabbed sidebar — same as FloatingChatWidget -->
        <div class="flex-[3] flex flex-col bg-surface/85 backdrop-blur-xl border-l border-border min-w-0">
          <!-- Tab bar -->
          <div class="shrink-0 border-b border-border-subtle/50 px-3 py-2.5">
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
                aria-selected={activeTab === 'progress'}
                class="flex-1 py-1.5 px-3 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer {activeTab === 'progress' ? 'bg-surface-hover text-text shadow-sm' : 'text-text-muted hover:text-text'}"
                onclick={() => (activeTab = 'progress')}
              >
                View Progress
              </button>
            </div>
          </div>

          <!-- Tab content -->
          <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
            {#if activeTab === 'chat'}
              <ChatPanel messages={widgetMessages} />
            {:else}
              <ProgressPanel />
            {/if}
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}
