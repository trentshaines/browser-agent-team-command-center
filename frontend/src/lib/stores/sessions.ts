import { writable } from 'svelte/store';
import { sessions as sessionsApi, type Session } from '$lib/api';

function createSessionsStore() {
  const { subscribe, set, update } = writable<Session[]>([]);

  return {
    subscribe,
    async load() {
      try {
        const data = await sessionsApi.list();
        set(data);
      } catch {}
    },
    async create(): Promise<Session> {
      const s = await sessionsApi.create();
      update(list => [s, ...list]);
      return s;
    },
    async delete(id: string) {
      await sessionsApi.delete(id);
      update(list => list.filter(s => s.id !== id));
    },
    updateTitle(id: string, title: string) {
      update(list => list.map(s => s.id === id ? { ...s, title } : s));
    },
    bumpUpdated(id: string) {
      update(list => {
        const idx = list.findIndex(s => s.id === id);
        if (idx < 0) return list;
        const [s] = list.splice(idx, 1);
        return [{ ...s, updated_at: new Date().toISOString() }, ...list];
      });
    },
  };
}

export const sessionsStore = createSessionsStore();
