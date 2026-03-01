<script lang="ts">
  import { ChevronDownIcon, XIcon } from 'lucide-svelte';
  import Logo from './Logo.svelte';
  import type { Session } from '$lib/api';

  let {
    sessions,
    currentSessionId,
    onSwitch,
    onDelete,
  }: {
    sessions: Session[];
    currentSessionId: string | null;
    onSwitch: (id: string) => void;
    onDelete: (id: string) => void;
  } = $props();

  let open = $state(false);
  let triggerEl = $state<HTMLButtonElement | null>(null);
  let dropdownEl = $state<HTMLDivElement | null>(null);

  function toggle() {
    open = !open;
  }

  function handleSwitch(id: string) {
    open = false;
    onSwitch(id);
  }

  function handleDelete(e: MouseEvent, id: string) {
    e.stopPropagation();
    onDelete(id);
  }

  function relativeTime(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  // Close on click outside or Escape
  $effect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') { open = false; }
    }
    function onClick(e: MouseEvent) {
      if (
        triggerEl && !triggerEl.contains(e.target as Node) &&
        dropdownEl && !dropdownEl.contains(e.target as Node)
      ) {
        open = false;
      }
    }
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onClick);
    };
  });

  const currentTitle = $derived(
    sessions.find(s => s.id === currentSessionId)?.title ?? 'James'
  );
</script>

<div class="relative">
  <button
    bind:this={triggerEl}
    onclick={toggle}
    class="flex items-center gap-2 px-1.5 py-1 -ml-1.5 rounded-lg hover:bg-white/10 transition-colors"
  >
    <Logo size={18} />
    <span class="text-sm font-semibold text-text max-w-[180px] truncate">{currentTitle}</span>
    <ChevronDownIcon
      size={14}
      class="text-text-faint transition-transform {open ? 'rotate-180' : ''}"
    />
  </button>

  {#if open}
    <div
      bind:this={dropdownEl}
      class="absolute top-full left-0 mt-1.5 w-72 rounded-xl bg-surface border border-white/15 shadow-[0_12px_40px_rgba(0,0,0,0.3)] backdrop-blur-xl overflow-hidden z-50"
    >
      <div class="px-3 pt-3 pb-1.5">
        <span class="text-[10px] font-medium text-text-faint uppercase tracking-widest">Projects</span>
      </div>

      <div class="max-h-[320px] overflow-y-auto px-1.5 pb-1.5">
        {#if sessions.length === 0}
          <div class="px-3 py-4 text-center">
            <p class="text-xs text-text-faint">No projects yet</p>
          </div>
        {:else}
          {#each sessions as session (session.id)}
            {@const isActive = session.id === currentSessionId}
            <div
              role="button"
              tabindex="0"
              onclick={() => handleSwitch(session.id)}
              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSwitch(session.id); } }}
              class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left group transition-colors cursor-pointer
                {isActive ? 'bg-accent/15' : 'hover:bg-white/8'}"
            >
              <span
                class="w-1.5 h-1.5 rounded-full shrink-0 {isActive ? 'bg-accent' : 'bg-transparent'}"
              ></span>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-text truncate">{session.title}</p>
                <p class="text-[10px] text-text-faint">{relativeTime(session.updated_at)}</p>
              </div>
              {#if !isActive}
                <button
                  onclick={(e) => handleDelete(e, session.id)}
                  class="p-1 rounded text-text-faint hover:text-danger opacity-0 group-hover:opacity-100 transition-all shrink-0"
                  aria-label="Delete project"
                >
                  <XIcon size={12} />
                </button>
              {/if}
            </div>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>
