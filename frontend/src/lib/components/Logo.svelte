<script lang="ts">
  import { palette } from '$lib/palette';

  let { size = 20 }: { size?: number } = $props();

  const gap = 1.5;  // gap between squares as SVG units (out of 24)
  const r = 3;      // corner radius
  const half = (24 - gap) / 2;
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  aria-hidden="true"
>
  <rect x="0"            y="0"            width={half} height={half} rx={r} fill={palette.accent} />
  <rect x={half + gap}   y="0"            width={half} height={half} rx={r} fill={palette.cyan} />
  <rect x="0"            y={half + gap}   width={half} height={half} rx={r} fill={palette.pink} />
  <rect x={half + gap}   y={half + gap}   width={half} height={half} rx={r} fill={palette.orange} />
</svg>
