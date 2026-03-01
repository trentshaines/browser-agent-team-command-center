import { json, error } from '@sveltejs/kit';
import { getSession, getMessages, addMessage, updateMessage, pushSSE } from '../../../_store';
import type { Message } from '../../../_store';

const MOCK_RESPONSES = [
	"I'm a mock assistant. The real backend isn't connected yet, but the UI is working great!",
	'This is a simulated response. Your frontend is set up correctly and ready for backend integration.',
	'Mock response: everything looks good on the frontend side! Connect the backend when you are ready.',
	"I'm running in mock mode. Once the real backend is connected, I'll be able to actually browse the web for you.",
];

export function GET({ params }) {
	if (!getSession(params.id)) error(404, 'Not found');
	return json(getMessages(params.id));
}

export async function POST({ params, request }) {
	const sessionId = params.id;
	if (!getSession(sessionId)) error(404, 'Not found');

	const body = await request.json().catch(() => ({}));
	const content: string = body.content ?? '';

	const userMsg: Message = {
		id: crypto.randomUUID(),
		role: 'user',
		content,
		created_at: new Date().toISOString(),
	};
	addMessage(sessionId, userMsg);

	const assistantMsg: Message = {
		id: crypto.randomUUID(),
		role: 'assistant',
		content: '',
		created_at: new Date().toISOString(),
	};
	addMessage(sessionId, assistantMsg);

	const responseContent = MOCK_RESPONSES[Math.floor(Math.random() * MOCK_RESPONSES.length)];

	// Simulate async processing — push SSE done event after a short delay
	setTimeout(() => {
		updateMessage(sessionId, assistantMsg.id, responseContent);
		pushSSE(sessionId, 'done', { message_id: assistantMsg.id, content: responseContent });
	}, 800);

	return json(assistantMsg, { status: 201 });
}
