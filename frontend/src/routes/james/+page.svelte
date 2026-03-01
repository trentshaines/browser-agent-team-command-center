<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { PlusIcon } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import AgentTiles from "$lib/components/AgentTiles.svelte";
  import CreateProjectModal from "$lib/components/CreateProjectModal.svelte";
  import Logo from "$lib/components/Logo.svelte";
  import { tasks, streamUrl, type AgentPlan } from '$lib/api';
  import SpawnAgentModal from '$lib/components/SpawnAgentModal.svelte';
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';
  import type { WidgetMessage } from '$lib/chat/types';
  import { goto } from '$app/navigation';

  let createModalOpen = $state(false);
  let spawnModalOpen = $state(false);
  let sessionId = $state<string | null>(null);

  /** Push or remove ?session= in the URL without a full navigation. */
  function syncSessionToUrl(id: string | null) {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set('session', id);
    else url.searchParams.delete('session');
    goto(url.pathname + url.search, { replaceState: true, noScroll: true });
  }

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

  // Map backend LogAction to a short verb phrase for Slack-like chat messages
  function formatAgentAction(action: string, url: string | null): string {
    if (!url) {
      switch (action) {
        case 'thinking': return 'Thinking…';
        case 'output': return 'Finished';
        case 'retry': return 'Retrying…';
        case 'error': return 'Error encountered';
        case 'paused': return 'Paused';
        case 'resumed': return 'Resumed';
        case 'judge': return 'Evaluating results…';
        case 'correction': return 'Correcting…';
        default: return action;
      }
    }
    const host = (() => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } })();
    switch (action) {
      case 'navigation': return `Navigating to ${host}…`;
      case 'thinking': return `Thinking about ${host}…`;
      case 'output': return `Done with ${host}`;
      case 'handoff': return `Handing off to ${host}…`;
      default: return `${action} on ${host}`;
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
      // Backend sends { agents: [{ agent_id, status, result }] }
      if (data.agents && Array.isArray(data.agents)) {
        for (const a of data.agents) {
          agentRuns = agentRuns.map(r =>
            r.id === a.agent_id
              ? { ...r, status: a.status === 'complete' ? 'complete' : 'error', result: a.result }
              : r
          );
        }
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
          content: formatAgentAction(data.action, data.url),
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
    syncSessionToUrl(id);
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

  // On mount, restore session from URL query param and reconnect SSE.
  onMount(() => {
    const params = new URLSearchParams(window.location.search);
    const restored = params.get('session');
    if (restored) {
      sessionId = restored;
      connectSSE(restored);
    }
  });

  onDestroy(() => {
    closeSSE();
  });
</script>

<svelte:head>
  <title>James — Command Center</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col relative overflow-hidden">
  <!-- Animated gradient background -->
  <div class="absolute inset-0 z-0 overflow-hidden pointer-events-none" aria-hidden="true">
    <div class="gradient-orb orb-1"></div>
    <div class="gradient-orb orb-2"></div>
    <div class="gradient-orb orb-3"></div>
    <div class="gradient-orb orb-4"></div>
  </div>
  <header class="relative z-10 flex items-center justify-between border-b border-white/15 backdrop-blur-xl px-6 py-3">
    <div class="flex items-center gap-2.5">
      <Logo size={18} />
      <span class="text-sm font-semibold text-text">James</span>
    </div>
    <button
      onclick={() => (createModalOpen = true)}
      class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] transition-all"
    >
      <PlusIcon size={14} />
      New Project
    </button>
  </header>

  <main class="flex-1 relative z-10 overflow-hidden">
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

<style>
  .gradient-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(100px);
    opacity: 0.35;
    will-change: transform, opacity;
  }

  .orb-1 {
    width: 45vw;
    height: 45vw;
    top: -10%;
    left: -10%;
    background: radial-gradient(circle, rgba(145,70,255,0.4) 0%, rgba(145,70,255,0.15) 40%, transparent 70%);
    animation: drift-1 18s ease-in-out infinite;
  }

  .orb-2 {
    width: 40vw;
    height: 40vw;
    bottom: -5%;
    right: -8%;
    background: radial-gradient(circle, rgba(219,39,119,0.35) 0%, rgba(219,39,119,0.12) 40%, transparent 70%);
    animation: drift-2 22s ease-in-out infinite;
  }

  .orb-3 {
    width: 35vw;
    height: 35vw;
    top: 40%;
    right: 20%;
    background: radial-gradient(circle, rgba(37,99,235,0.35) 0%, rgba(37,99,235,0.12) 40%, transparent 70%);
    animation: drift-3 20s ease-in-out infinite;
  }

  .orb-4 {
    width: 30vw;
    height: 30vw;
    bottom: 15%;
    left: 25%;
    background: radial-gradient(circle, rgba(217,119,6,0.3) 0%, rgba(217,119,6,0.1) 40%, transparent 70%);
    animation: drift-4 24s ease-in-out infinite;
  }

  @keyframes drift-1 {
    0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.35; }
    25%      { transform: translate(8vw, 6vh) scale(1.08); opacity: 0.28; }
    50%      { transform: translate(3vw, 12vh) scale(0.95); opacity: 0.4; }
    75%      { transform: translate(-5vw, 4vh) scale(1.05); opacity: 0.3; }
  }

  @keyframes drift-2 {
    0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.35; }
    30%      { transform: translate(-10vw, -8vh) scale(1.1); opacity: 0.25; }
    60%      { transform: translate(-4vw, -14vh) scale(0.92); opacity: 0.38; }
    80%      { transform: translate(6vw, -4vh) scale(1.03); opacity: 0.32; }
  }

  @keyframes drift-3 {
    0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.3; }
    35%      { transform: translate(-12vw, 5vh) scale(1.12); opacity: 0.22; }
    65%      { transform: translate(-6vw, -8vh) scale(0.9); opacity: 0.38; }
    85%      { transform: translate(4vw, 2vh) scale(1.06); opacity: 0.28; }
  }

  @keyframes drift-4 {
    0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.25; }
    20%      { transform: translate(6vw, -10vh) scale(1.08); opacity: 0.2; }
    50%      { transform: translate(12vw, -4vh) scale(0.94); opacity: 0.32; }
    75%      { transform: translate(2vw, -8vh) scale(1.04); opacity: 0.22; }
  }
</style>
