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

    // Card styles - Dark mode compatible
    'card': 'bg-[var(--color-bg-card)] rounded-lg shadow-md p-4 border border-[var(--color-border)] text-[var(--color-text-primary)]',
    'card-elevated': 'bg-[var(--color-bg-elevated)] rounded-lg shadow-lg p-4 border border-[var(--color-border)] text-[var(--color-text-primary)]',
    'card-interactive': 'bg-[var(--color-bg-card)] rounded-lg shadow-md p-4 border border-[var(--color-border)] text-[var(--color-text-primary)] hover:bg-[var(--color-bg-hover)] cursor-pointer transition-all duration-200',
    'card-header': 'bg-[var(--color-bg-elevated)] text-[var(--color-text-primary)] border-b border-[var(--color-border)]',

    // Panel styles (for sections like capabilities, logs, etc.) - Dark mode compatible
    'panel': 'bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)] text-[var(--color-text-primary)]',
    'panel-elevated': 'bg-[var(--color-bg-elevated)] rounded-lg border border-[var(--color-border)] text-[var(--color-text-primary)]',

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

    // Logs console styles
    'logs-container': 'bg-bg-primary rounded-lg border border-border font-mono text-sm',
    'logs-header': 'bg-bg-elevated border-b border-border px-4 py-3',
    'logs-footer': 'bg-bg-elevated border-t border-border px-4 py-3',
    'logs-content': 'bg-bg-primary p-4 overflow-auto',

    // Log level text colors
    'log-error': 'text-[var(--color-log-error)]',
    'log-warning': 'text-[var(--color-log-warning)]',
    'log-info': 'text-[var(--color-log-info)]',
    'log-debug': 'text-[var(--color-log-debug)] italic',
    'log-line-number': 'text-[var(--color-log-line-number)] select-none pr-3 text-right',

    // Code blocks styling
    'code-block': 'bg-[var(--color-code-bg)] text-[var(--color-code-fg)] font-mono p-4 rounded-lg',
    'code-console': 'bg-[var(--color-terminal-bg)] text-[var(--color-terminal-fg)] font-mono p-4 rounded-lg',
    'code-inline': 'bg-[var(--color-code-bg)] text-[var(--color-code-fg)] font-mono px-1.5 py-0.5 rounded text-sm',

    // Table styles
    'table-container': 'bg-bg-card rounded-lg border border-border overflow-hidden',
    'table-header': 'bg-bg-elevated',
    'table-row': 'hover:bg-bg-hover transition-colors',
    'table-row-alternate': 'bg-bg-secondary',

    // Terminal styles
    'terminal-container': 'bg-[var(--color-terminal-bg)] flex-1 p-2 overflow-hidden',
    'terminal-wrapper': 'flex flex-col h-full min-h-400px bg-[var(--el-bg-color)] rounded overflow-hidden',
    'terminal-toolbar': 'flex justify-between items-center p-2 bg-[var(--el-bg-color-overlay)] border-b border-[var(--el-border-color-lighter)] flex-shrink-0 flex-wrap gap-2',
    'terminal-status-dot': 'w-2 h-2 rounded-full',
    'terminal-status-connected': 'terminal-status-dot bg-[var(--color-success)] animate-pulse',
    'terminal-status-connecting': 'terminal-status-dot bg-[var(--color-warning)]',
    'terminal-status-disconnected': 'terminal-status-dot bg-[var(--color-info)]',

    // Login page styles
    'login-page': 'min-h-screen flex-center relative overflow-hidden bg-bg-primary',
    'login-card': 'relative z-1 w-full max-w-420px px-10 pt-12 pb-9 rounded-2xl backdrop-blur-xl border border-border-light bg-[var(--color-bg-card-alpha)] shadow-lg',
    'login-card-header': 'flex flex-col items-center mb-9',
    'login-card-title': 'my-4 text-28px font-bold text-text-primary tracking-wide',
    'login-card-subtitle': 'm-0 text-13px text-text-secondary tracking-wide',
    'login-card-form': 'w-full',
    'login-card-footer': 'flex justify-center mt-6 pt-4 border-t border-border-light',
    'login-card-version': 'text-11px text-text-muted tracking-wide',
    'login-btn': 'w-full py-14px rounded-10px text-white font-semibold text-15px tracking-wide cursor-pointer transition-all duration-300 bg-gradient-to-br from-border-focus via-accent to-accent-hover',
    'login-btn-hover': 'hover:-translate-y-0.5 hover:shadow-[0_4px_20px_var(--color-accent-light)]',
    'login-btn-loading': 'bg-gradient-to-br from-accent to-accent-hover opacity-70 cursor-not-allowed',
    'login-spinner': 'inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin',
    'login-particle': 'absolute rounded-full bg-accent-light blur-40px',
  },
})
