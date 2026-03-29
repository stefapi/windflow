<template>
  <div
    class="windflow-logo"
    :class="[
      `windflow-logo--${size}`,
      `windflow-logo--${variant}`,
      { 'windflow-logo--animate': animate },
    ]"
  >
    <svg
      class="windflow-logo__svg"
      :width="svgSize"
      :height="svgSize"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="WindFlow Logo"
      :style="{ color: strokeColor }"
      v-html="svgInnerContent"
    />
    <span
      v-if="showText"
      class="windflow-logo__text"
    >
      Wind<span class="windflow-logo__text-accent">Flow</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import svgRaw from '@/assets/windflow-logo.svg?raw'

type LogoSize = 'small' | 'medium' | 'large'
type LogoVariant = 'light' | 'dark' | 'auto'

interface Props {
  /** Taille du logo : small (24px), medium (48px), large (80px) */
  size?: LogoSize
  /** Active l'animation de pulsation douce du logo */
  animate?: boolean
  /** Affiche le texte "WindFlow" à côté du logo */
  showText?: boolean
  /** Variante de couleur : light (fond clair), dark (fond sombre), auto (détection CSS) */
  variant?: LogoVariant
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium',
  animate: false,
  showText: false,
  variant: 'auto',
})

const sizeMap: Record<LogoSize, number> = {
  small: 24,
  medium: 48,
  large: 80,
}

const svgSize = computed(() => sizeMap[props.size])

/**
 * Extracts the inner content (paths) from the imported SVG file.
 * The SVG file (windflow-logo.svg) is the single source of truth for the logo design.
 * The outer <svg> wrapper is managed by the template for dynamic attributes.
 */
const svgInnerContent = computed(() => {
  const match = svgRaw.match(/<svg[^>]*>([\s\S]*)<\/svg>/)
  return match?.[1] ?? ''
})

/**
 * Color applied via CSS `color` property, which feeds `currentColor` in the SVG paths.
 * Uses theme CSS variables for consistent theming.
 */
const strokeColor = computed(() => {
  if (props.variant === 'light') return 'var(--color-accent)'
  if (props.variant === 'dark') return 'var(--color-accent-hover)'
  // 'auto' — uses CSS custom property, falls back to theme accent
  return 'var(--windflow-logo-color, var(--color-accent))'
})
</script>

<style scoped>
.windflow-logo {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.windflow-logo__svg {
  flex-shrink: 0;
}

/* Animation : pulsation douce */
.windflow-logo--animate .windflow-logo__svg {
  animation: windflow-pulse 4s ease-in-out infinite;
}

@keyframes windflow-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }

  50% {
    transform: scale(1.04);
    opacity: 0.85;
  }
}

/* Texte - utilise les variables CSS globales du thème */
.windflow-logo__text {
  overflow: hidden;
  white-space: nowrap;
  color: var(--color-text-primary);
  font-weight: 500;
  letter-spacing: 0.01em;
}

.windflow-logo__text-accent {
  color: var(--color-accent);
}

.windflow-logo--small .windflow-logo__text {
  font-size: 14px;
}

.windflow-logo--medium .windflow-logo__text {
  font-size: 20px;
}

.windflow-logo--large .windflow-logo__text {
  font-size: 28px;
}

/* Variant overrides using theme CSS variables */
.windflow-logo--dark .windflow-logo__text {
  color: var(--color-text-primary);
}

.windflow-logo--dark .windflow-logo__text-accent {
  color: var(--color-accent-hover);
}

.windflow-logo--light .windflow-logo__text {
  color: var(--color-text-primary);
}

.windflow-logo--light .windflow-logo__text-accent {
  color: var(--color-accent);
}
</style>
