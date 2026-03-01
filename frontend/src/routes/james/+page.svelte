<script lang="ts">
  import { page } from "$app/stores";
  import {
    BotIcon,
    LogInIcon,
    MessageSquareIcon,
    WrenchIcon,
  } from "lucide-svelte";
  import MessageBubble from "$lib/components/MessageBubble.svelte";
  import ChatInput from "$lib/components/ChatInput.svelte";
  import type { Message } from "$lib/api";

  const apiUrl = $derived($page.url.origin + "/api");
  const backendUrl =
    typeof import.meta.env !== "undefined"
      ? (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
      : "";

  // Floating chat widget
  type TabId = "chat" | "history";
  let activeTab = $state<TabId>("chat");
  let chatMessages = $state<Message[]>([
    {
      id: "1",
      role: "assistant",
      content: "Hi! This is the dev chat widget. Type a message below.",
      created_at: new Date().toISOString(),
    },
  ]);

  function sendMessage(content: string) {
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    chatMessages = [...chatMessages, userMsg];
    // Placeholder assistant reply for demo
    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: `You said: "${content}" — (widget is local-only, no backend.)`,
      created_at: new Date().toISOString(),
    };
    chatMessages = [...chatMessages, assistantMsg];
  }
</script>

<svelte:head>
  <title>Browser Agent Command Center — James</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">
  <header
    class="border-b border-border-subtle bg-surface/50 px-6 py-4 flex items-center justify-between"
  >
    <div class="flex items-center gap-2">
      <BotIcon size={24} class="text-accent" />
      <span class="font-semibold text-text">Browser Agent Command Center</span>
    </div>
    <nav class="flex items-center gap-3">
      <a
        href="/login"
        class="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
      >
        <LogInIcon size={16} />
        Sign in
      </a>
      <a
        href="/chat"
        class="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent-hover transition-colors"
      >
        <MessageSquareIcon size={16} />
        Open app
      </a>
    </nav>
  </header>

  <main class="flex-1 flex flex-col items-center justify-center px-6 py-16">
    <div class="max-w-xl w-full flex flex-col items-center gap-8 text-center">
      <div class="flex flex-col items-center gap-4">
        <div class="p-4 rounded-2xl bg-surface border border-border-subtle">
          <BotIcon size={48} class="text-accent" />
        </div>
        <h1 class="text-3xl font-semibold text-text tracking-tight">
          Browser Agent Command Center
        </h1>
        <p class="text-text-muted text-lg max-w-md">
          Orchestrate a team of browser agents to research, compare, and extract
          information from the web.
        </p>
      </div>

      <div class="flex flex-wrap items-center justify-center gap-3">
        <a
          href="/login"
          class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-border bg-surface hover:bg-surface-hover text-text text-sm font-medium transition-colors"
        >
          <LogInIcon size={18} />
          Sign in with Google
        </a>
        <a
          href="/chat"
          class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors"
        >
          <MessageSquareIcon size={18} />
          Open chat
        </a>
      </div>

      <section
        class="mt-12 w-full text-left rounded-2xl border border-border-subtle bg-surface/80 p-5"
        aria-label="Development"
      >
        <div
          class="flex items-center gap-2 text-text-muted text-sm font-medium mb-3"
        >
          <WrenchIcon size={16} />
          Development
        </div>
        <ul class="space-y-2 text-sm text-text-muted">
          <li>
            <span class="text-text-faint">Frontend:</span>
            <code
              class="ml-2 px-1.5 py-0.5 rounded bg-surface-hover text-text font-mono text-xs"
              >{apiUrl}</code
            >
          </li>
          <li>
            <span class="text-text-faint">Backend (VITE_API_URL):</span>
            <code
              class="ml-2 px-1.5 py-0.5 rounded bg-surface-hover text-text font-mono text-xs break-all"
              >{backendUrl}</code
            >
          </li>
          <li>
            <a href="/login" class="text-accent hover:underline">/login</a>
            <span class="text-text-faint"> · </span>
            <a href="/chat" class="text-accent hover:underline">/chat</a>
          </li>
        </ul>
      </section>
    </div>
  </main>

  <footer
    class="border-t border-border-subtle px-6 py-3 text-center text-text-faint text-xs"
  >
    /james — dev homepage. Root / is unchanged for your coworker.
  </footer>

  <!-- Floating chat widget -->
  <div
    class="fixed bottom-6 right-6 w-[380px] max-h-[520px] flex flex-col rounded-2xl border border-border bg-background shadow-lg overflow-hidden z-50"
  >
    <!-- Header with tabs -->
    <header class="shrink-0 border-b border-border-subtle bg-surface px-3 py-2">
      <div class="flex rounded-lg bg-surface-hover p-0.5" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "chat"}
          class="flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors {activeTab ===
          'chat'
            ? 'bg-background text-text shadow-sm'
            : 'text-text-muted hover:text-text'}"
          onclick={() => (activeTab = "chat")}
        >
          Chat
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "history"}
          class="flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors {activeTab ===
          'history'
            ? 'bg-background text-text shadow-sm'
            : 'text-text-muted hover:text-text'}"
          onclick={() => (activeTab = "history")}
        >
          History
        </button>
      </div>
    </header>

    <!-- Middle: chat display or history -->
    <div class="flex-1 flex flex-col min-h-0">
      {#if activeTab === "chat"}
        <div
          class="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-1 min-h-[200px]"
        >
          {#each chatMessages as msg (msg.id)}
            <MessageBubble message={msg} />
          {/each}
        </div>
        <div class="shrink-0 border-t border-border-subtle">
          <ChatInput onsubmit={sendMessage} />
        </div>
      {:else}
        <div
          class="flex-1 overflow-y-auto px-3 py-4 text-sm text-text-muted text-center"
        >
          <p>No history yet.</p>
          <p class="mt-2 text-text-faint text-xs">
            Switch to Chat to send messages.
          </p>
        </div>
      {/if}
    </div>
  </div>
</div>
