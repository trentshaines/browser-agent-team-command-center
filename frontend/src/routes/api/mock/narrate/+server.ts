import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request }) => {
  const { agent_name, task, logs, completed, result } = await request.json() as {
    agent_name: string;
    task: string;
    logs: string[];
    completed?: boolean;
    result?: string;
  };

  // Simulate LLM latency
  await new Promise((r) => setTimeout(r, 300 + Math.random() * 300));

  let message: string;

  if (completed) {
    if (result) {
      // Summarize completion
      const short = result.length > 120 ? result.slice(0, 117) + '...' : result;
      message = `All done! ${short}`;
    } else {
      message = `Wrapped up the task but didn't get a clear result.`;
    }
  } else {
    // Synthesize a casual status update from the logs
    const recent = logs.slice(-3);
    if (recent.length === 0) {
      message = `Still working on it...`;
    } else if (recent.length === 1) {
      message = `Just ${recent[0].toLowerCase()}`;
    } else {
      const last = recent[recent.length - 1];
      message = `Been doing some work — ${recent.slice(0, -1).join(', ')}, and now ${last.toLowerCase()}`;
    }
  }

  return json({ message });
};
