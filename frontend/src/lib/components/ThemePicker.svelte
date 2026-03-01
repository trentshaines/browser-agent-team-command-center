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
    {
      name: 'Linen',
      vars: {
        'color-scheme': 'light',
        background: '#faf8f5',
        surface: '#f3f0ea',
        'surface-hover': '#ebe6de',
        border: '#d9d2c8',
        'border-subtle': '#e3ddd5',
        text: '#1c1a17',
        'text-muted': '#6e6257',
        'text-faint': '#a89e94',
        accent: '#a05070',
        'accent-hover': '#843d5b',
        danger: '#dc2626',
      },
    },
    {
      name: 'Parchment',
      vars: {
        'color-scheme': 'light',
        background: '#faf7f0',
        surface: '#f2ebd8',
        'surface-hover': '#e9e1cc',
        border: '#d3c8ae',
        'border-subtle': '#ddd4be',
        text: '#1e1a12',
        'text-muted': '#6e6048',
        'text-faint': '#a8977a',
        accent: '#8b6914',
        'accent-hover': '#6f5210',
        danger: '#dc2626',
      },
    },
    {
      name: 'Ash',
      vars: {
        'color-scheme': 'light',
        background: '#f7f7f7',
        surface: '#f0f0f0',
        'surface-hover': '#e6e6e6',
        border: '#d0d0d0',
        'border-subtle': '#dcdcdc',
        text: '#1a1a1a',
        'text-muted': '#666666',
        'text-faint': '#999999',
        accent: '#444444',
        'accent-hover': '#222222',
        danger: '#dc2626',
      },
    },
    {
      name: 'Lavender',
      vars: {
        'color-scheme': 'light',
        background: '#f5f4f8',
        surface: '#eeedf4',
        'surface-hover': '#e4e3ed',
        border: '#ceccda',
        'border-subtle': '#d8d7e4',
        text: '#18162a',
        'text-muted': '#635e7a',
        'text-faint': '#9e99b0',
        accent: '#6b5ea8',
        'accent-hover': '#574c8e',
        danger: '#dc2626',
      },
    },
    {
      name: 'Mint',
      vars: {
        'color-scheme': 'light',
        background: '#f3f7f5',
        surface: '#e9efec',
        'surface-hover': '#dde8e3',
        border: '#c5d5ce',
        'border-subtle': '#d3e0db',
        text: '#141e1a',
        'text-muted': '#4e6b62',
        'text-faint': '#8aada4',
        accent: '#2d7a63',
        'accent-hover': '#1f5f4c',
        danger: '#dc2626',
      },
    },
    {
      name: 'Peach',
      vars: {
        'color-scheme': 'light',
        background: '#faf5f2',
        surface: '#f3ece7',
        'surface-hover': '#ebe1da',
        border: '#d8c9bf',
        'border-subtle': '#e3d5cc',
        text: '#1e150f',
        'text-muted': '#6e5548',
        'text-faint': '#a88e83',
        accent: '#c05c35',
        'accent-hover': '#9a4827',
        danger: '#dc2626',
      },
    },
    {
      name: 'Frost',
      vars: {
        'color-scheme': 'light',
        background: '#f2f5f8',
        surface: '#e8eef4',
        'surface-hover': '#dae4ee',
        border: '#bfcfdd',
        'border-subtle': '#cfdae8',
        text: '#10181f',
        'text-muted': '#485a6a',
        'text-faint': '#8598a8',
        accent: '#3a6e8a',
        'accent-hover': '#2c5570',
        danger: '#dc2626',
      },
    },
    {
      name: 'Sepia',
      vars: {
        'color-scheme': 'light',
        background: '#f7f2e8',
        surface: '#f0e8d8',
        'surface-hover': '#e6dbc8',
        border: '#cfc0a8',
        'border-subtle': '#dacbb8',
        text: '#241a0a',
        'text-muted': '#72583a',
        'text-faint': '#b09070',
        accent: '#7a4f28',
        'accent-hover': '#5e3c1e',
        danger: '#dc2626',
      },
    },
    {
      name: 'Paper',
      vars: {
        'color-scheme': 'light',
        background: '#fefefe',
        surface: '#f8f8f8',
        'surface-hover': '#f0f0f0',
        border: '#e0e0e0',
        'border-subtle': '#e8e8e8',
        text: '#111111',
        'text-muted': '#555555',
        'text-faint': '#999999',
        accent: '#1a1a1a',
        'accent-hover': '#000000',
        danger: '#dc2626',
      },
    },
    {
      name: 'Blush',
      vars: {
        'color-scheme': 'light',
        background: '#f8f4f4',
        surface: '#f2ecec',
        'surface-hover': '#e9e0e0',
        border: '#d8cece',
        'border-subtle': '#e3d8d8',
        text: '#1e1616',
        'text-muted': '#6b5a5a',
        'text-faint': '#a89090',
        accent: '#956060',
        'accent-hover': '#7a4c4c',
        danger: '#dc2626',
      },
    },
    {
      name: 'Solarized',
      vars: {
        'color-scheme': 'light',
        background: '#fdf6e3',
        surface: '#eee8d5',
        'surface-hover': '#e1dbc8',
        border: '#ccc4af',
        'border-subtle': '#d8d2be',
        text: '#073642',
        'text-muted': '#586e75',
        'text-faint': '#839496',
        accent: '#268bd2',
        'accent-hover': '#1e6fa8',
        danger: '#dc2626',
      },
    },
    {
      name: 'Gruvbox',
      vars: {
        'color-scheme': 'light',
        background: '#fbf1c7',
        surface: '#f2e5bc',
        'surface-hover': '#ebdbb2',
        border: '#d5c4a1',
        'border-subtle': '#e0d3b0',
        text: '#282828',
        'text-muted': '#504945',
        'text-faint': '#928374',
        accent: '#d65d0e',
        'accent-hover': '#af3a03',
        danger: '#cc241d',
      },
    },
    {
      name: 'Nord',
      vars: {
        'color-scheme': 'light',
        background: '#eceff4',
        surface: '#e5e9f0',
        'surface-hover': '#d8dee9',
        border: '#c0c8d8',
        'border-subtle': '#cbd3e3',
        text: '#2e3440',
        'text-muted': '#4c566a',
        'text-faint': '#7b88a1',
        accent: '#5e81ac',
        'accent-hover': '#4c6f99',
        danger: '#bf616a',
      },
    },
    {
      name: 'Catppuccin',
      vars: {
        'color-scheme': 'light',
        background: '#eff1f5',
        surface: '#e6e9ef',
        'surface-hover': '#dce0e8',
        border: '#bcc0cc',
        'border-subtle': '#ccd0da',
        text: '#4c4f69',
        'text-muted': '#6c6f85',
        'text-faint': '#9ca0b0',
        accent: '#1e66f5',
        'accent-hover': '#186ee0',
        danger: '#d20f39',
      },
    },
    {
      name: 'Coffee',
      vars: {
        'color-scheme': 'light',
        background: '#f5f0eb',
        surface: '#ede6de',
        'surface-hover': '#e3d9cf',
        border: '#c8bcb0',
        'border-subtle': '#d8cec4',
        text: '#1a120a',
        'text-muted': '#6b5548',
        'text-faint': '#a89080',
        accent: '#6f4e37',
        'accent-hover': '#573c2a',
        danger: '#dc2626',
      },
    },
    {
      name: 'Coastal',
      vars: {
        'color-scheme': 'light',
        background: '#f2f6f8',
        surface: '#e8f0f4',
        'surface-hover': '#dae7ee',
        border: '#b8ced9',
        'border-subtle': '#c8dae3',
        text: '#0e1e28',
        'text-muted': '#456070',
        'text-faint': '#80a0b0',
        accent: '#2e7090',
        'accent-hover': '#1e5a74',
        danger: '#dc2626',
      },
    },
    {
      name: 'Wheat',
      vars: {
        'color-scheme': 'light',
        background: '#faf8f0',
        surface: '#f3efda',
        'surface-hover': '#eae5cc',
        border: '#d8cfb0',
        'border-subtle': '#e3d8bc',
        text: '#1c1a10',
        'text-muted': '#665e3a',
        'text-faint': '#a89c6a',
        accent: '#8b7030',
        'accent-hover': '#6e5824',
        danger: '#dc2626',
      },
    },
    {
      name: 'Mauve',
      vars: {
        'color-scheme': 'light',
        background: '#f6f3f8',
        surface: '#ede9f2',
        'surface-hover': '#e4deed',
        border: '#cdc5d8',
        'border-subtle': '#d8d2e4',
        text: '#1a1420',
        'text-muted': '#625a72',
        'text-faint': '#9e95ae',
        accent: '#8060a0',
        'accent-hover': '#664d85',
        danger: '#dc2626',
      },
    },
    {
      name: 'Everforest',
      vars: {
        'color-scheme': 'light',
        background: '#f2efdf',
        surface: '#eae6d0',
        'surface-hover': '#e0dbc5',
        border: '#c2bcab',
        'border-subtle': '#cfc9b8',
        text: '#5c6a72',
        'text-muted': '#708089',
        'text-faint': '#9da9a0',
        accent: '#8da101',
        'accent-hover': '#6e7c00',
        danger: '#dc2626',
      },
    },
    {
      name: 'Tokyo Day',
      vars: {
        'color-scheme': 'light',
        background: '#e1e2e7',
        surface: '#d5d6db',
        'surface-hover': '#c9cad0',
        border: '#b0b2be',
        'border-subtle': '#c4c6d3',
        text: '#3760bf',
        'text-muted': '#6172b0',
        'text-faint': '#8990b3',
        accent: '#2e7de9',
        'accent-hover': '#1a6bdb',
        danger: '#f52a65',
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
      <div class="grid grid-cols-3 gap-2 max-h-72 overflow-y-auto">
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
