<script lang="ts">
  import { cn } from '$lib/utils';
  import { agentBrowserWindowTileConfig } from './config';

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
  }: {
    src?: string;
    alt?: string;
    class?: string;
    imageClass?: string;
    draggable?: boolean;
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
      'overflow-hidden border border-border bg-background touch-none select-none',
      borderRadius,
      isDragging && 'z-10 ring-2 ring-accent/40'
    )}
    style="transform: translate({dragOffset.x}px, {dragOffset.y}px);"
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
