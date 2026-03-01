<script lang="ts">
  import { cn } from '$lib/utils';
  import { agentBrowserWindowTileConfig } from './config';
  import AgentTileStatusBar from './AgentTileStatusBar.svelte';
  import AgentExpandedModal from './AgentExpandedModal.svelte';
  import type { Message } from '$lib/api';

  import defaultTileImage from '$lib/assets/AgentBrowserWindowTile.png';

  type Corner = 'se' | 'sw' | 'ne' | 'nw';

  // Shared across all tile instances — incremented each time any tile is focused.
  let zCounter = 1;

  let {
    /** Override image source (e.g. for live screenshots). Defaults to static tile asset. */
    src = defaultTileImage,
    /** Alt text for the image */
    alt = agentBrowserWindowTileConfig.defaultAlt,
    /** Extra class names for the root container */
    class: className = '',
    /** Extra class names for the image element */
    imageClass = '',
    /** Whether the tile can be dragged to reposition. */
    draggable = true,
    /** Whether the tile can be diagonally resized from any corner. */
    resizable = true,
    /** Status label in the status bar (e.g. "Done", "In-Progress", "Blocked"). */
    status = '—',
    /** Agent name shown in the status bar (e.g. "James Agent"). */
    agentName = '—',
    /** Session chat messages to show in the expanded modal sidebar. */
    messages = [],
    /** Initial pixel width of the tile (sets starting size before any resize). */
    initialWidth = null,
    /** Initial left offset within the floating canvas. */
    initialLeft = 0,
    /** Initial top offset within the floating canvas. */
    initialTop = 0,
    /** Live browser session URL for interactive takeover. */
    liveUrl = null,
    /** Callback to signal the backend that the human is done with takeover. */
    onResume = undefined,
  }: {
    src?: string;
    alt?: string;
    class?: string;
    imageClass?: string;
    draggable?: boolean;
    resizable?: boolean;
    status?: string;
    agentName?: string;
    messages?: Message[];
    initialWidth?: number | null;
    initialLeft?: number;
    initialTop?: number;
    liveUrl?: string | null;
    onResume?: (() => void) | undefined;
  } = $props();

  // Interactive takeover state
  let isTakeover = $state(false);

  function enterTakeover() {
    isTakeover = true;
  }

  function exitTakeover() {
    isTakeover = false;
    onResume?.();
  }

  const { aspectRatio, objectFit } = agentBrowserWindowTileConfig;
  const [arW, arH] = aspectRatio.split('/').map(Number);
  const ratio = arW / arH; // width / height (e.g. 16/9 ≈ 1.778)

  // — Bring to front —
  let tileZ = $state(1);

  function bringToFront() {
    tileZ = ++zCounter;
  }

  // — Expand modal —
  let isOpen = $state(false);
  let modalOrigin = $state('50% 50%');

  function openExpand() {
    if (containerEl) {
      const r = containerEl.getBoundingClientRect();
      const dx = Math.round(r.left + r.width / 2 - window.innerWidth / 2);
      const dy = Math.round(r.top + r.height / 2 - window.innerHeight / 2);
      modalOrigin = `calc(50% + ${dx}px) calc(50% + ${dy}px)`;
    }
    isOpen = true;
  }

  // — Drag to reposition —
  let dragOffset = $state({ x: 0, y: 0 });
  let isDragging = $state(false);
  let dragStart = $state<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null);

  function onPointerDown(e: PointerEvent) {
    bringToFront();
    if (!draggable || (e.button !== undefined && e.button !== 0)) return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    isDragging = true;
    dragStart = { x: e.clientX, y: e.clientY, offsetX: dragOffset.x, offsetY: dragOffset.y };
  }

  function onPointerMove(e: PointerEvent) {
    if (!dragStart) return;
    dragOffset = {
      x: dragStart.offsetX + (e.clientX - dragStart.x),
      y: dragStart.offsetY + (e.clientY - dragStart.y),
    };
  }

  function onPointerUp(e: PointerEvent) {
    if (dragStart) {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
      dragStart = null;
      isDragging = false;
    }
  }

  // — Diagonal resize (all corners) —
  // Each corner keeps its opposite corner anchored:
  //   se → top-left fixed:     width += deltaX,  offset unchanged
  //   sw → top-right fixed:    width -= deltaX,  offsetX -= widthDelta
  //   ne → bottom-left fixed:  width += deltaX,  offsetY -= widthDelta/ratio
  //   nw → bottom-right fixed: width -= deltaX,  offsetX -= widthDelta, offsetY -= widthDelta/ratio

  let containerEl = $state<HTMLElement | null>(null);
  let resizeWidth = $state<number | null>(initialWidth);
  let isResizing = $state(false);
  let resizeStart = $state<{
    x: number;
    width: number;
    offsetX: number;
    offsetY: number;
    corner: Corner;
  } | null>(null);

  function makeResizePointerDown(corner: Corner) {
    return (e: PointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const currentWidth = containerEl?.getBoundingClientRect().width ?? 400;
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      isResizing = true;
      resizeStart = {
        x: e.clientX,
        width: currentWidth,
        offsetX: dragOffset.x,
        offsetY: dragOffset.y,
        corner,
      };
    };
  }

  function onResizePointerMove(e: PointerEvent) {
    if (!resizeStart) return;
    const { x, width: startWidth, offsetX: startOffsetX, offsetY: startOffsetY, corner } = resizeStart;
    const deltaX = e.clientX - x;

    // East corners grow rightward; west corners grow leftward (invert deltaX).
    const rawWidth = corner === 'se' || corner === 'ne' ? startWidth + deltaX : startWidth - deltaX;
    const newWidth = Math.max(200, rawWidth);
    const widthDelta = newWidth - startWidth; // actual change after clamping

    resizeWidth = newWidth;
    dragOffset = {
      x: corner === 'sw' || corner === 'nw' ? startOffsetX - widthDelta : startOffsetX,
      y: corner === 'ne' || corner === 'nw' ? startOffsetY - widthDelta / ratio : startOffsetY,
    };
  }

  function onResizePointerUp(e: PointerEvent) {
    if (resizeStart) {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
      resizeStart = null;
      isResizing = false;
    }
  }
</script>

{#snippet resizeHandle(corner: Corner)}
  <!--
    The grip SVG is designed for the SE corner (lines point toward bottom-right).
    CSS scale() mirrors it for the other corners.
  -->
  <div
    class={cn(
      'absolute z-10 p-4 touch-none',
      'text-(--text-muted) hover:text-(--text) transition-colors',
      corner === 'se' && 'bottom-0 right-0 cursor-se-resize',
      corner === 'sw' && 'bottom-0 left-0  cursor-sw-resize',
      corner === 'ne' && 'top-0  right-0  cursor-ne-resize',
      corner === 'nw' && 'top-0  left-0   cursor-nw-resize',
      isResizing && resizeStart?.corner === corner && 'text-(--text)'
    )}
    style={
      corner === 'sw' ? 'transform: scale(-1, 1);' :
      corner === 'ne' ? 'transform: scale(1, -1);' :
      corner === 'nw' ? 'transform: scale(-1, -1);' : ''
    }
    role="presentation"
    onpointerdown={makeResizePointerDown(corner)}
    onpointermove={onResizePointerMove}
    onpointerup={onResizePointerUp}
    onpointercancel={onResizePointerUp}
  >
  </div>
{/snippet}

<AgentExpandedModal
  {isOpen}
  {src}
  {alt}
  {agentName}
  {status}
  {messages}
  {modalOrigin}
  {liveUrl}
  {isTakeover}
  onEnterTakeover={enterTakeover}
  onExitTakeover={exitTakeover}
  onClose={() => (isOpen = false)}
/>

<div
  bind:this={containerEl}
  class={cn('relative', className)}
  style="position: absolute; left: {initialLeft}px; top: {initialTop}px; {resizeWidth != null ? `width: ${resizeWidth}px;` : ''} aspect-ratio: {aspectRatio}; transform: translate({dragOffset.x}px, {dragOffset.y}px); z-index: {isDragging || isResizing ? 9999 : tileZ};"
  role="group"
>
  <div
    class={cn(
      'touch-none select-none flex flex-col overflow-hidden relative size-full',
      'rounded-2xl border border-white/25',
      'bg-white/25 backdrop-blur-2xl',
      'shadow-[0_4px_24px_rgba(0,0,0,0.06),0_12px_28px_-4px_rgba(0,0,0,0.12),0_20px_40px_-8px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.4)]',
      'ring-1 ring-white/30',
      isResizing && 'ring-2 ring-accent/40'
    )}
  >
    <div
      class={draggable && !isTakeover ? (isDragging ? 'cursor-grabbing' : 'cursor-grab') : ''}
      role="presentation"
      onpointerdown={isTakeover ? undefined : onPointerDown}
      onpointermove={isTakeover ? undefined : onPointerMove}
      onpointerup={isTakeover ? undefined : onPointerUp}
      onpointercancel={isTakeover ? undefined : onPointerUp}
    >
      <AgentTileStatusBar {status} {agentName} />
    </div>
    {#if resizable}
      <!-- Render handles before the expand button so DOM order never beats z-index -->
      {@render resizeHandle('se')}
      {@render resizeHandle('sw')}
      {@render resizeHandle('ne')}
      {@render resizeHandle('nw')}
    {/if}
    <!-- Expand button: z-30 sits above all resize handles (z-10) -->
    <button
      type="button"
      class="absolute top-2 right-2 z-30 p-1.5 rounded-lg text-(--text-muted) hover:text-(--text) hover:bg-white/40 hover:shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-accent/50"
      aria-label="Expand"
      onclick={(e) => { e.stopPropagation(); openExpand(); }}
      onpointerdown={(e) => e.stopPropagation()}
    >
      <!-- Material Icon: open_in_full -->
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M21 11V3h-8l3.29 3.29-6.5 6.5L3 11v8h8l-3.29-3.29 6.5-6.5L21 11z"/>
      </svg>
    </button>
    <div class="flex-1 min-h-0 p-2">
      <div class="overflow-hidden size-full rounded-lg relative">
        {#if liveUrl}
          <iframe
            src={liveUrl}
            title="Live browser session"
            class={cn('size-full border-0 absolute inset-0', !isTakeover && 'pointer-events-none')}
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
          ></iframe>
          {#if !isTakeover}
            <img
              {src}
              {alt}
              class={cn('size-full pointer-events-none absolute inset-0', objectFit, imageClass)}
              loading="lazy"
              decoding="async"
              draggable="false"
            />
          {/if}
        {:else}
          <img
            {src}
            {alt}
            class={cn('size-full pointer-events-none', objectFit, imageClass)}
            loading="lazy"
            decoding="async"
            draggable="false"
          />
        {/if}
      </div>
    </div>
    <!-- Take Control / Hand Back buttons -->
    {#if liveUrl}
      <div class="absolute bottom-2 left-1/2 -translate-x-1/2 z-30">
        {#if isTakeover}
          <button
            type="button"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 text-white hover:bg-emerald-600 shadow-lg transition-all"
            onclick={(e) => { e.stopPropagation(); exitTakeover(); }}
            onpointerdown={(e) => e.stopPropagation()}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
            Done — Hand Back
          </button>
        {:else}
          <button
            type="button"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/90 text-gray-800 hover:bg-white shadow-lg backdrop-blur-sm transition-all"
            onclick={(e) => { e.stopPropagation(); enterTakeover(); }}
            onpointerdown={(e) => e.stopPropagation()}
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
            Take Control
          </button>
        {/if}
      </div>
    {/if}
  </div>
</div>
