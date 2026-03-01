<script lang="ts">
  import { cn } from '$lib/utils';
  import { agentBrowserWindowTileConfig } from './config';
  import AgentTileStatusBar from './AgentTileStatusBar.svelte';

  import defaultTileImage from '$lib/assets/AgentBrowserWindowTile.png';

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
    status?: string;
    agentName?: string;
    onExpand?: () => void;
  } = $props();

  const { borderRadius, aspectRatio, objectFit } = agentBrowserWindowTileConfig;

  let dragOffset = $state({ x: 0, y: 0 });
  let isDragging = $state(false);
  let pointerStart = $state<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null);

  function onPointerDown(e: PointerEvent) {
    if (!draggable || (e.button !== undefined && e.button !== 0)) return;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    isDragging = true;
    pointerStart = {
      x: e.clientX,
      y: e.clientY,
      offsetX: dragOffset.x,
      offsetY: dragOffset.y,
    };
  }

  function onPointerMove(e: PointerEvent) {
    if (!pointerStart) return;
    dragOffset = {
      x: pointerStart.offsetX + (e.clientX - pointerStart.x),
      y: pointerStart.offsetY + (e.clientY - pointerStart.y),
    };
  }

  function onPointerUp(e: PointerEvent) {
    if (pointerStart) {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
      pointerStart = null;
      isDragging = false;
    }
  }
</script>

<div
  class={cn(
    'relative',
    draggable && (isDragging ? 'cursor-grabbing' : 'cursor-grab'),
    className
  )}
  style="aspect-ratio: {aspectRatio};"
  role="group"
  aria-label={draggable ? 'Browser window tile, drag to move' : undefined}
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={onPointerUp}
  onpointercancel={onPointerUp}
>
  <div
    class={cn(
      'touch-none select-none flex flex-col overflow-hidden relative',
      'rounded-2xl border border-white/25 dark:border-white/15',
      'bg-white/25 dark:bg-white/10 backdrop-blur-2xl',
      'shadow-[0_4px_24px_rgba(0,0,0,0.06),0_12px_28px_-4px_rgba(0,0,0,0.12),0_20px_40px_-8px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.4)]',
      'ring-1 ring-white/30 dark:ring-white/15',
      isDragging && 'z-10 ring-2 ring-accent/40'
    )}
    style="transform: translate({dragOffset.x}px, {dragOffset.y}px);"
  >
    <AgentTileStatusBar {status} {agentName} />
    <button
      type="button"
      class="absolute top-2 right-2 z-10 p-1.5 rounded-lg text-(--text-muted) hover:text-(--text) hover:bg-black/5 dark:hover:bg-white/5 transition-colors focus:outline-none focus:ring-2 focus:ring-accent/50"
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
  </div>
</div>
