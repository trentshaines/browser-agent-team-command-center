// In-memory mock backend store — shared across all mock API routes in dev server process

export interface User {
	id: string;
	email: string;
	username: string;
	profile_image?: string;
}

export interface Session {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
}

export interface Message {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	created_at: string;
}

export const MOCK_USER: User = {
	id: 'mock-user-1',
	email: 'dev@localhost',
	username: 'dev',
};

const sessionsMap = new Map<string, Session>();
const messagesMap = new Map<string, Message[]>();

// SSE queue: sessionId → pending raw SSE strings
const sseQueues = new Map<string, string[]>();

// Sessions

export function getSessions(): Session[] {
	return [...sessionsMap.values()].sort(
		(a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
	);
}

export function getSession(id: string): Session | undefined {
	return sessionsMap.get(id);
}

export function createSession(title = 'New Chat'): Session {
	const s: Session = {
		id: crypto.randomUUID(),
		title,
		created_at: new Date().toISOString(),
		updated_at: new Date().toISOString(),
	};
	sessionsMap.set(s.id, s);
	return s;
}

export function updateSession(id: string, title: string): Session | null {
	const s = sessionsMap.get(id);
	if (!s) return null;
	const updated = { ...s, title, updated_at: new Date().toISOString() };
	sessionsMap.set(id, updated);
	return updated;
}

export function deleteSession(id: string): void {
	sessionsMap.delete(id);
	messagesMap.delete(id);
	sseQueues.delete(id);
}

// Messages

export function getMessages(sessionId: string): Message[] {
	return messagesMap.get(sessionId) ?? [];
}

export function addMessage(sessionId: string, msg: Message): void {
	const list = messagesMap.get(sessionId) ?? [];
	messagesMap.set(sessionId, [...list, msg]);
}

export function updateMessage(sessionId: string, msgId: string, content: string): void {
	const list = messagesMap.get(sessionId) ?? [];
	messagesMap.set(sessionId, list.map((m) => (m.id === msgId ? { ...m, content } : m)));
}

// SSE

export function pushSSE(sessionId: string, event: string, data: unknown): void {
	const raw = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
	const q = sseQueues.get(sessionId) ?? [];
	sseQueues.set(sessionId, [...q, raw]);
}

export function popSSE(sessionId: string): string[] {
	const q = sseQueues.get(sessionId) ?? [];
	sseQueues.set(sessionId, []);
	return q;
}
