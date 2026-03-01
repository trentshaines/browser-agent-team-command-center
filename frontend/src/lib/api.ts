const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
    ...init,
  });

  if (res.status === 401) {
    // Try to refresh
    const refreshed = await tryRefresh();
    if (refreshed) {
      const res2 = await fetch(`${BASE}${path}`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
        ...init,
      });
      if (!res2.ok) throw new ApiError(res2.status, await res2.text());
      if (res2.status === 204) return undefined as T;
      return res2.json();
    }
    throw new ApiError(401, 'Unauthorized');
  }

  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    return res.ok;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Auth
export interface User {
  id: string;
  email: string;
  username: string;
  profile_image?: string;
  is_admin: boolean;
}

export const auth = {
  me: () => request<User>('/auth/me'),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  googleUrl: () => `${BASE}/auth/google`,
  googleCallback: (code: string) => request<{ access_token: string; refresh_token: string; token_type: string }>('/auth/google', {
    method: 'POST',
    body: JSON.stringify({ code }),
  }),
};

// Sessions
export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export const sessions = {
  list: () => request<Session[]>('/sessions'),
  create: (title = 'New Chat') => request<Session>('/sessions', {
    method: 'POST',
    body: JSON.stringify({ title }),
  }),
  get: (id: string) => request<Session>(`/sessions/${id}`),
  update: (id: string, title: string) => request<Session>(`/sessions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  }),
  delete: (id: string) => request<void>(`/sessions/${id}`, { method: 'DELETE' }),
};

// Messages
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

export const messages = {
  list: (sessionId: string) => request<Message[]>(`/sessions/${sessionId}/messages`),
  send: (sessionId: string, content: string) =>
    request<Message>(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
  streamUrl: (sessionId: string) => `${BASE}/sessions/${sessionId}/stream`,
};
