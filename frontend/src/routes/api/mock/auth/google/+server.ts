import { redirect } from '@sveltejs/kit';

// Simulates Google OAuth by jumping straight to the app
export function GET() {
	redirect(302, '/chat');
}
