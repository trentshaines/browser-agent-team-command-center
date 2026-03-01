import { json } from '@sveltejs/kit';

/** Extract site/brand names from a prompt for use in agent names. */
function extractSites(prompt: string): string[] {
	const known = [
		'Amazon', 'Best Buy', 'Walmart', 'Target', 'eBay', 'Costco',
		'Google Flights', 'Kayak', 'Skyscanner', 'Expedia',
		'Yelp', 'Google Maps', 'TripAdvisor',
		'LinkedIn', 'Indeed', 'Glassdoor',
		'AWS', 'GCP', 'Azure',
		'Reddit', 'Twitter', 'YouTube',
		'arxiv', 'Google Scholar',
	];
	return known.filter((s) => prompt.toLowerCase().includes(s.toLowerCase()));
}

export async function POST({ request }) {
	const body = await request.json().catch(() => ({}));
	const prompt: string = body.prompt ?? '';

	// Simulate planning delay
	await new Promise((r) => setTimeout(r, 1200));

	const agents: { name: string; task: string }[] = [];
	const promptLower = prompt.toLowerCase();
	const sites = extractSites(prompt);

	if (sites.length >= 2) {
		// Multiple known sites → one agent per site
		for (const site of sites) {
			agents.push({
				name: `${site} Scout`,
				task: `Go to ${site} and ${prompt.replace(new RegExp(site, 'gi'), '').replace(/,?\s*(and|&)\s*$/i, '').trim() || 'complete the task'}`,
			});
		}
	} else if (
		promptLower.includes('compare') ||
		promptLower.includes('vs') ||
		promptLower.includes('across')
	) {
		agents.push(
			{ name: 'Price Hunter', task: `Search the first source for pricing info: ${prompt}` },
			{ name: 'Deal Finder', task: `Search the second source for pricing info: ${prompt}` },
			{ name: 'Review Analyst', task: `Search the third source and compile reviews: ${prompt}` },
		);
	} else if (prompt.length > 100) {
		agents.push(
			{ name: 'Lead Researcher', task: `Research the main topic: ${prompt.slice(0, 120)}` },
			{ name: 'Detail Gatherer', task: `Find supporting details and examples for: ${prompt.slice(0, 120)}` },
		);
	} else {
		agents.push({ name: 'Browser Agent', task: prompt || 'Browse the web' });
	}

	// Generate a short title from the prompt
	const titleWords = prompt.split(/\s+/).slice(0, 6).join(' ');
	const title = titleWords.length > 40 ? titleWords.slice(0, 40) + '...' : titleWords || 'New Project';

	return json({ title, agents });
}
