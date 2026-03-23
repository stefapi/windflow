/**
 * CSS Custom Properties utilities
 * STORY-508: Design System — Helper pour lire les variables CSS thémées au runtime
 *
 * Permet aux librairies JS (ECharts, etc.) d'utiliser les couleurs thémées WindFlow
 * qui sont définies comme CSS custom properties dans theme.css.
 */

/**
 * Lit la valeur d'une CSS custom property au runtime.
 * Utilisé pour passer des couleurs thémées aux libs JS (ECharts, etc.)
 * qui ne supportent pas les CSS variables directement.
 *
 * @param name - Nom de la variable CSS (ex: '--color-accent')
 * @returns Valeur résolue de la variable CSS au moment de l'appel
 *
 * @example
 * const accentColor = getCssVar('--color-accent')
 * // Returns: '#3b82f6' (dark) or '#2563eb' (light)
 */
export function getCssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

/**
 * Retourne un rgba() à partir d'une CSS custom property hexadécimale et d'une opacité.
 * Utile pour les gradients ECharts (colorStops) qui nécessitent des valeurs rgba concrètes.
 *
 * @param varName - Nom de la variable CSS hexadécimale (ex: '--color-accent')
 * @param opacity - Opacité entre 0 et 1
 * @returns Chaîne rgba() avec la couleur résolue et l'opacité spécifiée
 *
 * @example
 * const gradientStart = getCssVarRgba('--color-accent', 0.4)
 * // Returns: 'rgba(59, 130, 246, 0.4)' (dark) or 'rgba(37, 99, 235, 0.4)' (light)
 */
export function getCssVarRgba(varName: string, opacity: number): string {
  const hex = getCssVar(varName)
  // Convertir hex (#rrggbb ou #rgb) en rgb
  const full = hex.startsWith('#') ? hex : '#000000'
  let r: number
  let g: number
  let b: number

  if (full.length === 4) {
    // Format court #rgb → expand to #rrggbb
    r = parseInt(full[1] + full[1], 16)
    g = parseInt(full[2] + full[2], 16)
    b = parseInt(full[3] + full[3], 16)
  }
  else {
    r = parseInt(full.slice(1, 3), 16)
    g = parseInt(full.slice(3, 5), 16)
    b = parseInt(full.slice(5, 7), 16)
  }

  return `rgba(${r}, ${g}, ${b}, ${opacity})`
}
