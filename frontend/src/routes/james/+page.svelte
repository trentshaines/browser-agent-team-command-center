<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { PlusIcon } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import AgentTiles from "$lib/components/AgentTiles.svelte";
  import CreateProjectModal from "$lib/components/CreateProjectModal.svelte";
  import ProjectSwitcher from "$lib/components/ProjectSwitcher.svelte";
  import { tasks, streamUrl, narrate, type AgentPlan } from '$lib/api';
  import { useSessionMutations, migrateLocalStorageSessions } from '$lib/stores/sessions';
  import SpawnAgentModal from '$lib/components/SpawnAgentModal.svelte';
  import type { AgentRun } from '$lib/components/AgentRunPanel.svelte';
  import type { WidgetMessage } from '$lib/chat/types';
  import { goto } from '$app/navigation';
  import { useSafeQuery, useSafeConvexClient } from '$lib/convex';
  import { api } from '../../convex/_generated/api';
  import type { Id } from '../../convex/_generated/dataModel';

  let createModalOpen = $state(false);
  let spawnModalOpen = $state(false);
  let tileExpanded = $state(false);

  // Current session: we track both the Convex _id and the clientId (UUID used in URLs/SSE)
  let sessionConvexId = $state<Id<"sessions"> | null>(null);
  let sessionClientId = $state<string | null>(null);

  // Convex client + session mutations (null if Convex not configured)
  const convex = useSafeConvexClient();
  const sessionMutations = convex ? useSessionMutations() : null;

  // Sessions list from Convex (reactive query)
  const sessionsQuery = useSafeQuery(api.sessions.list, {});
  const sessions = $derived(sessionsQuery.data ?? []);

  // Messages from Convex for current session (skip when no session selected)
  const messagesQuery = useSafeQuery(
    api.messages.listBySession,
    () => sessionConvexId ? { sessionId: sessionConvexId } : 'skip',
  );
  const persistedMessages = $derived(messagesQuery.data ?? []);

  // Agent runs from Convex for current session (skip when no session selected)
  const agentRunsQuery = useSafeQuery(
    api.agentRuns.listBySession,
    () => sessionConvexId ? { sessionId: sessionConvexId } : 'skip',
  );
  const persistedAgentRuns = $derived(agentRunsQuery.data ?? []);

  /** Push or remove ?session= in the URL without a full navigation. */
  function syncSessionToUrl(id: string | null) {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set('session', id);
    else url.searchParams.delete('session');
    goto(url.pathname + url.search, { replaceState: true, noScroll: true });
  }

  // Chat state — local streaming buffer (messages being streamed that aren't persisted yet)
  let streamingMessages = $state<WidgetMessage[]>([]);
  let streaming = $state(false);
  let cancelledMessageId = $state<string | null>(null);
  let executiveSummary = $state('');

  // Merged message list: persisted + streaming buffer
  const messageList = $derived<WidgetMessage[]>([
    ...persistedMessages.map((m) => ({
      id: m.clientId,
      role: m.role as 'user' | 'assistant',
      content: m.content,
      created_at: new Date(m._creationTime).toISOString(),
      category: m.category as WidgetMessage['category'],
      senderName: m.senderName,
      agentId: m.agentId,
    })),
    ...streamingMessages,
  ]);

  // Agent state — merge persisted + live local state
  let liveAgentRuns = $state<AgentRun[]>([]);
  let agentFrames = $state<Record<string, {
    step: number | null;
    url: string | null;
    screenshot: string | null;
    done: boolean;
  }>>({});

  // Merged agent runs: persisted first, then any live-only runs
  const agentRuns: AgentRun[] = $derived.by(() => {
    const persisted = persistedAgentRuns.map((r) => ({
      id: r.clientId,
      name: r.name,
      task: r.task,
      status: r.status as AgentRun['status'],
      result: r.result ?? null,
      total_steps: r.totalSteps,
      steps: r.steps.map((s) => ({
        step: s.step,
        url: s.url ?? null,
        action: s.action ?? null,
        thought: s.thought ?? null,
        evaluation: s.evaluation ?? null,
        success: s.success ?? null,
        extracted_content: s.extractedContent ?? null,
        error: s.error ?? null,
      })),
      liveUrl: r.liveUrl ?? null,
    }));
    const persistedIds = new Set(persisted.map((r) => r.id));
    const liveOnly = liveAgentRuns.filter((r) => !persistedIds.has(r.id));
    return [...persisted, ...liveOnly];
  });

  // Agent state
  let currentTaskId = $state<string | null>(null);

  // Map agent_run_id → agent name for chat attribution
  const agentNames = new Map<string, string>();
  // Map agent_run_id → task description
  const agentTasks = new Map<string, string>();
  // Map agent clientId → Convex _id (for mutations)
  const agentConvexIds = new Map<string, Id<"agentRuns">>();

  // --- Log accumulator + narration timer ---
  const agentLogBuffers = new Map<string, string[]>();
  const narrationCursors = new Map<string, number>();
  let narrateTimer: ReturnType<typeof setInterval> | null = null;
  const NARRATE_INTERVAL = 8_000;
  const MIN_NEW_LOGS = 3;

  function formatLogLine(action: string, url: string | null): string {
    const host = url ? (() => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } })() : null;
    if (host) return `${action} on ${host}`;
    return action;
  }

  function accumulateLog(agentId: string, action: string, url: string | null) {
    const line = formatLogLine(action, url);
    const buf = agentLogBuffers.get(agentId);
    if (buf) buf.push(line);
    else agentLogBuffers.set(agentId, [line]);
  }

  async function persistMessage(msg: WidgetMessage) {
    if (!convex || !sessionConvexId) return;
    await convex.mutation(api.messages.send, {
      sessionId: sessionConvexId,
      clientId: msg.id,
      role: msg.role,
      content: msg.content,
      category: msg.category,
      senderName: msg.senderName,
      agentId: msg.agentId,
    });
  }

  async function narrateAgent(agentId: string, opts?: { completed?: boolean; result?: string }) {
    const logs = agentLogBuffers.get(agentId) ?? [];
    const cursor = narrationCursors.get(agentId) ?? 0;
    const newLogs = logs.slice(cursor);
    if (newLogs.length === 0 && !opts?.completed) return;

    const name = agentNames.get(agentId) ?? 'Agent';
    const task = agentTasks.get(agentId) ?? '';
    narrationCursors.set(agentId, logs.length);

    const msg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      senderName: name,
      category: opts?.completed ? 'completion' : 'status',
      agentId,
    };

    try {
      const { message } = await narrate.synthesize({
        agent_name: name,
        task,
        logs: newLogs,
        completed: opts?.completed,
        result: opts?.result,
      });
      msg.content = message;
    } catch {
      msg.content = opts?.completed
        ? (opts.result ? `Done — ${opts.result.slice(0, 200)}` : 'Finished')
        : newLogs[newLogs.length - 1] ?? '';
    }

    if (msg.content) {
      // Persist to Convex (not to streaming buffer — Convex query will pick it up)
      await persistMessage(msg);
    }
  }

  async function narrationSweep() {
    for (const [agentId, logs] of agentLogBuffers) {
      const cursor = narrationCursors.get(agentId) ?? 0;
      if (logs.length - cursor >= MIN_NEW_LOGS) {
        await narrateAgent(agentId);
      }
    }
  }

  function startNarrationTimer() {
    if (narrateTimer) return;
    narrateTimer = setInterval(narrationSweep, NARRATE_INTERVAL);
  }

  function stopNarrationTimer() {
    if (narrateTimer) { clearInterval(narrateTimer); narrateTimer = null; }
  }

  function resetNarrationState() {
    stopNarrationTimer();
    agentLogBuffers.clear();
    narrationCursors.clear();
    sseEventLog = [];
  }

  // --- SSE debug log: accumulate all raw events for later inspection ---
  let sseEventLog: { ts: string; event: string; data: unknown }[] = [];

  function logSSEEvent(eventType: string, data: unknown) {
    sseEventLog.push({ ts: new Date().toISOString(), event: eventType, data });
  }

  /** Download the accumulated SSE log as a JSON file. Call from browser console: window.__dumpSSELog() */
  function dumpSSELog() {
    const blob = new Blob([JSON.stringify(sseEventLog, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sse-log-${sessionClientId ?? 'unknown'}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  let eventSource: EventSource | null = null;

  function connectSSE(id: string): Promise<void> {
    const url = streamUrl(id);
    eventSource = new EventSource(url);

    const ready = new Promise<void>((resolve) => {
      eventSource!.addEventListener('open', () => { console.log('[SSE] connected to', url); resolve(); }, { once: true });
      eventSource!.addEventListener('error', (e) => { console.warn('[SSE] error/reconnect', eventSource?.readyState, e); resolve(); }, { once: true });
    });

    eventSource.onmessage = (e) => {
      console.log('[SSE] message (unnamed):', e.data?.slice(0, 120));
      try { logSSEEvent('message', JSON.parse(e.data)); } catch { logSSEEvent('message', e.data); }
    };

    eventSource.addEventListener('delta', (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('delta', data);
      if (data.message_id === cancelledMessageId) return;
      const last = streamingMessages[streamingMessages.length - 1];
      if (last?.id === data.message_id) {
        streamingMessages[streamingMessages.length - 1] = { ...last, content: last.content + data.delta };
      } else {
        const idx = streamingMessages.findIndex(m => m.id === data.message_id);
        if (idx >= 0) streamingMessages[idx] = { ...streamingMessages[idx], content: streamingMessages[idx].content + data.delta };
      }
    });

    eventSource.addEventListener('done', async (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('done', data);
      if (data.agents && Array.isArray(data.agents)) {
        for (const a of data.agents) {
          // Update local state
          liveAgentRuns = liveAgentRuns.map(r =>
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

      // Persist any streaming messages that were being buffered
      for (const msg of streamingMessages) {
        await persistMessage(msg);
      }
      streamingMessages = [];
    });

    eventSource.addEventListener('summary', (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('summary', data);
      console.log('[SSE] summary:', data.summary?.slice(0, 100));
      if (data.summary) {
        executiveSummary = data.summary;
      }
    });

    eventSource.addEventListener('agent_event', async (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('agent_event', data);
      console.log('[SSE] agent_event:', data.type, data);
      if (data.type === 'agent_spawned') {
        const existing = liveAgentRuns.find(r => r.id === data.agent_id)
          || persistedAgentRuns.find(r => r.clientId === data.agent_id);
        if (existing) {
          // Re-spawn: flip agent back to running
          liveAgentRuns = liveAgentRuns.map(r =>
            r.id === data.agent_id ? { ...r, status: 'running' as const } : r
          );
          const convexId = agentConvexIds.get(data.agent_id);
          if (convex && convexId) {
            await convex.mutation(api.agentRuns.updateStatus, {
              id: convexId,
              status: 'running',
            });
          }
          // Reset narration cursor so new steps get narrated
          narrationCursors.set(data.agent_id, agentLogBuffers.get(data.agent_id)?.length ?? 0);
          startNarrationTimer();
          return;
        }
        const name = data.name ?? `Browser ${liveAgentRuns.length + persistedAgentRuns.length + 1}`;
        agentNames.set(data.agent_id, name);
        agentTasks.set(data.agent_id, data.task);
        liveAgentRuns = [...liveAgentRuns, {
          id: data.agent_id,
          name,
          task: data.task,
          status: 'running',
          steps: [],
          liveUrl: data.live_url ?? null,
        }];

        // Persist agent run to Convex
        if (convex && sessionConvexId) {
          const convexId = await convex.mutation(api.agentRuns.create, {
            sessionId: sessionConvexId,
            clientId: data.agent_id,
            name,
            task: data.task,
            status: 'running',
            liveUrl: data.live_url ?? undefined,
          });
          agentConvexIds.set(data.agent_id, convexId);
        }

        // Persist spawn message
        const spawnMsg: WidgetMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `On it — ${data.task}`,
          created_at: new Date().toISOString(),
          senderName: name,
          category: 'spawn',
          agentId: data.agent_id,
        };
        await persistMessage(spawnMsg);
        startNarrationTimer();
      } else if (data.type === 'agent_complete') {
        liveAgentRuns = liveAgentRuns.map(r =>
          r.id === data.agent_run_id
            ? { ...r, status: data.result ? 'complete' : 'error', result: data.result, total_steps: data.total_steps }
            : r
        );

        // Persist status update
        const convexId = agentConvexIds.get(data.agent_run_id);
        if (convex && convexId) {
          await convex.mutation(api.agentRuns.updateStatus, {
            id: convexId,
            status: data.result ? 'complete' : 'error',
            result: data.result ?? undefined,
            totalSteps: data.total_steps ?? undefined,
          });
        }

        await narrateAgent(data.agent_run_id, {
          completed: true,
          result: data.result ?? undefined,
        });
      }
    });

    eventSource.addEventListener('agent_log', async (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('agent_log', data);
      console.log('[SSE] agent_log:', data.action, data.url);
      const runIdx = liveAgentRuns.findIndex(r => r.id === data.agent_run_id);
      if (runIdx >= 0) {
        if (liveAgentRuns[runIdx].steps.some(s => s.step === data.step)) return;
        liveAgentRuns[runIdx] = { ...liveAgentRuns[runIdx], steps: [...liveAgentRuns[runIdx].steps, data] };
        accumulateLog(data.agent_run_id, data.action, data.url);

        // Persist step to Convex
        const convexId = agentConvexIds.get(data.agent_run_id);
        if (convex && convexId) {
          await convex.mutation(api.agentRuns.addStep, {
            agentRunId: convexId,
            step: data.step ?? liveAgentRuns[runIdx].steps.length,
            url: data.url ?? undefined,
            action: data.action ?? undefined,
            thought: data.thought ?? undefined,
            evaluation: data.evaluation ?? undefined,
            success: data.success ?? undefined,
            extractedContent: data.extracted_content ?? undefined,
            error: data.error ?? undefined,
          });
        }
      }
    });

    eventSource.addEventListener('handoff', async (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('handoff', data);
      console.log('[SSE] handoff:', data.agent_id, data.message);
      liveAgentRuns = liveAgentRuns.map(r =>
        r.id === data.agent_id ? { ...r, status: 'paused' as const, handoffMessage: data.message ?? null } : r
      );

      // Persist paused status
      const convexId = agentConvexIds.get(data.agent_id);
      if (convex && convexId) {
        await convex.mutation(api.agentRuns.updateStatus, {
          id: convexId,
          status: 'paused',
        });
      }

      const name = agentNames.get(data.agent_id) ?? 'Agent';
      const handoffMsg: WidgetMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.message ?? 'Needs human help',
        created_at: new Date().toISOString(),
        senderName: name,
        category: 'blocked',
        agentId: data.agent_id,
      };
      await persistMessage(handoffMsg);
    });

    eventSource.addEventListener('human_input_received', async (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('human_input_received', data);
      console.log('[SSE] human_input_received:', data.agent_id);
      liveAgentRuns = liveAgentRuns.map(r =>
        r.id === data.agent_id ? { ...r, status: 'running' as const, handoffMessage: null } : r
      );
      const convexId = agentConvexIds.get(data.agent_id);
      if (convex && convexId) {
        await convex.mutation(api.agentRuns.updateStatus, {
          id: convexId,
          status: 'running',
        });
      }
    });

    eventSource.addEventListener('agent_frame', (e) => {
      const data = JSON.parse(e.data);
      logSSEEvent('agent_frame', { agent_id: data.agent_id, step: data.step, url: data.url, screenshot_len: data.screenshot?.length });
      console.log('[SSE] agent_frame:', data.agent_id, 'step', data.step, 'screenshot bytes:', data.screenshot?.length);
      if (!liveAgentRuns.some(r => r.id === data.agent_id) && !persistedAgentRuns.some(r => r.clientId === data.agent_id)) {
        console.warn('[SSE] agent_frame dropped — agent not found');
        return;
      }
      agentFrames = { ...agentFrames, [data.agent_id]: {
        step: data.step,
        url: data.url,
        screenshot: data.screenshot,
        done: false,
      }};
    });

    eventSource.addEventListener('error_event', (e) => {
      try { logSSEEvent('error_event', JSON.parse(e.data)); } catch { logSSEEvent('error_event', null); }
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
    if (!sessionClientId || !sessionConvexId) return;
    if (streaming) {
      const last = streamingMessages[streamingMessages.length - 1];
      if (last?.role === 'assistant') cancelledMessageId = last.id;
      streaming = false;
      closeSSE();
      // Persist any leftover streaming messages
      for (const msg of streamingMessages) {
        await persistMessage(msg);
      }
      streamingMessages = [];
      await connectSSE(sessionClientId);
    }
    streaming = true;
    cancelledMessageId = null;
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      category: 'user',
    };
    // Persist user message immediately
    await persistMessage(userMsg);
    await tick();

    // Check for @-mention reprompt: @AgentName <instruction>
    // Try to match a known agent name after the leading @
    if (content.startsWith('@') && currentTaskId) {
      const rest = content.slice(1); // strip leading @
      let matchedAgentId: string | null = null;
      let instruction = '';
      // Check all known names, longest first to avoid partial matches
      const entries = [...agentNames.entries()].sort((a, b) => b[1].length - a[1].length);
      for (const [id, name] of entries) {
        if (rest.toLowerCase().startsWith(name.toLowerCase())) {
          const after = rest.slice(name.length);
          // Must be followed by whitespace or end of string
          if (after.length === 0 || /^[\s\u00A0]/.test(after)) {
            matchedAgentId = id;
            instruction = after.replace(/^[\s\u00A0]+/, '');
            break;
          }
        }
      }
      if (matchedAgentId && instruction) {
        try {
          await tasks.reprompt(currentTaskId, matchedAgentId, instruction);
        } catch (e) {
          console.error('Failed to reprompt agent:', e);
          streaming = false;
        }
        return;
      }
    }

    try {
      const resp = await tasks.spawn(sessionClientId, content);
      currentTaskId = resp.task_id;
    } catch {
      streaming = false;
    }
  }

  function stopStreaming() {
    const last = streamingMessages[streamingMessages.length - 1];
    if (last?.role === 'assistant') cancelledMessageId = last.id;
    streaming = false;
    const id = sessionClientId;
    closeSSE();
    if (id) connectSSE(id);
  }

  async function handleResumeAgent(agentId: string) {
    if (!currentTaskId) return;
    try {
      await tasks.respond(currentTaskId, agentId, '');
    } catch (e) {
      console.error('Failed to resume agent:', e);
    }
  }

  async function handleSpawn(name: string, task: string) {
    if (!sessionClientId || !sessionConvexId) return;
    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: task,
      created_at: new Date().toISOString(),
      category: 'user',
    };
    await persistMessage(userMsg);
    try {
      const resp = await tasks.spawn(sessionClientId, task, [{ name, task }]);
      currentTaskId = resp.task_id;
    } catch (e) {
      console.error('Failed to spawn agent:', e);
    }
  }

  async function switchSession(clientId: string) {
    if (clientId === sessionClientId) return;
    const session = sessions.find(s => s.clientId === clientId);
    if (!session) return;

    resetNarrationState();
    streamingMessages = [];
    liveAgentRuns = [];
    agentFrames = {};
    streaming = false;
    cancelledMessageId = null;
    currentTaskId = null;
    executiveSummary = '';
    agentConvexIds.clear();
    closeSSE();

    sessionConvexId = session._id;
    sessionClientId = clientId;
    syncSessionToUrl(clientId);
    await sessionMutations?.bumpUpdated(session._id);
    await connectSSE(clientId);
  }

  async function deleteSession(clientId: string) {
    const session = sessions.find(s => s.clientId === clientId);
    if (!session) return;
    await sessionMutations?.remove(session._id);
    if (clientId === sessionClientId) {
      resetNarrationState();
      closeSSE();
      sessionConvexId = null;
      sessionClientId = null;
      currentTaskId = null;
      streamingMessages = [];
      liveAgentRuns = [];
      agentFrames = {};
      streaming = false;
      cancelledMessageId = null;
      executiveSummary = '';
      syncSessionToUrl(null);
    }
  }

  async function onProjectLaunched(clientId: string, goal: string, agents: AgentPlan[]) {
    // The session was already created in CreateProjectModal — find it
    // We need to wait briefly for the Convex query to pick it up
    let session = sessions.find(s => s.clientId === clientId);
    // If not yet in query results, look it up directly
    if (!session && convex) {
      const looked = await convex.query(api.sessions.getByClientId, { clientId });
      if (looked) session = looked;
    }
    if (!session) return;

    resetNarrationState();
    sessionConvexId = session._id;
    sessionClientId = clientId;
    syncSessionToUrl(clientId);
    createModalOpen = false;
    streamingMessages = [];
    liveAgentRuns = [];
    agentFrames = {};
    streaming = false;
    cancelledMessageId = null;
    currentTaskId = null;
    executiveSummary = '';
    agentConvexIds.clear();
    closeSSE();
    await connectSSE(clientId);
    await sessionMutations?.bumpUpdated(session._id);

    const userMsg: WidgetMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: goal,
      created_at: new Date().toISOString(),
      category: 'user',
    };
    await persistMessage(userMsg);
    await tick();
    try {
      streaming = true;
      const resp = await tasks.spawn(clientId, goal, agents);
      currentTaskId = resp.task_id;
    } catch {
      streaming = false;
    }
  }

  // On mount: migrate localStorage + restore session from URL
  onMount(async () => {
    (window as any).__dumpSSELog = dumpSSELog;
    if (convex) {
      await migrateLocalStorageSessions(convex);
    }
    const params = new URLSearchParams(window.location.search);
    const restored = params.get('session');
    if (restored) {
      sessionClientId = restored;
      // Look up Convex ID for this session
      if (convex) {
        const session = await convex.query(api.sessions.getByClientId, { clientId: restored });
        if (session) {
          sessionConvexId = session._id;
        }
      }
      connectSSE(restored);
    }
  });

  onDestroy(() => {
    resetNarrationState();
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
  <header class="relative z-20 flex items-center justify-between border-b border-white/15 backdrop-blur-xl px-6 py-3">
    <ProjectSwitcher
      {sessions}
      currentSessionId={sessionClientId}
      onSwitch={switchSession}
      onDelete={deleteSession}
    />
    <button
      onclick={() => (createModalOpen = true)}
      class="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-accent text-white hover:opacity-90 active:scale-[0.97] transition-all"
    >
      <PlusIcon size={14} />
      New Project
    </button>
  </header>

  <main class="flex-1 relative z-10 overflow-hidden">
    {#if agentRuns.length > 0}
      <AgentTiles runs={agentRuns} frames={agentFrames} fullscreen messages={messageList} onExpandChange={(v) => (tileExpanded = v)} onResumeAgent={handleResumeAgent} />
    {:else if sessionClientId}
      <div class="flex items-center justify-center h-full">
        <p class="text-text-faint text-sm select-none">Agent windows will appear here</p>
      </div>
    {/if}
  </main>

  {#if !tileExpanded}
    <FloatingChatWidget
      messages={messageList}
      {streaming}
      agentRuns={agentRuns}
      onSend={sendMessage}
      disabled={!sessionClientId}
      {executiveSummary}
      onSpawnAgent={sessionClientId ? () => (spawnModalOpen = true) : undefined}
    />
  {/if}
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
