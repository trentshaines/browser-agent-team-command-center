<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { page } from '$app/state';
  import { messages as messagesApi, agentRuns as agentRunsApi, type Message } from '$lib/api';
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

  // When the user cancels a streaming response, record the message ID so that
  // any in-flight delta/done events for it are ignored.
  let cancelledMessageId = $state<string | null>(null);

  // Smart scroll: only snap to bottom if user is already near the bottom
  let autoScroll = true;
  let _scrollRaf: number | null = null;

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
    cancelledMessageId = null;
    closeSSE();
    try {
      const [msgs, runs] = await Promise.all([
        messagesApi.list(id),
        agentRunsApi.list(id).catch(() => []),
      ]);
      if (seq !== loadSeq) return; // superseded by a newer session selection
      messageList = msgs;
      agentRuns = runs.map(r => ({
        id: r.id,
        task: r.task,
        status: r.status,
        result: r.result,
        total_steps: r.total_steps,
        steps: r.steps,
      }));
    } catch (e) {
      if (seq !== loadSeq) return;
      error = 'Failed to load messages';
    } finally {
      if (seq === loadSeq) loading = false;
    }
    await tick();
    scrollToBottom(true);
    await connectSSE(id);

    // Handle starter prompt from query param
    const starter = page.url.searchParams.get('starter');
    if (starter && messageList.length === 0) {
      const url = new URL(window.location.href);
      url.searchParams.delete('starter');
      history.replaceState({}, '', url.toString());
      await sendMessage(starter);
    }
  }

  function connectSSE(id: string): Promise<void> {
    const url = messagesApi.streamUrl(id);
    eventSource = new EventSource(url, { withCredentials: true });

    // Resolve once the connection is open (or immediately on error so callers aren't stuck)
    const ready = new Promise<void>((resolve) => {
      eventSource!.addEventListener('open', () => resolve(), { once: true });
      eventSource!.addEventListener('error', () => resolve(), { once: true });
    });

    eventSource.addEventListener('delta', (e) => {
      const data = JSON.parse(e.data);
      applyDelta(data.message_id, data.delta);
    });

    eventSource.addEventListener('thinking_delta', (e) => {
      const data = JSON.parse(e.data);
      const mid = data.message_id as string;
      const prev = thinkingMap.get(mid) ?? '';
      const isFirst = prev === '';
      thinkingMap.set(mid, prev + data.thinking);
      thinkingMap = thinkingMap;
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
          name: data.name ?? `Browser ${agentRuns.length + 1}`,
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
      const runIdx = agentRuns.findIndex(r => r.id === data.agent_run_id);
      if (runIdx >= 0) {
        agentRuns[runIdx] = { ...agentRuns[runIdx], steps: [...agentRuns[runIdx].steps, data] };
      }
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

    eventSource.addEventListener('error_event', (e) => {
      streaming = false;
      try {
        const data = JSON.parse(e.data);
        if (data.error) error = `Agent error: ${data.error}`;
      } catch { /* ignore parse errors */ }
    });

    eventSource.onerror = () => {
      if (eventSource?.readyState === EventSource.CLOSED) {
        streaming = false;
        error = 'Connection lost. Refresh to reconnect.';
      }
    };

    return ready;
  }

  function closeSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function applyDelta(messageId: string, delta: string) {
    if (messageId === cancelledMessageId) return; // ignore events for cancelled messages
    const last = messageList[messageList.length - 1];
    if (last?.id === messageId) {
      messageList[messageList.length - 1] = { ...last, content: last.content + delta };
    } else {
      // fallback for safety
      const idx = messageList.findIndex(m => m.id === messageId);
      if (idx >= 0) {
        messageList[idx] = { ...messageList[idx], content: messageList[idx].content + delta };
      }
    }
    scrollToBottom();
  }

  function finalizeMessage(messageId: string, content: string) {
    if (messageId === cancelledMessageId) return; // ignore finalization for cancelled messages
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
    cancelledMessageId = null; // clear any previous cancellation

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
    if (_scrollRaf !== null) return; // already scheduled
    _scrollRaf = requestAnimationFrame(() => {
      _scrollRaf = null;
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    });
  }

  let activeTab = $state<'chat' | 'browser'>('chat');

  const liveAgentCount = $derived(
    Object.values(agentFrames).filter(f => !f.done).length
  );

  // Global Escape key handler — works regardless of which element has focus
  $effect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && streaming) {
        e.preventDefault();
        const last = messageList[messageList.length - 1];
        if (last?.role === 'assistant') cancelledMessageId = last.id;
        streaming = false;
        const id = sessionId;
        closeSSE();
        connectSSE(id);
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  });

  onDestroy(() => {
    closeSSE();
  });
</script>

<div class="flex flex-col h-full">
  <!-- Tab bar -->
  <div class="flex items-center gap-1 px-4 pt-2 pb-0 border-b border-border shrink-0" role="tablist" aria-label="Chat views">
    <button
      role="tab"
      aria-selected={activeTab === 'chat'}
      aria-controls="panel-chat"
      onclick={() => activeTab = 'chat'}
      class="px-3 py-1.5 text-xs font-medium rounded-t transition-colors
        {activeTab === 'chat'
          ? 'text-text border-b-2 border-accent -mb-px'
          : 'text-text-faint hover:text-text'}"
    >
      Chat
    </button>
    <button
      role="tab"
      aria-selected={activeTab === 'browser'}
      aria-controls="panel-browser"
      onclick={() => activeTab = 'browser'}
      class="px-3 py-1.5 text-xs font-medium rounded-t transition-colors flex items-center gap-1.5
        {activeTab === 'browser'
          ? 'text-text border-b-2 border-accent -mb-px'
          : 'text-text-faint hover:text-text'}"
    >
      Browser
      {#if liveAgentCount > 0}
        <span class="flex items-center gap-1" aria-label="{liveAgentCount} agents live">
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
    <div id="panel-chat" role="tabpanel" bind:this={scrollEl} onscroll={onScroll} class="flex-1 overflow-y-auto px-4 py-6">
      <div class="max-w-3xl mx-auto">
        {#if loading}
          <div class="flex justify-center py-12" role="status" aria-label="Loading messages">
            <div class="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" aria-hidden="true"></div>
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

    <!-- Agent tiles: inline screenshot strip -->
    {#if Object.keys(agentFrames).length > 0}
      <AgentTiles frames={agentFrames} />
    {:else if agentRuns.some(r => r.status === 'running')}
      <div class="border-t border-border-subtle bg-surface px-4 py-2 flex items-center gap-2 shrink-0">
        <span class="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse shrink-0"></span>
        <span class="text-xs text-text-muted">
          {agentRuns.filter(r => r.status === 'running').length} agent{agentRuns.filter(r => r.status === 'running').length !== 1 ? 's' : ''} working…
        </span>
      </div>
    {/if}

    <ChatInput
      onsubmit={sendMessage}
      disabled={loading}
      {streaming}
      onstop={() => {
        // Record which message is being cancelled so its events are ignored
        const last = messageList[messageList.length - 1];
        if (last?.role === 'assistant') cancelledMessageId = last.id;
        streaming = false;
        // Close and immediately reconnect SSE so future messages still stream
        const id = sessionId;
        closeSSE();
        connectSSE(id);
      }}
    />

  <!-- Browser tab -->
  {:else}
    <div id="panel-browser" role="tabpanel" class="flex-1 overflow-y-auto p-4">
      {#if Object.keys(agentFrames).length === 0}
        <div class="flex flex-col items-center justify-center h-full text-center gap-3">
          <p class="text-text-faint text-sm">No browser agents active</p>
          <button
            onclick={() => activeTab = 'chat'}
            class="text-xs text-accent hover:underline"
          >
            ← Go to Chat and send a task that requires web browsing
          </button>
        </div>
      {:else}
        <AgentTiles frames={agentFrames} fullscreen />
      {/if}
    </div>
  {/if}
</div>
