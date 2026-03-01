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
      name: 'Sky',
      vars: {
        'color-scheme': 'light',
        background: '#f0f7ff',
        surface: '#e1effd',
        'surface-hover': '#cce3fb',
        border: '#a8d0f5',
        'border-subtle': '#bddaf8',
        text: '#0c1e35',
        'text-muted': '#3a6d9e',
        'text-faint': '#7aabcf',
        accent: '#0284c7',
        'accent-hover': '#0369a1',
        danger: '#dc2626',
      },
    },
    {
      name: 'Slate',
      vars: {
        'color-scheme': 'light',
        background: '#f8fafc',
        surface: '#f1f5f9',
        'surface-hover': '#e2e8f0',
        border: '#cbd5e1',
        'border-subtle': '#e2e8f0',
        text: '#0f172a',
        'text-muted': '#475569',
        'text-faint': '#94a3b8',
        accent: '#6366f1',
        'accent-hover': '#4f46e5',
        danger: '#dc2626',
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
      name: 'Honey',
      vars: {
        'color-scheme': 'light',
        background: '#fffbf5',
        surface: '#fff4e6',
        'surface-hover': '#ffead0',
        border: '#ffd59a',
        'border-subtle': '#ffe5b8',
        text: '#2d1a00',
        'text-muted': '#8a5a00',
        'text-faint': '#c48a3a',
        accent: '#d97706',
        'accent-hover': '#b45309',
        danger: '#dc2626',
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
