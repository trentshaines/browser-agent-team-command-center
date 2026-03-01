<script lang="ts">
  import { page } from "$app/stores";
  import {
    LogInIcon,
    MessageSquareIcon,
    WrenchIcon,
  } from "lucide-svelte";
  import { FloatingChatWidget } from "$lib/chat";
  import { AgentBrowserWindowTile } from "$lib/components/AgentBrowserWindowTile";

  const apiUrl = $derived($page.url.origin + "/api");
  const backendUrl =
    typeof import.meta.env !== "undefined"
      ? (import.meta.env.VITE_API_URL ?? "http://localhost:8000")
      : "";
</script>

<svelte:head>
  <title>Windows — James</title>
</svelte:head>

<div class="min-h-screen bg-background flex flex-col">
  <header
    class="border-b border-border-subtle bg-surface/50 px-6 py-4 flex items-center justify-between"
  >
    <div class="flex items-center gap-2">
      <span class="text-xl">🪟</span>
      <span class="font-semibold text-text">Windows</span>
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
          <span class="text-5xl">🪟</span>
        </div>
        <h1 class="text-3xl font-semibold text-text tracking-tight">
          Windows
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

      <section class="mt-12 w-full" aria-label="Agent browser windows">
        <div
          class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 max-w-4xl mx-auto"
        >
          <AgentBrowserWindowTile
            class="w-full"
            status="Done"
            agentName="James Agent"
          />
          <AgentBrowserWindowTile
            class="w-full"
            status="In-Progress"
            agentName="Kelly Agent"
          />
          <AgentBrowserWindowTile
            class="w-full"
            status="Blocked"
            agentName="Sam Agent"
          />
        </div>
      </section>

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

  <FloatingChatWidget />
</div>
