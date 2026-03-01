import { json } from '@sveltejs/kit';
import { MOCK_USER } from '../../_store';

export function GET() {
	return json(MOCK_USER);
}
