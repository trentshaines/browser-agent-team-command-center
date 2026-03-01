<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { page } from '$app/state';
  import { messages as messagesApi, type Message } from '$lib/api';
  import { sessionsStore } from '$lib/stores/sessions';
  import MessageBubble from '$lib/components/MessageBubble.svelte';
  import ChatInput from '$lib/components/ChatInput.svelte';

  let sessionId = $derived(page.params.sessionId!);
  let messageList = $state<Message[]>([]);
  let streaming = $state(false);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let scrollEl: HTMLDivElement;
  let eventSource: EventSource | null = null;

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
    closeSSE();
    try {
      messageList = await messagesApi.list(id);
    } catch (e) {
      error = 'Failed to load messages';
    } finally {
      loading = false;
    }
    await tick();
    scrollToBottom();

    // Connect SSE
    connectSSE(id);

    // Handle starter prompt from query param
    const starter = page.url.searchParams.get('starter');
    if (starter && messageList.length === 0) {
      // Remove from URL without navigation
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

    eventSource.addEventListener('error_event', (e) => {
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
    scrollToBottom();
  }

  async function sendMessage(content: string) {
    if (streaming) return;
    streaming = true;
    error = null;

    try {
      const assistantMsg = await messagesApi.send(sessionId, content);

      // Add user message (find by content from the list after POST, or re-fetch)
      const freshMessages = await messagesApi.list(sessionId);
      // Keep local streaming state for the last assistant message
      const serverAssistant = freshMessages.find(m => m.id === assistantMsg.id);
      messageList = freshMessages.map(m =>
        m.id === assistantMsg.id ? { ...m, content: serverAssistant?.content ?? '' } : m
      );

      // Update session title if it was auto-set
      await tick();
      scrollToBottom();
    } catch (e) {
      streaming = false;
      error = 'Failed to send message';
    }
  }

  function scrollToBottom() {
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
  <div bind:this={scrollEl} class="flex-1 overflow-y-auto px-4 py-6">
    <div class="max-w-3xl mx-auto">
      {#if loading}
        <div class="flex justify-center py-12">
          <div class="w-5 h-5 border-2 border-[#7c6ff7] border-t-transparent rounded-full animate-spin"></div>
        </div>
      {:else if error}
        <div class="text-center py-12">
          <p class="text-red-400 text-sm">{error}</p>
        </div>
      {:else if messageList.length === 0}
        <div class="flex flex-col items-center justify-center py-16 text-center gap-3">
          <p class="text-[#555] text-sm">Send a message to start the conversation</p>
        </div>
      {:else}
        {#each messageList as message (message.id)}
          <MessageBubble {message} />
        {/each}
      {/if}
    </div>
  </div>

  <!-- Input -->
  <ChatInput
    onsubmit={sendMessage}
    disabled={loading}
    {streaming}
    onstop={() => { streaming = false; closeSSE(); connectSSE(sessionId); }}
  />
</div>
