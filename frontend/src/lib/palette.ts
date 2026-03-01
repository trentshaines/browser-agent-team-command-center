/**
 * Design colour palette for the command center.
 *
 * Use these constants anywhere you need a named colour that isn't part of the
 * CSS-variable-based theme (--accent, --text, etc.).  The `AGENT_COLORS` list
 * is the single source of truth for agent/sender colours across both the chat
 * feed and the planning modal cards.
 */

// ── Agent colours ────────────────────────────────────────────────────────────
// Carefully chosen to be visually distinct, readable on both light and dark
// backgrounds, and pleasant when shown side-by-side in a grid.
//
// Each entry has:
//   hex  — the primary colour (used for dots, sender names, borders)
//   bg   — a very low-opacity tint for card backgrounds
//   ring — a subtle ring for card outlines

export interface AgentColor {
  hex: string;
  bg: string;
  ring: string;
}

export const AGENT_COLORS: readonly AgentColor[] = [
  { hex: '#7c3aed', bg: 'rgba(124,58,237,0.08)',  ring: 'rgba(124,58,237,0.18)' },  // violet
  { hex: '#2563eb', bg: 'rgba(37,99,235,0.08)',    ring: 'rgba(37,99,235,0.18)' },   // blue
  { hex: '#d97706', bg: 'rgba(217,119,6,0.08)',    ring: 'rgba(217,119,6,0.18)' },   // amber
  { hex: '#059669', bg: 'rgba(5,150,105,0.08)',    ring: 'rgba(5,150,105,0.18)' },   // emerald
  { hex: '#db2777', bg: 'rgba(219,39,119,0.08)',   ring: 'rgba(219,39,119,0.18)' },  // pink
  { hex: '#0891b2', bg: 'rgba(8,145,178,0.08)',    ring: 'rgba(8,145,178,0.18)' },   // cyan
  { hex: '#dc2626', bg: 'rgba(220,38,38,0.08)',    ring: 'rgba(220,38,38,0.18)' },   // red
  { hex: '#4f46e5', bg: 'rgba(79,70,229,0.08)',    ring: 'rgba(79,70,229,0.18)' },   // indigo
  { hex: '#ca8a04', bg: 'rgba(202,138,4,0.08)',    ring: 'rgba(202,138,4,0.18)' },   // yellow
  { hex: '#0d9488', bg: 'rgba(13,148,136,0.08)',   ring: 'rgba(13,148,136,0.18)' },  // teal
  { hex: '#9333ea', bg: 'rgba(147,51,234,0.08)',   ring: 'rgba(147,51,234,0.18)' },  // purple
  { hex: '#ea580c', bg: 'rgba(234,88,12,0.08)',    ring: 'rgba(234,88,12,0.18)' },   // orange
] as const;

/** Pick agent colour by index (wraps around). */
export function agentColorByIndex(index: number): AgentColor {
  return AGENT_COLORS[index % AGENT_COLORS.length];
}

/** Deterministic colour for a given sender/agent name. */
export function senderColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length].hex;
}

// ── Named palette (for reference / one-off programmatic use) ─────────────────

export const palette = {
  violet:  '#7c3aed',
  blue:    '#2563eb',
  amber:   '#d97706',
  emerald: '#059669',
  pink:    '#db2777',
  cyan:    '#0891b2',
  red:     '#dc2626',
  indigo:  '#4f46e5',
  yellow:  '#ca8a04',
  teal:    '#0d9488',
  purple:  '#9333ea',
  orange:  '#ea580c',
} as const;
