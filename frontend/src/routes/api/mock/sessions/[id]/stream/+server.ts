import { popSSE } from '../../../_store';

// Polls the SSE queue every 100ms and streams events to the client.
// This mimics the real backend's streaming endpoint for frontend dev.
export function GET({ params }) {
	const sessionId = params.id;
	let cancelled = false;

	const stream = new ReadableStream({
		async start(controller) {
			const encoder = new TextEncoder();
			controller.enqueue(encoder.encode(': connected\n\n'));

			while (!cancelled) {
				await new Promise<void>((r) => setTimeout(r, 100));
				const events = popSSE(sessionId);
				for (const e of events) {
					try {
						controller.enqueue(encoder.encode(e));
					} catch {
						cancelled = true;
						break;
					}
				}
			}
		},
		cancel() {
			cancelled = true;
		},
	});

	return new Response(stream, {
		headers: {
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache',
			Connection: 'keep-alive',
		},
	});
}
