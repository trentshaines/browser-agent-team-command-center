<script lang="ts">
  import WidgetMessageBubble from './WidgetMessageBubble.svelte';
  import AgentMentionInput from './AgentMentionInput.svelte';
  import type { WidgetMessage } from './types';
  import type { AgentOption } from './AgentMentionInput.svelte';

  let {
    messages,
    onSend,
    placeholder = 'Message the team...',
    onSpawnAgent,
    agents = [],
  }: {
    messages: WidgetMessage[];
    onSend?: (content: string) => void;
    placeholder?: string;
    onSpawnAgent?: () => void;
    agents?: AgentOption[];
  } = $props();

  let scrollEl: HTMLDivElement;

  $effect(() => {
    messages; // rerun when messages change
    requestAnimationFrame(() => {
      if (scrollEl) scrollEl.scrollTop = scrollEl.scrollHeight;
    });
  });
</script>

<div class="flex-1 min-h-0 flex flex-col overflow-hidden">
  <div
    bind:this={scrollEl}
    class="flex-1 min-h-0 overflow-y-auto px-3 py-2 flex flex-col bg-transparent"
  >
    {#if messages.length === 0}
      <div class="flex-1 flex flex-col items-center justify-center text-center px-6 gap-3 py-8">
        <div class="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-accent/60">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <path d="M12 11v6M9 14h6"/>
          </svg>
        </div>
        <div>
          <p class="text-xs font-medium text-text-muted">No active project</p>
          <p class="text-[11px] text-text-faint mt-1 leading-relaxed">
            Create a project to start chatting with your team.
          </p>
        </div>
      </div>
    {:else}
      {#each messages as msg, i (msg.id)}
        {@const prevSender = i > 0 ? (messages[i - 1].senderName ?? (messages[i - 1].role === 'user' ? 'You' : 'Orchestrator')) : null}
        {@const thisSender = msg.senderName ?? (msg.role === 'user' ? 'You' : 'Orchestrator')}
        {@const sameSender = prevSender === thisSender}
        <WidgetMessageBubble message={msg} senderName={msg.senderName} compact={sameSender} category={msg.category} agentNames={agents.map(a => a.name)} />
      {/each}
    {/if}
  </div>

  {#if onSend}
    <div class="shrink-0 border-t border-white/15 px-3 py-2 bg-white/5">
      <div class="relative flex items-center gap-2 rounded-xl bg-white/10 border border-white/20 px-3 py-2 focus-within:border-white/40 focus-within:bg-white/15 transition-colors">
        {#if onSpawnAgent}
          <button
            type="button"
            onclick={onSpawnAgent}
            class="shrink-0 flex items-center gap-1 text-xs font-medium text-[#2563eb] hover:text-white hover:bg-[#2563eb] rounded-lg px-2 py-1 -ml-1 cursor-pointer transition-all duration-150 mr-2 border-r border-white/20"
            aria-label="Spawn new agent"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            Agent
          </button>
        {/if}
        <AgentMentionInput {agents} {placeholder} onSubmit={onSend} />
      </div>
    </div>
  {/if}
</div>
