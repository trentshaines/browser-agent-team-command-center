import { json } from '@sveltejs/kit';
import { getSessions, createSession } from '../_store';

export function GET() {
	return json(getSessions());
}

export async function POST({ request }) {
	const body = await request.json().catch(() => ({}));
	const s = createSession(body.title);
	return json(s, { status: 201 });
}
