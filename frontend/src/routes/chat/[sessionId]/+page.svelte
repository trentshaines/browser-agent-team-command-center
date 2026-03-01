<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { page } from '$app/state';
  import { messages as messagesApi, type Message } from '$lib/api';
  import { sessionsStore } from '$lib/stores/sessions';
  import MessageBubble from '$lib/components/MessageBubble.svelte';
  import ChatInput from '$lib/components/ChatInput.svelte';
  import AgentRunPanel, { type AgentRun } from '$lib/components/AgentRunPanel.svelte';
  import AgentTiles from '$lib/components/AgentTiles.svelte';

  let sessionId = $derived(page.params.sessionId!);
  let messageList = $state<Message[]>([]);
  let streaming = $state(false);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let scrollEl: HTMLDivElement;
  let eventSource: EventSource | null = null;

  // Agent run tracking
  let agentRuns = $state<AgentRun[]>([]);

  // Live screenshot frames per agent (keyed by agent_id from browser_agent.py)
  let agentFrames = $state<Record<string, { step: number | null; url: string | null; screenshot: string | null; done: boolean }>>({});

  // Thinking content per message (messageId -> accumulated text)
  let thinkingMap = $state<Map<string, string>>(new Map());
  let thinkingDoneSet = $state<Set<string>>(new Set());

  // Stale-request guard: incremented on each loadMessages call so an in-flight
  // fetch from a previous session cannot overwrite state for the current one.
  let loadSeq = 0;

  // Smart scroll: only snap to bottom if user is already near the bottom
  let autoScroll = true;

  function onScroll() {
    if (!scrollEl) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollEl;
    autoScroll = scrollHeight - scrollTop - clientHeight < 120;
  }

  // Load messages when session changes
  $effect(() => {
    const id = sessionId;
    loadMessages(id);
    return () => {
      closeSSE();
    };
  });

  async function loadMessages(id: string) {
    const seq = ++loadSeq;
    loading = true;
    error = null;
    autoScroll = true;
    agentRuns = [];
    thinkingMap = new Map();
    thinkingDoneSet = new Set();
    closeSSE();
    try {
      const result = await messagesApi.list(id);
      if (seq !== loadSeq) return; // superseded by a newer session selection
      messageList = result;
    } catch (e) {
      if (seq !== loadSeq) return;
      error = 'Failed to load messages';
    } finally {
      if (seq === loadSeq) loading = false;
    }
    await tick();
    scrollToBottom(true);
    connectSSE(id);

    // Handle starter prompt from query param
    const starter = page.url.searchParams.get('starter');
    if (starter && messageList.length === 0) {
      const url = new URL(window.location.href);
      url.searchParams.delete('starter');
      history.replaceState({}, '', url.toString());
      await sendMessage(starter);
    }
  }

  function connectSSE(id: string) {
    const url = messagesApi.streamUrl(id);
    eventSource = new EventSource(url, { withCredentials: true });

    eventSource.addEventListener('delta', (e) => {
      const data = JSON.parse(e.data);
      applyDelta(data.message_id, data.delta);
    });

    eventSource.addEventListener('thinking_delta', (e) => {
      const data = JSON.parse(e.data);
      const mid = data.message_id as string;
      const prev = thinkingMap.get(mid) ?? '';
      const isFirst = prev === '';
      thinkingMap = new Map([...thinkingMap, [mid, prev + data.thinking]]);
      // Force scroll when thinking block first appears (it adds height to the page)
      if (isFirst) scrollToBottom(true);
      else scrollToBottom();
    });

    eventSource.addEventListener('done', (e) => {
      const data = JSON.parse(e.data);
      finalizeMessage(data.message_id, data.content);
      // Mark thinking done for this message
      if (thinkingMap.has(data.message_id)) {
        thinkingDoneSet = new Set([...thinkingDoneSet, data.message_id]);
      }
      streaming = false;
      sessionsStore.bumpUpdated(id);
      // Mark all agent tiles as done
      agentFrames = Object.fromEntries(
        Object.entries(agentFrames).map(([aid, f]) => [aid, { ...f, done: true }])
      );
    });

    eventSource.addEventListener('agent_event', (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'agent_spawned') {
        agentRuns = [...agentRuns, {
          id: data.agent_id,
          task: data.task,
          status: 'running',
          steps: [],
        }];
      } else if (data.type === 'agent_complete') {
        agentRuns = agentRuns.map(r =>
          r.id === data.agent_run_id
            ? { ...r, status: data.result ? 'complete' : 'error', result: data.result, total_steps: data.total_steps }
            : r
        );
      }
      scrollToBottom();
    });

    eventSource.addEventListener('agent_log', (e) => {
      const data = JSON.parse(e.data);
      agentRuns = agentRuns.map(r =>
        r.id === data.agent_run_id
          ? { ...r, steps: [...r.steps, data] }
          : r
      );
      scrollToBottom();
    });

    eventSource.addEventListener('agent_frame', (e) => {
      const data = JSON.parse(e.data);
      const isFirstFrame = !agentFrames[data.agent_id];
      agentFrames[data.agent_id] = {
        step: data.step,
        url: data.url,
        screenshot: data.screenshot,
        done: false,
      };
      // When the tile panel appears for the first time it shrinks the viewport —
      // force scroll so content stays visible.
      if (isFirstFrame) scrollToBottom(true);
    });

    eventSource.addEventListener('error_event', () => {
      streaming = false;
    });

    eventSource.onerror = () => {
      if (eventSource?.readyState === EventSource.CLOSED) {
        streaming = false;
        error = 'Connection lost. Refresh to reconnect.';
      }
    };
  }

  function closeSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function applyDelta(messageId: string, delta: string) {
    const idx = messageList.findIndex(m => m.id === messageId);
    if (idx >= 0) {
      messageList[idx] = { ...messageList[idx], content: messageList[idx].content + delta };
    }
    scrollToBottom();
  }

  function finalizeMessage(messageId: string, content: string) {
    const idx = messageList.findIndex(m => m.id === messageId);
    if (idx >= 0) {
      messageList[idx] = { ...messageList[idx], content };
    }
    scrollToBottom(true);
  }

  async function sendMessage(content: string) {
    if (streaming) return;
    streaming = true;
    error = null;
    agentRuns = [];
    agentFrames = {};
    thinkingMap = new Map();
    thinkingDoneSet = new Set();
    autoScroll = true;

    try {
      const assistantMsg = await messagesApi.send(sessionId, content);

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      messageList = [...messageList, userMsg, { ...assistantMsg, content: '' }];

      await tick();
      scrollToBottom(true);
    } catch (e) {
      streaming = false;
      error = 'Failed to send message';
    }
  }

  function scrollToBottom(force = false) {
    if (!force && !autoScroll) return;
    tick().then(() => {
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    });
  }

  let activeTab = $state<'chat' | 'browser'>('chat');

  const liveAgentCount = $derived(
    Object.values(agentFrames).filter(f => !f.done).length
  );

  // Switch to browser tab automatically when first frame arrives
  $effect(() => {
    if (liveAgentCount > 0 && activeTab === 'chat') {
      activeTab = 'browser';
    }
  });

  onDestroy(() => {
    closeSSE();
  });
</script>

<div class="flex flex-col h-full">
  <!-- Tab bar -->
  <div class="flex items-center gap-1 px-4 pt-2 pb-0 border-b border-border shrink-0">
    <button
      onclick={() => activeTab = 'chat'}
      class="px-3 py-1.5 text-xs font-medium rounded-t transition-colors
        {activeTab === 'chat'
          ? 'text-text border-b-2 border-accent -mb-px'
          : 'text-text-faint hover:text-text'}"
    >
      Chat
    </button>
    <button
      onclick={() => activeTab = 'browser'}
      class="px-3 py-1.5 text-xs font-medium rounded-t transition-colors flex items-center gap-1.5
        {activeTab === 'browser'
          ? 'text-text border-b-2 border-accent -mb-px'
          : 'text-text-faint hover:text-text'}"
    >
      Browser
      {#if liveAgentCount > 0}
        <span class="flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse"></span>
          <span class="text-[10px] text-violet-400">{liveAgentCount}</span>
        </span>
      {:else if Object.keys(agentFrames).length > 0}
        <span class="text-[10px] text-text-faint">{Object.keys(agentFrames).length}</span>
      {/if}
    </button>
  </div>

  <!-- Chat tab -->
  {#if activeTab === 'chat'}
    <div bind:this={scrollEl} onscroll={onScroll} class="flex-1 overflow-y-auto px-4 py-6">
      <div class="max-w-3xl mx-auto">
        {#if loading}
          <div class="flex justify-center py-12">
            <div class="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
          </div>
        {:else if error}
          <div class="text-center py-12">
            <p class="text-danger text-sm">{error}</p>
          </div>
        {:else if messageList.length === 0}
          <div class="flex flex-col items-center justify-center py-16 text-center gap-3">
            <p class="text-text-faint text-sm">Send a message to start the conversation</p>
          </div>
        {:else}
          {#each messageList as message (message.id)}
            <MessageBubble
              {message}
              thinking={thinkingMap.get(message.id) ?? ''}
              thinkingDone={thinkingDoneSet.has(message.id)}
            />
          {/each}
          <AgentRunPanel runs={agentRuns} />
        {/if}
      </div>
    </div>

    <ChatInput
      onsubmit={sendMessage}
      disabled={loading}
      {streaming}
      onstop={() => { streaming = false; }}
    />

  <!-- Browser tab -->
  {:else}
    <div class="flex-1 overflow-y-auto p-4">
      {#if Object.keys(agentFrames).length === 0}
        <div class="flex flex-col items-center justify-center h-full text-center gap-3">
          <p class="text-text-faint text-sm">No browser agents active</p>
          <p class="text-text-faint text-xs">Switch to Chat and send a task that requires web browsing</p>
        </div>
      {:else}
        <AgentTiles frames={agentFrames} fullscreen />
      {/if}
    </div>
  {/if}
</div>
