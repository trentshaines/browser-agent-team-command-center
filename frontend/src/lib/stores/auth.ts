import { writable } from 'svelte/store';
import { auth as authApi, ApiError } from '$lib/api';

interface User {
  id: string;
  email: string;
  username: string;
  profile_image?: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
}

function createAuthStore() {
  const { subscribe, set, update } = writable<AuthState>({ user: null, loading: true });

  return {
    subscribe,
    async init() {
      try {
        const user = await authApi.me();
        set({ user, loading: false });
      } catch (e) {
        set({ user: null, loading: false });
      }
    },
    async logout() {
      try {
        await authApi.logout();
      } catch {}
      set({ user: null, loading: false });
    },
    setUser(user: User | null) {
      update(s => ({ ...s, user }));
    },
  };
}

export const authStore = createAuthStore();
