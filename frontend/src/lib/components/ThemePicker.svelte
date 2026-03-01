<script lang="ts">
  import { PaletteIcon } from 'lucide-svelte';

  type Theme = {
    name: string;
    vars: Record<string, string>;
  };

  const themes: Theme[] = [
    {
      name: 'Claude Light',
      vars: {
        'color-scheme': 'light',
        background: '#f5f4f0',
        surface: '#eeece7',
        'surface-hover': '#e5e2db',
        border: '#d4cfc7',
        'border-subtle': '#dedad3',
        text: '#1a1916',
        'text-muted': '#6b6760',
        'text-faint': '#a09c97',
        accent: '#b45309',
        'accent-hover': '#92400e',
        danger: '#dc2626',
      },
    },
    {
      name: 'Dark',
      vars: {
        'color-scheme': 'dark',
        background: '#0d0d0d',
        surface: '#141414',
        'surface-hover': '#1a1a1a',
        border: '#2a2a2a',
        'border-subtle': '#222',
        text: '#e8e8e8',
        'text-muted': '#888',
        'text-faint': '#555',
        accent: '#7c6ff7',
        'accent-hover': '#9489f9',
        danger: '#ef4444',
      },
    },
    {
      name: 'Midnight',
      vars: {
        'color-scheme': 'dark',
        background: '#0a0e1a',
        surface: '#111827',
        'surface-hover': '#1e2a3d',
        border: '#1e3a5f',
        'border-subtle': '#172035',
        text: '#e2e8f0',
        'text-muted': '#94a3b8',
        'text-faint': '#475569',
        accent: '#38bdf8',
        'accent-hover': '#7dd3fc',
        danger: '#ef4444',
      },
    },
    {
      name: 'Forest',
      vars: {
        'color-scheme': 'light',
        background: '#f2f5f0',
        surface: '#e8ede4',
        'surface-hover': '#dce4d6',
        border: '#c3cebc',
        'border-subtle': '#d2daca',
        text: '#1a2018',
        'text-muted': '#5a6b55',
        'text-faint': '#8fa088',
        accent: '#2d6a4f',
        'accent-hover': '#1b4332',
        danger: '#dc2626',
      },
    },
    {
      name: 'Rose',
      vars: {
        'color-scheme': 'light',
        background: '#fdf2f4',
        surface: '#fce7eb',
        'surface-hover': '#f9d0d8',
        border: '#f0b8c4',
        'border-subtle': '#f5cdd6',
        text: '#1f0a10',
        'text-muted': '#7e3a4d',
        'text-faint': '#b07585',
        accent: '#be123c',
        'accent-hover': '#9f1239',
        danger: '#dc2626',
      },
    },
    {
      name: 'Zinc',
      vars: {
        'color-scheme': 'dark',
        background: '#09090b',
        surface: '#18181b',
        'surface-hover': '#27272a',
        border: '#3f3f46',
        'border-subtle': '#27272a',
        text: '#fafafa',
        'text-muted': '#a1a1aa',
        'text-faint': '#52525b',
        accent: '#e4e4e7',
        'accent-hover': '#ffffff',
        danger: '#ef4444',
      },
    },
  ];

  let open = $state(false);

  function applyTheme(theme: Theme) {
    const root = document.documentElement;
    for (const [key, value] of Object.entries(theme.vars)) {
      if (key === 'color-scheme') {
        root.style.colorScheme = value;
      } else {
        root.style.setProperty(`--${key}`, value);
      }
    }
    localStorage.setItem('theme', JSON.stringify(theme));
    open = false;
  }

  // Restore saved theme on mount
  $effect(() => {
    const saved = localStorage.getItem('theme');
    if (saved) {
      try { applyTheme(JSON.parse(saved)); } catch {}
    }
  });

  // Preview color for each theme (the accent dot + bg)
  function swatchStyle(theme: Theme) {
    return `background: ${theme.vars.background}; border-color: ${theme.vars.border};`;
  }
  function accentStyle(theme: Theme) {
    return `background: ${theme.vars.accent};`;
  }
</script>

<div class="relative">
  <button
    onclick={() => (open = !open)}
    class="p-1.5 rounded text-text-muted hover:text-text hover:bg-surface-hover transition-colors"
    title="Change theme"
    aria-label="Change theme"
  >
    <PaletteIcon size={15} />
  </button>

  {#if open}
    <!-- Backdrop -->
    <button
      class="fixed inset-0 z-10"
      onclick={() => (open = false)}
      aria-label="Close theme picker"
    ></button>

    <!-- Popover -->
    <div class="absolute bottom-8 left-0 z-20 bg-surface border border-border rounded-xl shadow-xl p-3 w-52">
      <p class="text-xs font-medium text-text-muted mb-2 px-1">Theme</p>
      <div class="grid grid-cols-3 gap-2">
        {#each themes as theme}
          <button
            onclick={() => applyTheme(theme)}
            class="flex flex-col items-center gap-1.5 p-2 rounded-lg hover:bg-surface-hover transition-colors group"
            title={theme.name}
          >
            <!-- Swatch card -->
            <div
              class="w-12 h-8 rounded-md border flex items-end justify-end p-1"
              style={swatchStyle(theme)}
            >
              <div class="w-2.5 h-2.5 rounded-full" style={accentStyle(theme)}></div>
            </div>
            <span class="text-[10px] text-text-muted group-hover:text-text leading-none text-center">{theme.name}</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>
