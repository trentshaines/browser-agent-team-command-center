<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { page } from '$app/state';
  import { messages as messagesApi, type Message } from '$lib/api';
  import { sessionsStore } from '$lib/stores/sessions';
  import MessageBubble from '$lib/components/MessageBubble.svelte';
  import ChatInput from '$lib/components/ChatInput.svelte';
  import AgentRunPanel, { type AgentRun } from '$lib/components/AgentRunPanel.svelte';

  let sessionId = $derived(page.params.sessionId!);
  let messageList = $state<Message[]>([]);
  let streaming = $state(false);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let scrollEl: HTMLDivElement;
  let eventSource: EventSource | null = null;

  // Agent run tracking
  let agentRuns = $state<AgentRun[]>([]);

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
    loading = true;
    error = null;
    autoScroll = true;
    agentRuns = [];
    closeSSE();
    try {
      messageList = await messagesApi.list(id);
    } catch (e) {
      error = 'Failed to load messages';
    } finally {
      loading = false;
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

    eventSource.addEventListener('done', (e) => {
      const data = JSON.parse(e.data);
      finalizeMessage(data.message_id, data.content);
      streaming = false;
      sessionsStore.bumpUpdated(id);
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

    eventSource.addEventListener('error_event', () => {
      streaming = false;
    });

    eventSource.onerror = () => {
      // SSE reconnects automatically; ignore transient errors
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

  onDestroy(() => {
    closeSSE();
  });
</script>

<div class="flex flex-col h-full">
  <!-- Messages area -->
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
          <MessageBubble {message} />
        {/each}
        <AgentRunPanel runs={agentRuns} />
      {/if}
    </div>
  </div>

  <!-- Input -->
  <ChatInput
    onsubmit={sendMessage}
    disabled={loading}
    {streaming}
    onstop={() => { streaming = false; }}
  />
</div>
