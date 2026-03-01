<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { PlusIcon } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import AgentTiles from "$lib/components/AgentTiles.svelte";
  import CreateProjectModal from "$lib/components/CreateProjectModal.svelte";
  import { auth, messages as messagesApi } from '$lib/api';
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';
  import type { WidgetMessage } from '$lib/chat/types';

  let authenticated = $state(false);
  let authError = $state<string | null>(null);
  let createModalOpen = $state(false);
  let sessionId = $state<string | null>(null);

  onMount(async () => {
    try {
      await auth.me();
      authenticated = true;
    } catch {
      try {
        await auth.devLogin();
        authenticated = true;
      } catch (e) {
        authError = e instanceof Error ? e.message : 'Failed to authenticate';
      }
    }
  });

  // Chat state
  let messageList = $state<WidgetMessage[]>([]);
  let streaming = $state(false);
  let cancelledMessageId = $state<string | null>(null);

  // Agent state
  let agentRuns = $state<AgentRun[]>([]);
  let agentFrames = $state<Record<string, {
    step: number | null;
    url: string | null;
    screenshot: string | null;
    done: boolean;
  }>>({});

  let eventSource: EventSource | null = null;

  function connectSSE(id: string): Promise<void> {
    const url = messagesApi.streamUrl(id);
    eventSource = new EventSource(url, { withCredentials: true });

    const ready = new Promise<void>((resolve) => {
      eventSource!.addEventListener('open', () => resolve(), { once: true });
      eventSource!.addEventListener('error', () => resolve(), { once: true });
    });

    eventSource.addEventListener('delta', (e) => {
      const data = JSON.parse(e.data);
      if (data.message_id === cancelledMessageId) return;
      const last = messageList[messageList.length - 1];
      if (last?.id === data.message_id) {
        messageList[messageList.length - 1] = { ...last, content: last.content + data.delta };
      } else {
        const idx = messageList.findIndex(m => m.id === data.message_id);
        if (idx >= 0) messageList[idx] = { ...messageList[idx], content: messageList[idx].content + data.delta };
      }
    });

    eventSource.addEventListener('done', (e) => {
      const data = JSON.parse(e.data);
      if (data.message_id !== cancelledMessageId) {
        const idx = messageList.findIndex(m => m.id === data.message_id);
        if (idx >= 0) messageList[idx] = { ...messageList[idx], content: data.content };
      }
      streaming = false;
      agentFrames = Object.fromEntries(
        Object.entries(agentFrames).map(([aid, f]) => [aid, { ...f, done: true }])
      );
    });

    eventSource.addEventListener('agent_event', (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'agent_spawned') {
        if (agentRuns.some(r => r.id === data.agent_id)) return;
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
    });

    eventSource.addEventListener('agent_log', (e) => {
      const data = JSON.parse(e.data);
      const runIdx = agentRuns.findIndex(r => r.id === data.agent_run_id);
      if (runIdx >= 0) {
        if (agentRuns[runIdx].steps.some(s => s.step === data.step)) return;
        agentRuns[runIdx] = { ...agentRuns[runIdx], steps: [...agentRuns[runIdx].steps, data] };
      }
    });

    eventSource.addEventListener('agent_frame', (e) => {
      const data = JSON.parse(e.data);
      if (!agentRuns.some(r => r.id === data.agent_id)) return;
      agentFrames[data.agent_id] = {
        step: data.step,
        url: data.url,
        screenshot: data.screenshot,
        done: false,
      };
    });

    eventSource.addEventListener('error_event', () => {
      streaming = false;
    });

    eventSource.onerror = () => {
      if (eventSource?.readyState === EventSource.CLOSED) streaming = false;
    };

    return ready;
  }

  function closeSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  async function sendMessage(content: string) {
    if (!sessionId) return;
    if (streaming) {
      const last = messageList[messageList.length - 1];
      if (last?.role === 'assistant') cancelledMessageId = last.id;
      streaming = false;
      closeSSE();
      await connectSSE(sessionId);
    }
    streaming = true;
    cancelledMessageId = null;
    try {
      const assistantMsg = await messagesApi.send(sessionId, content);
      const userMsg: WidgetMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };
      messageList = [...messageList, userMsg, { ...assistantMsg, content: '' }];
      await tick();
    } catch {
      streaming = false;
    }
  }

  function stopStreaming() {
    const last = messageList[messageList.length - 1];
    if (last?.role === 'assistant') cancelledMessageId = last.id;
    streaming = false;
    const id = sessionId;
    closeSSE();
    if (id) connectSSE(id);
  }

  async function onProjectLaunched(id: string, goal: string) {
    // Reset state for new session
    sessionId = id;
    createModalOpen = false;
    messageList = [];
    agentRuns = [];
    agentFrames = {};
    streaming = false;
    cancelledMessageId = null;
    closeSSE();
    await connectSSE(id);
    await sendMessage(goal);
  }

  onDestroy(() => {
    closeSSE();
  });
</script>

<svelte:head>
  <title>Windows — James</title>
</svelte:head>

{#if authError}
  <div class="min-h-screen bg-background flex items-center justify-center">
    <p class="text-red-500 text-sm">Auth failed: {authError}</p>
  </div>
{:else if !authenticated}
  <div class="min-h-screen bg-background flex items-center justify-center">
    <div class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
  </div>
{:else}
<div class="min-h-screen bg-background flex flex-col">
  <header class="relative flex items-center justify-center border-b border-border-subtle bg-surface/50 px-6 py-4">
    <span class="font-semibold text-text">Windows</span>
    <button
      onclick={() => (createModalOpen = true)}
      class="absolute right-6 flex items-center justify-center w-8 h-8 rounded-lg text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
      aria-label="New project"
    >
      <PlusIcon size={18} />
    </button>
  </header>

  <main class="flex-1 relative overflow-hidden">
    {#if Object.keys(agentFrames).length > 0}
      <AgentTiles frames={agentFrames} fullscreen messages={messageList} />
    {:else if agentRuns.some(r => r.status === 'running')}
      <div class="flex items-center justify-center h-full gap-3">
        <div class="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
        <span class="text-sm text-text-muted">
          {agentRuns.filter(r => r.status === 'running').length} agent{agentRuns.filter(r => r.status === 'running').length !== 1 ? 's' : ''} starting…
        </span>
      </div>
    {:else if sessionId}
      <div class="flex items-center justify-center h-full">
        <p class="text-text-faint text-sm select-none">Agent windows will appear here</p>
      </div>
    {:else}
      <div class="flex flex-col items-center justify-center h-full gap-3 text-center">
        <p class="text-text-faint text-sm select-none">Create a project to get started</p>
        <button
          onclick={() => (createModalOpen = true)}
          class="text-accent text-sm hover:underline"
        >
          New Project
        </button>
      </div>
    {/if}
  </main>

  <FloatingChatWidget
    messages={messageList}
    {streaming}
    onSend={sendMessage}
    onStop={stopStreaming}
    disabled={!sessionId}
  />
</div>

<CreateProjectModal
  isOpen={createModalOpen}
  onClose={() => (createModalOpen = false)}
  onLaunch={onProjectLaunched}
/>
{/if}
