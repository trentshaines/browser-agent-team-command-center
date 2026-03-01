import { json } from '@sveltejs/kit';

export async function POST({ request }) {
	const body = await request.json().catch(() => ({}));
	const prompt: string = body.prompt ?? '';

	// Simulate planning delay
	await new Promise((r) => setTimeout(r, 1200));

	// Generate a mock plan based on the prompt
	const words = prompt.split(/\s+/).slice(0, 5).join(' ');
	const title = words.length > 30 ? words.slice(0, 30) + '...' : words || 'New Project';

	// Simple heuristic: create 1-3 agents based on prompt length
	const agents = [];
	const promptLower = prompt.toLowerCase();

	if (promptLower.includes('compare') || promptLower.includes('vs') || promptLower.includes('across')) {
		agents.push(
			{ name: 'Research Agent 1', task: `Search the first source for: ${prompt}` },
			{ name: 'Research Agent 2', task: `Search the second source for: ${prompt}` },
			{ name: 'Research Agent 3', task: `Search the third source for: ${prompt}` }
		);
	} else if (prompt.length > 100) {
		agents.push(
			{ name: 'Primary Researcher', task: `Research the main topic: ${prompt.slice(0, 80)}...` },
			{ name: 'Detail Gatherer', task: `Find supporting details for: ${prompt.slice(0, 80)}...` }
		);
	} else {
		agents.push({ name: 'Browser Agent', task: prompt || 'Browse the web' });
	}

	return json({ title, agents });
}
