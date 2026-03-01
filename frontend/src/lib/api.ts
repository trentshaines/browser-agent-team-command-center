const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Sessions — client-side only (server.py doesn't manage sessions)
export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

// Message type (used by chat components for local state)
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

// Planning — decompose a goal into an agent team
export interface AgentPlan {
  name: string;
  task: string;
}

export interface PlanResponse {
  title: string;
  agents: AgentPlan[];
}

export const planning = {
  create: (prompt: string) =>
    request<PlanResponse>('/plan', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    }),
};

// Tasks — spawn agents via the orchestrator
export interface AgentSpec {
  name: string;
  task: string;
}

export interface TaskResponse {
  task_id: string;
}

export const tasks = {
  spawn: (sessionId: string, prompt: string, agents?: AgentSpec[]) =>
    request<TaskResponse>(`/sessions/${sessionId}/task`, {
      method: 'POST',
      body: JSON.stringify({ prompt, ...(agents ? { agents } : {}) }),
    }),
};

// SSE stream URL for a session
export function streamUrl(sessionId: string): string {
  return `${BASE}/sessions/${sessionId}/stream`;
}

// Agent run types (used by components for local state)
export interface AgentRunStep {
  step: number;
  url?: string | null;
  action?: string | null;
  thought?: string | null;
  evaluation?: string | null;
  success?: boolean | null;
  extracted_content?: string | null;
  error?: string | null;
}

export interface AgentRunRecord {
  id: string;
  task: string;
  status: 'running' | 'complete' | 'error';
  result?: string | null;
  total_steps: number;
  steps: AgentRunStep[];
}
