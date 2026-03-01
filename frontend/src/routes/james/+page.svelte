<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { PlusIcon } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import AgentTiles from "$lib/components/AgentTiles.svelte";
  import CreateProjectModal from "$lib/components/CreateProjectModal.svelte";
  import Logo from "$lib/components/Logo.svelte";
  import { tasks, streamUrl, type AgentPlan, type TaskResponse } from '$lib/api';
  import SpawnAgentModal from '$lib/components/SpawnAgentModal.svelte';
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';
  import type { WidgetMessage } from '$lib/chat/types';

  let createModalOpen = $state(false);
  let spawnModalOpen = $state(false);
  let sessionId = $state<string | null>(null);

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

  // Map agent_run_id → agent name for chat attribution
  const agentNames = new Map<string, string>();

  // Map action_type to a short verb phrase for Slack-like chat messages
  function formatAgentAction(actionType: string, url: string): string {
    const host = (() => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } })();
    switch (actionType) {
      case 'navigate': return `Navigating to ${host}…`;
      case 'click': return `Clicked on ${host}`;
      case 'extract': return `Extracting data from ${host}`;
      case 'type': return `Typing on ${host}`;
      case 'scroll': return `Scrolling on ${host}`;
      case 'wait': return `Waiting…`;
      default: return `${actionType} on ${host}`;
    }
  }

  let eventSource: EventSource | null = null;

  function connectSSE(id: string): Promise<void> {
    const url = streamUrl(id);
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
        const name = data.name ?? `Browser ${agentRuns.length + 1}`;
        agentNames.set(data.agent_id, name);
        agentRuns = [...agentRuns, {
          id: data.agent_id,
          name,
          task: data.task,
          status: 'running',
          steps: [],
        }];
        // Post spawn as a chat message
        messageList = [...messageList, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Starting: ${data.task}`,
          created_at: new Date().toISOString(),
          senderName: name,
        }];
      } else if (data.type === 'agent_complete') {
        agentRuns = agentRuns.map(r =>
          r.id === data.agent_run_id
            ? { ...r, status: data.result ? 'complete' : 'error', result: data.result, total_steps: data.total_steps }
            : r
        );
        const name = agentNames.get(data.agent_run_id) ?? 'Agent';
        messageList = [...messageList, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.result ? `Done — ${data.result}` : 'Failed',
          created_at: new Date().toISOString(),
          senderName: name,
        }];
      }
    });

    eventSource.addEventListener('agent_log', (e) => {
      const data = JSON.parse(e.data);
      const runIdx = agentRuns.findIndex(r => r.id === data.agent_run_id);
      if (runIdx >= 0) {
        if (agentRuns[runIdx].steps.some(s => s.step === data.step)) return;
        agentRuns[runIdx] = { ...agentRuns[runIdx], steps: [...agentRuns[runIdx].steps, data] };
        // Post step as a short chat message
        const name = agentNames.get(data.agent_run_id) ?? 'Agent';
        messageList = [...messageList, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: formatAgentAction(data.action_type, data.url),
          created_at: new Date().toISOString(),
          senderName: name,
        }];
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
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    };
    messageList = [...messageList, userMsg];
    await tick();
    try {
      await tasks.spawn(sessionId, content);
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

  async function handleSpawn(name: string, task: string) {
    if (!sessionId) return;
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: task,
      created_at: new Date().toISOString(),
    };
    messageList = [...messageList, userMsg];
    try {
      await tasks.spawn(sessionId, task, [{ name, task }]);
    } catch (e) {
      console.error('Failed to spawn agent:', e);
    }
  }

  async function onProjectLaunched(id: string, goal: string, agents: AgentPlan[]) {
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

    // Use direct task spawning with the confirmed agent team
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: goal,
      created_at: new Date().toISOString(),
    };
    messageList = [...messageList, userMsg];
    await tick();
    try {
      streaming = true;
      await tasks.spawn(id, goal, agents);
    } catch {
      streaming = false;
    }
  }

  onDestroy(() => {
    closeSSE();
  });
</script>

<svelte:head>
  <title>James — Command Center</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">
  <header class="flex items-center justify-between border-b border-border-subtle bg-surface/50 px-6 py-3">
    <div class="flex items-center gap-2.5">
      <Logo size={18} />
      <span class="text-sm font-semibold text-text">James</span>
    </div>
    <button
      onclick={() => (createModalOpen = true)}
      class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] transition-all"
    >
      <PlusIcon size={14} />
      New Project
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
    {agentRuns}
    onSend={sendMessage}
    onStop={stopStreaming}
    disabled={!sessionId}
    onSpawnAgent={sessionId ? () => (spawnModalOpen = true) : undefined}
  />
</div>

<CreateProjectModal
  isOpen={createModalOpen}
  onClose={() => (createModalOpen = false)}
  onLaunch={onProjectLaunched}
/>

<SpawnAgentModal
  isOpen={spawnModalOpen}
  onClose={() => (spawnModalOpen = false)}
  onSpawn={handleSpawn}
/>
