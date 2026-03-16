/**
 * Composable pour la gestion de l'état responsive de la sidebar
 * STORY-413 : Responsive sidebar rétractable
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'

// Breakpoints alignés avec les AC de la STORY-413
const BREAKPOINTS = {
  MOBILE: 768,    // ≤767px : sidebar cachée
  TABLET: 1024,   // 768px–1023px : sidebar rétractée
  DESKTOP: 1024,  // ≥1024px : sidebar complète
} as const

// Clé localStorage pour la persistance
const STORAGE_KEY = 'windflow-sidebar-collapsed'

// État global partagé (singleton)
const isCollapsed = ref(false)
const isMobileOpen = ref(false)
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1024)

/**
 * Détecte le type d'écran actuel
 */
function getScreenType(): 'mobile' | 'tablet' | 'desktop' {
  if (windowWidth.value < BREAKPOINTS.MOBILE) {
    return 'mobile'
  }
  if (windowWidth.value < BREAKPOINTS.TABLET) {
    return 'tablet'
  }
  return 'desktop'
}

/**
 * Charge l'état depuis localStorage
 */
function loadFromStorage(): boolean {
  if (typeof localStorage === 'undefined') return false
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'true'
}

/**
 * Sauvegarde l'état dans localStorage
 */
function saveToStorage(collapsed: boolean): void {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(STORAGE_KEY, String(collapsed))
}

/**
 * Composable useSidebar
 * Gère l'état réactif de la sidebar avec support responsive
 */
export function useSidebar() {
  // Computed pour le type d'écran
  const screenType = computed(() => getScreenType())

  // Computed pour savoir si on est en mode mobile
  const isMobile = computed(() => screenType.value === 'mobile')

  // Computed pour savoir si on est en mode tablette
  const isTablet = computed(() => screenType.value === 'tablet')

  // Computed pour savoir si on est en mode desktop
  const isDesktop = computed(() => screenType.value === 'desktop')

  // État effectif de la sidebar selon l'écran
  // - Mobile : toujours cachée (sauf si ouverte via hamburger)
  // - Tablette : rétractée par défaut
  // - Desktop : état personnalisé ou complet par défaut
  const effectiveCollapsed = computed(() => {
    if (isMobile.value) {
      return true // Sur mobile, la sidebar est toujours "collapsed" (cachée)
    }
    if (isTablet.value) {
      return true // Sur tablette, rétractée par défaut
    }
    return isCollapsed.value // Sur desktop, état personnalisé
  })

  /**
   * Toggle l'état rétracté (desktop uniquement)
   */
  function toggle(): void {
    if (!isDesktop.value) return
    isCollapsed.value = !isCollapsed.value
    saveToStorage(isCollapsed.value)
  }

  /**
   * Définit l'état rétracté explicitement
   */
  function setCollapsed(collapsed: boolean): void {
    if (!isDesktop.value) return
    isCollapsed.value = collapsed
    saveToStorage(collapsed)
  }

  /**
   * Ouvre la sidebar mobile (hamburger)
   */
  function openMobile(): void {
    if (!isMobile.value) return
    isMobileOpen.value = true
  }

  /**
   * Ferme la sidebar mobile
   */
  function closeMobile(): void {
    isMobileOpen.value = false
  }

  /**
   * Toggle la sidebar mobile
   */
  function toggleMobile(): void {
    if (!isMobile.value) return
    isMobileOpen.value = !isMobileOpen.value
  }

  /**
   * Gestion du redimensionnement de la fenêtre
   */
  function handleResize(): void {
    windowWidth.value = window.innerWidth

    // Fermer la sidebar mobile si on passe sur un écran plus grand
    if (!isMobile.value) {
      isMobileOpen.value = false
    }
  }

  // Lifecycle hooks
  onMounted(() => {
    // Charger l'état sauvegardé
    isCollapsed.value = loadFromStorage()

    // Initialiser la largeur
    windowWidth.value = window.innerWidth

    // Écouter les changements de taille
    window.addEventListener('resize', handleResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
  })

  return {
    // État
    isCollapsed: effectiveCollapsed,
    isMobileOpen,
    screenType,
    isMobile,
    isTablet,
    isDesktop,
    windowWidth,

    // Largeur de la sidebar selon l'état
    sidebarWidth: computed(() => {
      if (isMobile.value) return 0 // Cachée sur mobile
      if (effectiveCollapsed.value) return 64 // Rétractée (icônes uniquement)
      return 220 // Complète
    }),

    // Actions
    toggle,
    setCollapsed,
    openMobile,
    closeMobile,
    toggleMobile,
  }
}

// Export des breakpoints pour les tests
export { BREAKPOINTS }
