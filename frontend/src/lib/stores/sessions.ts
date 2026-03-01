import { writable } from 'svelte/store';
import type { Session } from '$lib/api';

export const sessionsLoading = writable(false);

const STORAGE_KEY = 'browser-agent-sessions';

function loadFromStorage(): Session[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveToStorage(sessions: Session[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

function createSessionsStore() {
  const { subscribe, set, update } = writable<Session[]>([]);

  return {
    subscribe,
    async load() {
      sessionsLoading.set(true);
      const data = loadFromStorage();
      set(data);
      sessionsLoading.set(false);
    },
    create(title = 'New Chat'): Session {
      const s: Session = {
        id: crypto.randomUUID(),
        title,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      update(list => {
        const next = [s, ...list];
        saveToStorage(next);
        return next;
      });
      return s;
    },
    delete(id: string) {
      update(list => {
        const next = list.filter(s => s.id !== id);
        saveToStorage(next);
        return next;
      });
    },
    updateTitle(id: string, title: string) {
      update(list => {
        const next = list.map(s => s.id === id ? { ...s, title } : s);
        saveToStorage(next);
        return next;
      });
    },
    bumpUpdated(id: string) {
      update(list => {
        const idx = list.findIndex(s => s.id === id);
        if (idx < 0) return list;
        const s = list[idx];
        const next = [{ ...s, updated_at: new Date().toISOString() }, ...list.filter((_, i) => i !== idx)];
        saveToStorage(next);
        return next;
      });
    },
  };
}

export const sessionsStore = createSessionsStore();
