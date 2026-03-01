import { writable } from 'svelte/store';
import { sessions as sessionsApi, type Session } from '$lib/api';

export const sessionsLoading = writable(false);

function createSessionsStore() {
  const { subscribe, set, update } = writable<Session[]>([]);

  return {
    subscribe,
    async load() {
      sessionsLoading.set(true);
      try {
        const data = await sessionsApi.list();
        set(data);
      } catch (e) {
        console.error('Failed to load sessions:', e);
      } finally {
        sessionsLoading.set(false);
      }
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
        const s = list[idx];
        return [{ ...s, updated_at: new Date().toISOString() }, ...list.filter((_, i) => i !== idx)];
      });
    },
  };
}

export const sessionsStore = createSessionsStore();
