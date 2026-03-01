import type { Message } from '$lib/api';

export type MessageCategory = 'user' | 'spawn' | 'status' | 'completion' | 'orchestrator' | 'blocked';

export type WidgetMessage = Message & {
  senderName?: string;
  category?: MessageCategory;
  agentId?: string;
};
