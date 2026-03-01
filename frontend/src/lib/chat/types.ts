import type { Message } from '$lib/api';

export type WidgetMessage = Message & { senderName?: string };
