/**
 * Design tokens.
 *
 * Every colour resolves to a CSS variable defined in `index.css`, so the same
 * class works in light and dark mode. Only two families exist: neutrals (the
 * surfaces and the ink) and the four functional colours, which are reserved for
 * state and never used decoratively.
 *
 * @type {import('tailwindcss').Config}
 */
const withOpacity = (variable) => `rgb(var(${variable}) / <alpha-value>)`

module.exports = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // --- Surfaces -----------------------------------------------------
        //: Named `canvas`, not `base`: a colour called `base` would make
        //: `text-base` mean both "16px" and a text colour, and Tailwind emits
        //: both rules. The winner then depends on stylesheet order.
        canvas: withOpacity('--c-canvas'),
        panel: withOpacity('--c-panel'),
        elevated: withOpacity('--c-elevated'),
        line: withOpacity('--c-line'),
        'line-strong': withOpacity('--c-line-strong'),

        // --- Ink ----------------------------------------------------------
        ink: withOpacity('--c-ink'),
        'ink-2': withOpacity('--c-ink-2'),
        'ink-3': withOpacity('--c-ink-3'),

        // --- Single accent -------------------------------------------------
        accent: {
          DEFAULT: withOpacity('--c-accent'),
          soft: withOpacity('--c-accent-soft'),
          //: The far end of the brand gradient. Paired with `accent`, never
          //: used alone: on its own it is just another blue.
          2: withOpacity('--c-accent-2'),
          dim: 'rgb(var(--c-accent) / 0.12)',
        },

        // --- Functional status palette (reserved) --------------------------
        ok: {
          DEFAULT: withOpacity('--c-ok'),
          soft: withOpacity('--c-ok-soft'),
          dim: 'rgb(var(--c-ok) / 0.12)',
        },
        warn: {
          DEFAULT: withOpacity('--c-warn'),
          soft: withOpacity('--c-warn-soft'),
          dim: 'rgb(var(--c-warn) / 0.12)',
        },
        crit: {
          DEFAULT: withOpacity('--c-crit'),
          soft: withOpacity('--c-crit-soft'),
          dim: 'rgb(var(--c-crit) / 0.12)',
        },
        info: {
          DEFAULT: withOpacity('--c-info'),
          soft: withOpacity('--c-info-soft'),
          dim: 'rgb(var(--c-info) / 0.12)',
        },
        //: `risk` used to sit here, a fifth level between warn and crit. It was
        //: never used by a component, and squeezing it in made warn and crit
        //: indistinguishable to a colourblind reader. Three states, all proven
        //: separable, beat four that blur.
        //: Reserved for what the assistant suggests, so a recommendation is
        //: never mistaken for a measured state.
        ai: {
          DEFAULT: withOpacity('--c-ai'),
          soft: withOpacity('--c-ai-soft'),
          dim: 'rgb(var(--c-ai) / 0.12)',
        },

        // --- Categorical series (fixed order, never cycled) ----------------
        chart: {
          1: withOpacity('--c-chart-1'),
          2: withOpacity('--c-chart-2'),
          3: withOpacity('--c-chart-3'),
          4: withOpacity('--c-chart-4'),
        },

        // --- Sequential ramp (magnitude only) ------------------------------
        seq: {
          1: withOpacity('--c-seq-1'),
          2: withOpacity('--c-seq-2'),
          3: withOpacity('--c-seq-3'),
          4: withOpacity('--c-seq-4'),
          5: withOpacity('--c-seq-5'),
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'Consolas', 'monospace'],
      },
      fontSize: {
        //: 12px, not 11: below this the numerals in JetBrains Mono stop
        //: being separable at a glance, which is the whole point of them.
        '2xs': ['0.75rem', { lineHeight: '1.05rem' }],
      },
      letterSpacing: {
        widest2: '0.14em',
      },
      boxShadow: {
        panel: 'var(--shadow-panel)',
        lift: 'var(--shadow-lift)',
        glow: '0 0 0 1px rgb(var(--c-accent) / 0.25)',
      },
      keyframes: {
        pulseRing: {
          '0%': { opacity: '0.5', transform: 'scale(1)' },
          '70%': { opacity: '0', transform: 'scale(2.1)' },
          '100%': { opacity: '0', transform: 'scale(2.1)' },
        },
      },
      animation: {
        'pulse-ring': 'pulseRing 2.6s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
    },
  },
  plugins: [],
}
