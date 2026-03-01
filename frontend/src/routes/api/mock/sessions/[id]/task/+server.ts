import { json } from '@sveltejs/kit';
import { pushSSE } from '../../../_store';

const SCREENSHOT_BLUE =
	'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAAB//EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AMAAB/9k=';
const SCREENSHOT_GREEN =
	'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAACAAIDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAABv/EABQQAQAAAAAAAAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8AmAAB/9k=';

export async function POST({ params, request }) {
	const sessionId = params.id;

	const body = await request.json().catch(() => ({}));
	const prompt: string = body.prompt ?? '';
	const agents: { name: string; task: string }[] = body.agents ?? [];

	const taskId = crypto.randomUUID();
	const agentInfos: { agent_id: string; task: string }[] = [];

	// Spawn each agent with staggered timing
	agents.forEach((agent, i) => {
		const agentId = crypto.randomUUID();
		agentInfos.push({ agent_id: agentId, task: agent.task });
		const baseDelay = i * 200;

		// agent spawned
		setTimeout(() => {
			pushSSE(sessionId, 'agent_event', {
				type: 'agent_spawned',
				agent_id: agentId,
				name: agent.name,
				task: agent.task,
			});
		}, 300 + baseDelay);

		// first frame
		setTimeout(() => {
			pushSSE(sessionId, 'agent_frame', {
				agent_id: agentId,
				step: 1,
				url: 'https://example.com',
				screenshot: i % 2 === 0 ? SCREENSHOT_BLUE : SCREENSHOT_GREEN,
			});
		}, 800 + baseDelay);

		// agent log
		setTimeout(() => {
			pushSSE(sessionId, 'agent_log', {
				agent_run_id: agentId,
				step: 1,
				url: 'https://example.com',
				action_type: 'navigate',
				thought: `Navigating to complete: ${agent.task.slice(0, 50)}`,
				success: true,
			});
		}, 1000 + baseDelay);

		// agent complete
		setTimeout(() => {
			pushSSE(sessionId, 'agent_event', {
				type: 'agent_complete',
				agent_run_id: agentId,
				result: `Completed: ${agent.task.slice(0, 80)}`,
				total_steps: 1,
			});
		}, 3000 + baseDelay);
	});

	// done event after all agents
	const doneDelay = 3500 + agents.length * 200;
	setTimeout(() => {
		pushSSE(sessionId, 'done', { agents: agentInfos.map(a => ({ ...a, status: 'complete' })) });
	}, doneDelay);

	return json({ task_id: taskId, agents: agentInfos }, { status: 201 });
}
