import { defineConfig, presetUno, presetAttributify, presetIcons } from 'unocss'

/**
 * WindFlow UnoCSS Configuration
 * STORY-421: Dark Theme Palette
 *
 * Color tokens are defined in src/styles/theme.css as CSS custom properties.
 * This config provides UnoCSS shortcuts that reference those tokens.
 */

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify(),
    presetIcons({
      scale: 1.2,
      warn: true,
    }),
  ],
  theme: {
    colors: {
      // Primary accent (blue)
      accent: {
        DEFAULT: 'var(--color-accent)',
        hover: 'var(--color-accent-hover)',
        light: 'var(--color-accent-light)',
      },
      // Status colors
      success: {
        DEFAULT: 'var(--color-success)',
        light: 'var(--color-success-light)',
      },
      warning: {
        DEFAULT: 'var(--color-warning)',
        light: 'var(--color-warning-light)',
      },
      error: {
        DEFAULT: 'var(--color-error)',
        light: 'var(--color-error-light)',
      },
      info: {
        DEFAULT: 'var(--color-info)',
        light: 'var(--color-info-light)',
      },
      // Background colors
      bg: {
        primary: 'var(--color-bg-primary)',
        secondary: 'var(--color-bg-secondary)',
        card: 'var(--color-bg-card)',
        elevated: 'var(--color-bg-elevated)',
        hover: 'var(--color-bg-hover)',
        input: 'var(--color-bg-input)',
      },
      // Text colors
      text: {
        primary: 'var(--color-text-primary)',
        secondary: 'var(--color-text-secondary)',
        muted: 'var(--color-text-muted)',
        placeholder: 'var(--color-text-placeholder)',
      },
      // Border colors
      border: {
        DEFAULT: 'var(--color-border)',
        light: 'var(--color-border-light)',
        focus: 'var(--color-border-focus)',
      },
      // Legacy aliases for Element Plus compatibility
      primary: {
        DEFAULT: 'var(--color-accent)',
        light: 'var(--color-accent-hover)',
        lighter: 'var(--color-accent-light)',
        dark: 'var(--color-accent)',
      },
      danger: {
        DEFAULT: 'var(--color-error)',
        light: 'var(--color-error-light)',
        dark: 'var(--color-error)',
      },
    },
  },
  shortcuts: {
    // Layout
    'flex-center': 'flex items-center justify-center',
    'flex-between': 'flex items-center justify-between',
    'flex-col-center': 'flex flex-col items-center justify-center',

    // Card styles
    'card': 'bg-bg-card rounded-lg shadow-md p-4 border border-border',
    'card-elevated': 'bg-bg-elevated rounded-lg shadow-lg p-4 border border-border',

    // Button base
    'btn': 'px-4 py-2 rounded cursor-pointer transition-all duration-200',
    'btn-primary': 'btn bg-accent text-white hover:bg-accent-hover',
    'btn-secondary': 'btn bg-bg-elevated text-text-primary border border-border hover:bg-bg-hover',
    'btn-success': 'btn bg-success text-white hover:opacity-90',
    'btn-warning': 'btn bg-warning text-white hover:opacity-90',
    'btn-danger': 'btn bg-error text-white hover:opacity-90',
    'btn-ghost': 'btn bg-transparent text-text-secondary hover:bg-bg-hover hover:text-text-primary',

    // Text styles
    'text-heading': 'text-text-primary font-semibold',
    'text-body': 'text-text-primary',
    'text-muted': 'text-text-secondary',
    'text-label': 'text-text-secondary text-sm',

    // Input styles
    'input-base': 'bg-bg-input border border-border rounded text-text-primary placeholder-text-placeholder focus:border-accent focus:outline-none transition-colors',

    // Status badges
    'badge': 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
    'badge-success': 'badge bg-success-light text-success',
    'badge-warning': 'badge bg-warning-light text-warning',
    'badge-error': 'badge bg-error-light text-error',
    'badge-info': 'badge bg-info-light text-info',

    // Dividers
    'divider': 'border-t border-border',
    'divider-vertical': 'border-l border-border h-full',
  },
})
