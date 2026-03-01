/**
 * AgentBrowserWindowTile configuration.
 * Edit these values to change the tile's look without touching the component.
 */
export const agentBrowserWindowTileConfig = {
  /** Border radius of the outer rounded rectangle (Tailwind class or value) */
  borderRadius: 'rounded-2xl',
  /** Aspect ratio of the tile: width / height (e.g. 16/9, 4/3) */
  aspectRatio: '16 / 9' as const,
  /** Object fit for the inner image */
  objectFit: 'object-cover' as const,
  /** Default alt text for the image */
  defaultAlt: 'Agent browser window',
} as const;

export type AgentBrowserWindowTileConfig = typeof agentBrowserWindowTileConfig;

/** Common status values for the tile status bar. Any string is allowed. */
export type AgentTileStatus = 'Done' | 'In-Progress' | 'Blocked' | (string & {});
