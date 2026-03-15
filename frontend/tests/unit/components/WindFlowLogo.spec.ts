/**
 * Tests unitaires pour WindFlowLogo.vue
 * STORY-471 : Refonte Page Login avec Design Unifié et Nouveau Logo
 *
 * Le composant charge le SVG depuis @/assets/windflow-logo.svg (source de vérité)
 * via un import ?raw, et injecte les paths via v-html.
 * La couleur est contrôlée via la propriété CSS `color` (qui alimente `currentColor`).
 */
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Mock the ?raw SVG import — reproduces the canonical SVG file content
vi.mock('@/assets/windflow-logo.svg?raw', () => ({
  default: `<svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 22 C20 18, 30 18, 38 22 C46 26, 52 22, 56 18" stroke="currentColor" stroke-width="3" stroke-linecap="round" fill="none" opacity="0.45"/>
  <path d="M8 32 C18 26, 30 26, 40 32 C50 38, 56 32, 60 26" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" fill="none"/>
  <path d="M12 42 C20 38, 30 38, 38 42 C46 46, 52 42, 56 38" stroke="currentColor" stroke-width="3" stroke-linecap="round" fill="none" opacity="0.45"/>
</svg>`,
}))

import WindFlowLogo from '@/components/WindFlowLogo.vue'

describe('WindFlowLogo', () => {
  describe('Rendu par défaut', () => {
    it('rend le composant avec les props par défaut', () => {
      const wrapper = mount(WindFlowLogo)

      expect(wrapper.find('.windflow-logo').exists()).toBe(true)
      expect(wrapper.find('.windflow-logo__svg').exists()).toBe(true)
    })

    it('ne affiche pas le texte par défaut', () => {
      const wrapper = mount(WindFlowLogo)

      expect(wrapper.find('.windflow-logo__text').exists()).toBe(false)
    })

    it('ne active pas l\'animation par défaut', () => {
      const wrapper = mount(WindFlowLogo)

      expect(wrapper.find('.windflow-logo--animate').exists()).toBe(false)
    })

    it('utilise la taille medium par défaut', () => {
      const wrapper = mount(WindFlowLogo)

      expect(wrapper.find('.windflow-logo--medium').exists()).toBe(true)
      const svg = wrapper.find('.windflow-logo__svg')
      expect(svg.attributes('width')).toBe('48')
      expect(svg.attributes('height')).toBe('48')
    })
  })

  describe('Prop size', () => {
    it('rend en taille small (24px)', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { size: 'small' },
      })

      expect(wrapper.find('.windflow-logo--small').exists()).toBe(true)
      const svg = wrapper.find('.windflow-logo__svg')
      expect(svg.attributes('width')).toBe('24')
      expect(svg.attributes('height')).toBe('24')
    })

    it('rend en taille medium (48px)', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { size: 'medium' },
      })

      expect(wrapper.find('.windflow-logo--medium').exists()).toBe(true)
      const svg = wrapper.find('.windflow-logo__svg')
      expect(svg.attributes('width')).toBe('48')
      expect(svg.attributes('height')).toBe('48')
    })

    it('rend en taille large (80px)', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { size: 'large' },
      })

      expect(wrapper.find('.windflow-logo--large').exists()).toBe(true)
      const svg = wrapper.find('.windflow-logo__svg')
      expect(svg.attributes('width')).toBe('80')
      expect(svg.attributes('height')).toBe('80')
    })
  })

  describe('Prop animate', () => {
    it('active l\'animation quand animate=true', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { animate: true },
      })

      expect(wrapper.find('.windflow-logo--animate').exists()).toBe(true)
    })

    it('désactive l\'animation quand animate=false', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { animate: false },
      })

      expect(wrapper.find('.windflow-logo--animate').exists()).toBe(false)
    })
  })

  describe('Prop showText', () => {
    it('affiche le texte "WindFlow" quand showText=true', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { showText: true },
      })

      const text = wrapper.find('.windflow-logo__text')
      expect(text.exists()).toBe(true)
      expect(text.text()).toBe('WindFlow')
    })

    it('cache le texte quand showText=false', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { showText: false },
      })

      expect(wrapper.find('.windflow-logo__text').exists()).toBe(false)
    })
  })

  describe('SVG et accessibilité', () => {
    it('contient un SVG avec role="img"', () => {
      const wrapper = mount(WindFlowLogo)

      const svg = wrapper.find('svg')
      expect(svg.exists()).toBe(true)
      expect(svg.attributes('role')).toBe('img')
    })

    it('contient un aria-label pour l\'accessibilité', () => {
      const wrapper = mount(WindFlowLogo)

      const svg = wrapper.find('svg')
      expect(svg.attributes('aria-label')).toBe('WindFlow Logo')
    })

    it('contient des paths de flux (lignes courbes) chargés depuis le SVG externe', () => {
      const wrapper = mount(WindFlowLogo)

      const paths = wrapper.findAll('path')
      expect(paths.length).toBeGreaterThanOrEqual(3)
    })

    it('utilise currentColor comme stroke dans les paths (délégué au fichier SVG)', () => {
      const wrapper = mount(WindFlowLogo)

      const paths = wrapper.findAll('path')
      for (const path of paths) {
        expect(path.attributes('stroke')).toBe('currentColor')
      }
    })
  })

  describe('Prop variant', () => {
    it('applique la classe windflow-logo--auto par défaut', () => {
      const wrapper = mount(WindFlowLogo)

      expect(wrapper.find('.windflow-logo--auto').exists()).toBe(true)
    })

    it('applique la classe windflow-logo--dark quand variant="dark"', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { variant: 'dark' },
      })

      expect(wrapper.find('.windflow-logo--dark').exists()).toBe(true)
    })

    it('applique la classe windflow-logo--light quand variant="light"', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { variant: 'light' },
      })

      expect(wrapper.find('.windflow-logo--light').exists()).toBe(true)
    })

    it('applique la couleur CSS #60a5fa en variant dark (pour currentColor)', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { variant: 'dark' },
      })

      const svg = wrapper.find('.windflow-logo__svg')
      // jsdom converts hex to rgb() format
      expect(svg.attributes('style')).toContain('color: rgb(96, 165, 250)')
    })

    it('applique la couleur CSS #3b82f6 en variant light (pour currentColor)', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { variant: 'light' },
      })

      const svg = wrapper.find('.windflow-logo__svg')
      // jsdom converts hex to rgb() format
      expect(svg.attributes('style')).toContain('color: rgb(59, 130, 246)')
    })

    it('utilise la CSS custom property en variant auto', () => {
      const wrapper = mount(WindFlowLogo, {
        props: { variant: 'auto' },
      })

      const svg = wrapper.find('.windflow-logo__svg')
      expect(svg.attributes('style')).toContain('--windflow-logo-color')
    })
  })

  describe('Chargement SVG depuis fichier externe', () => {
    it('injecte le contenu SVG interne via v-html', () => {
      const wrapper = mount(WindFlowLogo)

      const svg = wrapper.find('svg')
      // Le SVG doit contenir les paths injectés via v-html
      expect(svg.html()).toContain('M12 22')
      expect(svg.html()).toContain('M8 32')
      expect(svg.html()).toContain('M12 42')
    })

    it('conserve le viewBox 0 0 64 64 du design original', () => {
      const wrapper = mount(WindFlowLogo)

      const svg = wrapper.find('svg')
      // SVG viewBox attribute is case-sensitive (camelCase)
      expect(svg.attributes('viewBox')).toBe('0 0 64 64')
    })
  })

  describe('Combinaison de props', () => {
    it('rend correctement avec toutes les props', () => {
      const wrapper = mount(WindFlowLogo, {
        props: {
          size: 'large',
          animate: true,
          showText: true,
        },
      })

      expect(wrapper.find('.windflow-logo--large').exists()).toBe(true)
      expect(wrapper.find('.windflow-logo--animate').exists()).toBe(true)
      expect(wrapper.find('.windflow-logo__text').exists()).toBe(true)
      expect(wrapper.find('.windflow-logo__svg').attributes('width')).toBe('80')
    })

    it('rend en mode sidebar (small, pas de texte, pas d\'animation)', () => {
      const wrapper = mount(WindFlowLogo, {
        props: {
          size: 'small',
          animate: false,
          showText: false,
        },
      })

      expect(wrapper.find('.windflow-logo--small').exists()).toBe(true)
      expect(wrapper.find('.windflow-logo--animate').exists()).toBe(false)
      expect(wrapper.find('.windflow-logo__text').exists()).toBe(false)
    })
  })
})
