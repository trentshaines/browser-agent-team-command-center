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
  }: {
    src?: string;
    alt?: string;
    class?: string;
    imageClass?: string;
    draggable?: boolean;
    status?: string;
    agentName?: string;
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
    class={cn('touch-none select-none flex flex-col overflow-hidden', borderRadius)}
    style="transform: translate({dragOffset.x}px, {dragOffset.y}px);"
  >
    <AgentTileStatusBar {status} {agentName} />
    <div
      class={cn(
        'overflow-hidden flex-1 min-h-0 rounded-2xl',
        'border border-border',
        'bg-(--surface)/80 dark:bg-black/40 backdrop-blur-xl',
        'shadow-[0_4px_24px_rgba(0,0,0,0.08),inset_0_1px_0_rgba(255,255,255,0.5)]',
        'ring-1 ring-black/[0.06] dark:ring-white/10',
        isDragging && 'z-10 ring-2 ring-accent/40'
      )}
    >
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
