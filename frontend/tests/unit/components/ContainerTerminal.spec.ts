/**
 * ContainerTerminal.vue Unit Tests
 * STORY-504 : Refactoriser ContainerTerminal.vue → variables CSS thémées (palette VS Code)
 *
 * Tests focus sur l'intégration du thème CSS (variables CSS, absence de couleurs hardcodées)
 */

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

describe('ContainerTerminal.vue - Theme Integration', () => {
  describe('CSS Variables Usage', () => {
    it('should not contain hardcoded hex colors in <style> section', () => {
      // Lire le contenu du fichier source
      const componentPath = join(process.cwd(), 'src/components/ContainerTerminal.vue')
      const componentContent = readFileSync(componentPath, 'utf-8')

      // Extraire la section <style>
      const styleMatch = componentContent.match(/<style[^>]*>([\s\S]*?)<\/style>/)
      expect(styleMatch).not.toBeNull()

      const styleContent = styleMatch![1]

      // Vérifier qu'il n'y a pas de couleurs hex hardcodées (sauf dans les commentaires)
      // On ignore les lignes qui sont des commentaires
      const styleLines = styleContent.split('\n').filter(line => !line.trim().startsWith('/*') && !line.trim().startsWith('*'))
      const cleanStyleContent = styleLines.join('\n')

      // Pattern pour les couleurs hex (6 caractères)
      const hexColorPattern = /#[0-9a-fA-F]{6}\b/g
      const matches = cleanStyleContent.match(hexColorPattern)

      // Il ne devrait pas y avoir de couleurs hex hardcodées
      // Les couleurs doivent utiliser des variables CSS
      expect(matches).toBeNull()
    })

    it('should use var(--color-terminal-bg) for terminal background', () => {
      const componentPath = join(process.cwd(), 'src/components/ContainerTerminal.vue')
      const componentContent = readFileSync(componentPath, 'utf-8')

      const styleMatch = componentContent.match(/<style[^>]*>([\s\S]*?)<\/style>/)
      expect(styleMatch).not.toBeNull()

      const styleContent = styleMatch![1]

      // Vérifier que la variable CSS terminal-bg est utilisée
      expect(styleContent).toContain('var(--color-terminal-bg)')
    })

    it('should use var(--color-success), var(--color-warning), var(--color-info) for status dots', () => {
      const componentPath = join(process.cwd(), 'src/components/ContainerTerminal.vue')
      const componentContent = readFileSync(componentPath, 'utf-8')

      const styleMatch = componentContent.match(/<style[^>]*>([\s\S]*?)<\/style>/)
      expect(styleMatch).not.toBeNull()

      const styleContent = styleMatch![1]

      // Vérifier que les variables CSS de status sont utilisées
      expect(styleContent).toContain('var(--color-success)')
      expect(styleContent).toContain('var(--color-warning)')
      expect(styleContent).toContain('var(--color-info)')
    })

    it('should not have theme-dark or theme-light classes in CSS', () => {
      const componentPath = join(process.cwd(), 'src/components/ContainerTerminal.vue')
      const componentContent = readFileSync(componentPath, 'utf-8')

      const styleMatch = componentContent.match(/<style[^>]*>([\s\S]*?)<\/style>/)
      expect(styleMatch).not.toBeNull()

      const styleContent = styleMatch![1]

      // Vérifier qu'il n'y a plus de classes theme-dark/theme-light
      expect(styleContent).not.toContain('.theme-dark')
      expect(styleContent).not.toContain('.theme-light')
    })
  })

  describe('Template Simplification', () => {
    it('should not have conditional theme classes in template', () => {
      const componentPath = join(process.cwd(), 'src/components/ContainerTerminal.vue')
      const componentContent = readFileSync(componentPath, 'utf-8')

      // Extraire la section <template>
      const templateMatch = componentContent.match(/<template>([\s\S]*?)<\/template>/)
      expect(templateMatch).not.toBeNull()

      const templateContent = templateMatch![1]

      // Vérifier que terminal-container n'a pas de :class conditionnel pour le thème
      // Le pattern à éviter : :class="{ 'theme-dark': ... }"
      const conditionalThemePattern = /:class="\{[^}]*theme-(dark|light)[^}]*\}"/
      expect(templateContent).not.toMatch(conditionalThemePattern)
    })
  })
})
