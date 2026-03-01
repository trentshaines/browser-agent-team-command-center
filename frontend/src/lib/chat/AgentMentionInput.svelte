<script lang="ts">
  import { tick } from 'svelte';
  import { senderColor } from '$lib/palette';

  export interface AgentOption {
    id: string;
    name: string;
  }

  let {
    agents = [],
    placeholder = 'Message the team...',
    onSubmit,
  }: {
    agents?: AgentOption[];
    placeholder?: string;
    onSubmit?: (text: string) => void;
  } = $props();

  let editorEl: HTMLDivElement;
  let menuEl: HTMLDivElement;

  // Autocomplete state
  let showMenu = $state(false);
  let menuQuery = $state('');
  let selectedIdx = $state(0);
  let mentionAnchorNode: Node | null = null;
  let mentionAnchorOffset = 0;

  const filtered = $derived(
    menuQuery === ''
      ? agents
      : agents.filter((a) =>
          a.name.toLowerCase().includes(menuQuery.toLowerCase())
        )
  );

  // Reset selection when filtered list changes
  $effect(() => {
    if (selectedIdx >= filtered.length) selectedIdx = Math.max(0, filtered.length - 1);
  });

  function getPlainText(): string {
    // Walk childNodes to extract text, preserving spaces
    if (!editorEl) return '';
    let text = '';
    for (const node of editorEl.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        text += node.textContent ?? '';
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        text += (node as HTMLElement).textContent ?? '';
      }
    }
    return text;
  }

  function submit() {
    const text = getPlainText().trim();
    if (!text) return;
    closeMenu();
    onSubmit?.(text);
    editorEl.innerHTML = '';
  }

  function closeMenu() {
    showMenu = false;
    menuQuery = '';
    selectedIdx = 0;
    mentionAnchorNode = null;
  }

  function insertMention(agent: AgentOption) {
    // Delete the @query text, insert a styled span
    const sel = window.getSelection();
    if (!sel || !mentionAnchorNode) {
      closeMenu();
      return;
    }

    // Find the text node containing the @mention and replace
    const textNode = mentionAnchorNode;
    const text = textNode.textContent ?? '';
    const atPos = text.lastIndexOf('@', mentionAnchorOffset);
    if (atPos === -1) { closeMenu(); return; }

    const range = document.createRange();
    range.setStart(textNode, atPos);
    // The cursor might have moved; use current offset from textContent
    const cursorPos = getCurrentOffsetInNode(textNode);
    range.setEnd(textNode, cursorPos !== null ? cursorPos : mentionAnchorOffset + menuQuery.length);
    range.deleteContents();

    // Create mention span
    const span = document.createElement('span');
    span.className = 'mention-tag';
    span.contentEditable = 'false';
    span.style.color = senderColor(agent.name);
    span.style.fontWeight = '600';
    span.textContent = `@${agent.name}`;
    span.dataset.agentId = agent.id;
    span.dataset.agentName = agent.name;

    range.insertNode(span);

    // Add a space after mention and place cursor there
    const space = document.createTextNode('\u00A0');
    span.after(space);

    const newRange = document.createRange();
    newRange.setStartAfter(space);
    newRange.collapse(true);
    sel.removeAllRanges();
    sel.addRange(newRange);

    closeMenu();
    editorEl.focus();
  }

  function getCurrentOffsetInNode(node: Node): number | null {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return null;
    const range = sel.getRangeAt(0);
    if (range.startContainer === node) return range.startOffset;
    return null;
  }

  function onInput() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) { closeMenu(); return; }

    const range = sel.getRangeAt(0);
    const node = range.startContainer;
    if (node.nodeType !== Node.TEXT_NODE) { closeMenu(); return; }

    const text = node.textContent ?? '';
    const cursor = range.startOffset;
    // Find last '@' before cursor that isn't preceded by a non-space char
    const before = text.slice(0, cursor);
    const atMatch = before.match(/(^|[\s\u00A0])@([^\s]*)$/);

    if (atMatch && agents.length > 0) {
      menuQuery = atMatch[2];
      mentionAnchorNode = node;
      mentionAnchorOffset = cursor - atMatch[2].length - 1; // position of @
      showMenu = true;
      selectedIdx = 0;
    } else {
      closeMenu();
    }
  }

  function onKeydown(e: KeyboardEvent) {
    if (showMenu && filtered.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIdx = (selectedIdx + 1) % filtered.length;
        scrollSelectedIntoView();
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIdx = (selectedIdx - 1 + filtered.length) % filtered.length;
        scrollSelectedIntoView();
        return;
      }
      if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault();
        insertMention(filtered[selectedIdx]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        closeMenu();
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function scrollSelectedIntoView() {
    tick().then(() => {
      menuEl?.querySelector('[data-selected="true"]')?.scrollIntoView({ block: 'nearest' });
    });
  }

  // Paste as plain text
  function onPaste(e: ClipboardEvent) {
    e.preventDefault();
    const text = e.clipboardData?.getData('text/plain') ?? '';
    document.execCommand('insertText', false, text);
  }

  export function focus() {
    editorEl?.focus();
  }
</script>

<div class="mention-input-wrapper relative">
  <!-- Autocomplete dropdown — positioned above the input -->
  {#if showMenu && filtered.length > 0}
    <div
      bind:this={menuEl}
      class="absolute bottom-full left-0 right-0 mb-1 rounded-lg bg-[#1e1e2e] border border-white/20 shadow-xl overflow-hidden z-50 max-h-40 overflow-y-auto"
    >
      {#each filtered as agent, i (agent.id)}
        <button
          type="button"
          data-selected={i === selectedIdx}
          class="w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors cursor-pointer
            {i === selectedIdx ? 'bg-white/15' : 'hover:bg-white/10'}"
          onmousedown={(e) => { e.preventDefault(); insertMention(agent); }}
          onmouseenter={() => (selectedIdx = i)}
        >
          <span
            class="w-2 h-2 rounded-full shrink-0"
            style="background: {senderColor(agent.name)}"
          ></span>
          <span class="font-medium" style="color: {senderColor(agent.name)}">{agent.name}</span>
        </button>
      {/each}
    </div>
  {/if}

  <!-- Editable input -->
  <div
    bind:this={editorEl}
    contenteditable="true"
    role="textbox"
    aria-label={placeholder}
    aria-multiline="false"
    class="mention-editor flex-1 bg-transparent text-xs text-text outline-none min-h-[1.5em] max-h-20 overflow-y-auto break-words"
    oninput={onInput}
    onkeydown={onKeydown}
    onpaste={onPaste}
    data-placeholder={placeholder}
  ></div>
</div>

<style>
  .mention-editor:empty::before {
    content: attr(data-placeholder);
    color: var(--text-faint, #888);
    pointer-events: none;
  }

  .mention-editor :global(.mention-tag) {
    border-radius: 3px;
    padding: 0 2px;
    background: rgba(255, 255, 255, 0.08);
    user-select: all;
    cursor: default;
  }
</style>
