// In-memory mock backend store — shared across all mock API routes in dev server process

export interface Session {
	id: string;
	title: string;
	created_at: string;
	updated_at: string;
}

const sessionsMap = new Map<string, Session>();

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
	sseQueues.delete(id);
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
