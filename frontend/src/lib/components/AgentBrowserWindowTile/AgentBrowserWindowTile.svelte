<script lang="ts">
  import { cn } from '$lib/utils';
  import { agentBrowserWindowTileConfig } from './config';
  import AgentTileStatusBar from './AgentTileStatusBar.svelte';

  import defaultTileImage from '$lib/assets/AgentBrowserWindowTile.png';

  type Corner = 'se' | 'sw' | 'ne' | 'nw';

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
    /** Called when the expand (open in full) button is clicked. */
    onExpand,
  }: {
    src?: string;
    alt?: string;
    class?: string;
    imageClass?: string;
    draggable?: boolean;
    resizable?: boolean;
    status?: string;
    agentName?: string;
    onExpand?: () => void;
  } = $props();

  const { aspectRatio, objectFit } = agentBrowserWindowTileConfig;
  const [arW, arH] = aspectRatio.split('/').map(Number);
  const ratio = arW / arH; // width / height (e.g. 16/9 ≈ 1.778)

  // — Drag to reposition —
  let dragOffset = $state({ x: 0, y: 0 });
  let isDragging = $state(false);
  let dragStart = $state<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null);

  function onPointerDown(e: PointerEvent) {
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
  //   se → top-left fixed:    width += deltaX,  offset unchanged
  //   sw → top-right fixed:   width -= deltaX,  offsetX -= widthDelta
  //   ne → bottom-left fixed: width += deltaX,  offsetY -= widthDelta/ratio
  //   nw → bottom-right fixed:width -= deltaX,  offsetX -= widthDelta, offsetY -= widthDelta/ratio

  let containerEl = $state<HTMLElement | null>(null);
  let resizeWidth = $state<number | null>(null);
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
    The grip SVG is designed for the SE corner (lines from top-right to bottom-left).
    CSS scale() mirrors it for the other corners so the lines always point toward the corner.
  -->
  <div
    class={cn(
      'absolute z-10 p-1 touch-none',
      'text-(--text-muted) hover:text-(--text) transition-colors',
      corner === 'se' && 'bottom-1.5 right-1.5 cursor-se-resize',
      corner === 'sw' && 'bottom-1.5 left-1.5  cursor-sw-resize',
      corner === 'ne' && 'top-1.5  right-1.5  cursor-ne-resize',
      corner === 'nw' && 'top-1.5  left-1.5   cursor-nw-resize',
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
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true">
      <line x1="9" y1="2" x2="2" y2="9"/>
      <line x1="9" y1="6" x2="6" y2="9"/>
    </svg>
  </div>
{/snippet}

<div
  bind:this={containerEl}
  class={cn(
    'relative',
    draggable && (isDragging ? 'cursor-grabbing' : 'cursor-grab'),
    className
  )}
  style="{resizeWidth != null ? `width: ${resizeWidth}px;` : ''} aspect-ratio: {aspectRatio}; transform: translate({dragOffset.x}px, {dragOffset.y}px);"
  role="group"
  aria-label={draggable ? 'Browser window tile, drag to move' : undefined}
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
>
  <div
    class={cn(
      'touch-none select-none flex flex-col overflow-hidden relative size-full',
      'rounded-2xl border border-white/25 dark:border-white/15',
      'bg-white/25 dark:bg-white/10 backdrop-blur-2xl',
      'shadow-[0_4px_24px_rgba(0,0,0,0.06),0_12px_28px_-4px_rgba(0,0,0,0.12),0_20px_40px_-8px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.4)]',
      'ring-1 ring-white/30 dark:ring-white/15',
      isResizing && 'ring-2 ring-accent/40'
    )}
  >
    <AgentTileStatusBar {status} {agentName} />
    <button
      type="button"
      class="absolute top-2 right-2 z-20 p-1.5 rounded-lg text-(--text-muted) hover:text-(--text) hover:bg-black/5 dark:hover:bg-white/5 transition-colors focus:outline-none focus:ring-2 focus:ring-accent/50"
      aria-label="Expand"
      onclick={(e) => {
        e.stopPropagation();
        onExpand?.();
      }}
      onpointerdown={(e) => e.stopPropagation()}
    >
      <!-- Material Icon: open_in_full (OpenInFull) -->
      <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M21 11V3h-8l3.29 3.29-6.5 6.5L3 11v8h8l-3.29-3.29 6.5-6.5L21 11z"/>
      </svg>
    </button>
    <div class="flex-1 min-h-0 p-2">
      <div class="overflow-hidden size-full rounded-lg">
        <img
          {src}
          {alt}
          class={cn('size-full pointer-events-none', objectFit, imageClass)}
          loading="lazy"
          decoding="async"
          draggable="false"
        />
      </div>
    </div>
    {#if resizable}
      {@render resizeHandle('se')}
      {@render resizeHandle('sw')}
      {@render resizeHandle('ne')}
      {@render resizeHandle('nw')}
    {/if}
  </div>
</div>
