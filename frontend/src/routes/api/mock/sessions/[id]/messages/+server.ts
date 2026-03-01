import { json, error } from '@sveltejs/kit';
import { getSession, getMessages, addMessage, updateMessage, pushSSE } from '../../../_store';
import type { Message } from '../../../_store';

const MOCK_RESPONSES = [
	"I'm a mock assistant. The real backend isn't connected yet, but the UI is working great!",
	'This is a simulated response. Your frontend is set up correctly and ready for backend integration.',
	'Mock response: everything looks good on the frontend side! Connect the backend when you are ready.',
	"I'm running in mock mode. Once the real backend is connected, I'll be able to actually browse the web for you.",
];

// Minimal 2x2 JPEG placeholders (~300 bytes each) as base64 data URIs.
// These are tiny colored squares used to simulate distinct screenshots.
const SCREENSHOT_BLUE =
	'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AMAAB/9k=';
const SCREENSHOT_GREEN =
	'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAABv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AmAAB/9k=';
const SCREENSHOT_RED =
	'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAABf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AlAAB/9k=';

const MOCK_STEPS = [
	{ url: 'https://example.com', action_type: 'navigate', thought: 'Navigating to the target page', screenshot: SCREENSHOT_BLUE },
	{ url: 'https://example.com/results', action_type: 'click', thought: 'Clicking the search button', screenshot: SCREENSHOT_GREEN },
	{ url: 'https://example.com/results#data', action_type: 'extract', thought: 'Extracting data from the page', screenshot: SCREENSHOT_RED },
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
	const agentId = crypto.randomUUID();

	// t=300ms — agent spawned → tile spinner appears
	setTimeout(() => {
		pushSSE(sessionId, 'agent_event', {
			type: 'agent_spawned',
			agent_id: agentId,
			name: 'Mock Browser Agent',
			task: content || 'Browse the web',
		});
	}, 300);

	// t=600ms — agent_log step 1
	setTimeout(() => {
		pushSSE(sessionId, 'agent_log', {
			agent_run_id: agentId,
			step: 1,
			url: MOCK_STEPS[0].url,
			action_type: MOCK_STEPS[0].action_type,
			thought: MOCK_STEPS[0].thought,
			success: true,
		});
	}, 600);

	// t=800ms — agent_frame step 1 → tile shows first screenshot
	setTimeout(() => {
		pushSSE(sessionId, 'agent_frame', {
			agent_id: agentId,
			step: 1,
			url: MOCK_STEPS[0].url,
			screenshot: MOCK_STEPS[0].screenshot,
		});
	}, 800);

	// t=2300ms — agent_log step 2
	setTimeout(() => {
		pushSSE(sessionId, 'agent_log', {
			agent_run_id: agentId,
			step: 2,
			url: MOCK_STEPS[1].url,
			action_type: MOCK_STEPS[1].action_type,
			thought: MOCK_STEPS[1].thought,
			success: true,
		});
	}, 2300);

	// t=2500ms — agent_frame step 2 → tile image updates
	setTimeout(() => {
		pushSSE(sessionId, 'agent_frame', {
			agent_id: agentId,
			step: 2,
			url: MOCK_STEPS[1].url,
			screenshot: MOCK_STEPS[1].screenshot,
		});
	}, 2500);

	// t=4000ms — agent_log step 3
	setTimeout(() => {
		pushSSE(sessionId, 'agent_log', {
			agent_run_id: agentId,
			step: 3,
			url: MOCK_STEPS[2].url,
			action_type: MOCK_STEPS[2].action_type,
			thought: MOCK_STEPS[2].thought,
			success: true,
		});
	}, 4000);

	// t=4200ms — agent_frame step 3 → tile image updates
	setTimeout(() => {
		pushSSE(sessionId, 'agent_frame', {
			agent_id: agentId,
			step: 3,
			url: MOCK_STEPS[2].url,
			screenshot: MOCK_STEPS[2].screenshot,
		});
	}, 4200);

	// t=5200ms — agent complete
	setTimeout(() => {
		pushSSE(sessionId, 'agent_event', {
			type: 'agent_complete',
			agent_run_id: agentId,
			result: 'Successfully extracted data from the page',
			total_steps: 3,
		});
	}, 5200);

	// t=5400ms — done + assistant message finalizes
	setTimeout(() => {
		updateMessage(sessionId, assistantMsg.id, responseContent);
		pushSSE(sessionId, 'done', { message_id: assistantMsg.id, content: responseContent });
	}, 5400);

	return json(assistantMsg, { status: 201 });
}
