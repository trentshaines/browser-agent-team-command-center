import { writable } from 'svelte/store';

// No auth — always logged in
interface AuthState {
  user: { id: string; username: string } | null;
  loading: boolean;
}

function createAuthStore() {
  const { subscribe, set } = writable<AuthState>({ user: null, loading: true });

  return {
    subscribe,
    async init() {
      // No backend auth — immediately set a local user
      set({ user: { id: 'local', username: 'you' }, loading: false });
    },
  };
}

export const authStore = createAuthStore();
