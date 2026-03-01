import { useSafeConvexClient } from '$lib/convex';
import { api } from '../../convex/_generated/api';
import type { Id } from '../../convex/_generated/dataModel';
import type { ConvexClient } from 'convex/browser';

const STORAGE_KEY = 'browser-agent-sessions';
const MIGRATED_KEY = 'browser-agent-sessions-migrated';

/**
 * Get Convex session mutation wrappers.
 * Returns null if Convex isn't configured.
 */
export function useSessionMutations() {
  const client = useSafeConvexClient();
  if (!client) return null;

  return {
    async create(title: string): Promise<{ _id: Id<"sessions">; clientId: string }> {
      const clientId = crypto.randomUUID();
      const _id = await client.mutation(api.sessions.create, { clientId, title });
      return { _id, clientId };
    },
    async remove(id: Id<"sessions">) {
      await client.mutation(api.sessions.remove, { id });
    },
    async updateTitle(id: Id<"sessions">, title: string) {
      await client.mutation(api.sessions.updateTitle, { id, title });
    },
    async bumpUpdated(id: Id<"sessions">) {
      await client.mutation(api.sessions.bumpUpdated, { id });
    },
  };
}

/**
 * One-time migration: push localStorage sessions to Convex, then set migrated flag.
 */
export async function migrateLocalStorageSessions(client: ConvexClient) {
  if (typeof window === 'undefined') return;
  if (localStorage.getItem(MIGRATED_KEY)) return;

  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    localStorage.setItem(MIGRATED_KEY, '1');
    return;
  }

  try {
    const sessions: { id: string; title: string }[] = JSON.parse(raw);
    for (const s of sessions) {
      await client.mutation(api.sessions.create, {
        clientId: s.id,
        title: s.title,
      });
    }
  } catch {
    // Best-effort migration
  }

  localStorage.setItem(MIGRATED_KEY, '1');
}
