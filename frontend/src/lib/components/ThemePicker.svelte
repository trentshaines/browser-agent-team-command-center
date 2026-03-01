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
      name: 'Sage',
      vars: {
        'color-scheme': 'light',
        background: '#f3f5f1',
        surface: '#eaece7',
        'surface-hover': '#e0e4dc',
        border: '#cdd1c8',
        'border-subtle': '#d8dbd4',
        text: '#1a1c18',
        'text-muted': '#636860',
        'text-faint': '#9da39a',
        accent: '#5a7a62',
        'accent-hover': '#436350',
        danger: '#dc2626',
      },
    },
    {
      name: 'Dusk',
      vars: {
        'color-scheme': 'light',
        background: '#f5f4f6',
        surface: '#eeeced',
        'surface-hover': '#e5e2e8',
        border: '#d4cfd7',
        'border-subtle': '#dedad0',
        text: '#1a1620',
        'text-muted': '#6b6070',
        'text-faint': '#a09ca8',
        accent: '#7c6a8d',
        'accent-hover': '#63557a',
        danger: '#dc2626',
      },
    },
    {
      name: 'Mist',
      vars: {
        'color-scheme': 'light',
        background: '#f3f4f7',
        surface: '#eaedf2',
        'surface-hover': '#dce2ea',
        border: '#c8ced9',
        'border-subtle': '#d5dae3',
        text: '#141820',
        'text-muted': '#586070',
        'text-faint': '#8e98a8',
        accent: '#4a6b8a',
        'accent-hover': '#3a5572',
        danger: '#dc2626',
      },
    },
    {
      name: 'Clay',
      vars: {
        'color-scheme': 'light',
        background: '#f5f3f0',
        surface: '#eeeae6',
        'surface-hover': '#e6e0da',
        border: '#d4cdc6',
        'border-subtle': '#ddd7d0',
        text: '#1e1714',
        'text-muted': '#6e6058',
        'text-faint': '#a89c96',
        accent: '#9b4a3a',
        'accent-hover': '#7d3a2c',
        danger: '#dc2626',
      },
    },
    {
      name: 'Stone',
      vars: {
        'color-scheme': 'light',
        background: '#f6f5f3',
        surface: '#efeeed',
        'surface-hover': '#e6e4e1',
        border: '#d5d2ce',
        'border-subtle': '#dedad7',
        text: '#1c1b19',
        'text-muted': '#6d6b67',
        'text-faint': '#a3a09c',
        accent: '#5c7a7a',
        'accent-hover': '#486464',
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
