import { json, error } from '@sveltejs/kit';
import { getSession, updateSession, deleteSession } from '../../_store';

export function GET({ params }) {
	const s = getSession(params.id);
	if (!s) error(404, 'Not found');
	return json(s);
}

export async function PATCH({ params, request }) {
	const body = await request.json().catch(() => ({}));
	const s = updateSession(params.id, body.title);
	if (!s) error(404, 'Not found');
	return json(s);
}

export function DELETE({ params }) {
	deleteSession(params.id);
	return new Response(null, { status: 204 });
}
