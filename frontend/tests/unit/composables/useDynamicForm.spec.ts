/**
 * useDynamicForm Unit Tests — STORY-171 (AC 3 : bornes canoniques minimum/maximum).
 *
 * Contrat `GET /stacks/{id}` (source de vérité) : les variables numériques
 exposent `minimum`/`maximum` uniquement — `min`/`max` ne sont plus lus.
 */
import { describe, it, expect } from 'vitest'
import { useDynamicForm, type VariableDefinition, type ValidationRule } from '@/composables/useDynamicForm'

/**
 * Exécute un validator de règle Element Plus et capture l'éventuelle erreur.
 */
function runValidator(rule: ValidationRule, value: unknown): Error | undefined {
  let captured: Error | undefined
  rule.validator?.({}, value, (error?: Error) => {
    captured = error
  })
  return captured
}

/**
 * Collecte les erreurs produites par l'ensemble des validators d'un champ.
 */
function collectErrors(rules: ValidationRule[], value: unknown): Error[] {
  return rules
    .filter((rule) => rule.validator !== undefined)
    .map((rule) => runValidator(rule, value))
    .filter((error): error is Error => error !== undefined)
}

describe('useDynamicForm — STORY-171 bornes canoniques minimum/maximum', () => {
  describe('champ integer borné', () => {
    const variables: Record<string, VariableDefinition> = {
      host_port: {
        type: 'integer',
        label: 'Port hôte',
        default: 5432,
        minimum: 1,
        maximum: 65535,
      },
    }

    it('le FormField porte les bornes canoniques minimum/maximum', () => {
      const { fields } = useDynamicForm(variables)
      const field = fields.value.find((f) => f.key === 'host_port')

      expect(field).toBeDefined()
      expect(field?.minimum).toBe(1)
      expect(field?.maximum).toBe(65535)
      // AC 3 : plus aucune propriété legacy min/max servie
      expect(field !== undefined && 'min' in field).toBe(false)
      expect(field !== undefined && 'max' in field).toBe(false)
    })

    it('une valeur sous la borne minimum déclenche une erreur de validation', () => {
      const { fields } = useDynamicForm(variables)
      const field = fields.value.find((f) => f.key === 'host_port')
      const rules = field?.validationRules ?? []

      const errors = collectErrors(rules, 0)
      expect(errors.some((e) => e.message.includes('>= 1'))).toBe(true)
    })

    it('une valeur au-dessus de la borne maximum déclenche une erreur de validation', () => {
      const { fields } = useDynamicForm(variables)
      const field = fields.value.find((f) => f.key === 'host_port')
      const rules = field?.validationRules ?? []

      const errors = collectErrors(rules, 70000)
      expect(errors.some((e) => e.message.includes('<= 65535'))).toBe(true)
    })

    it("une valeur dans l'intervalle passe toutes les règles", () => {
      const { fields } = useDynamicForm(variables)
      const field = fields.value.find((f) => f.key === 'host_port')
      const rules = field?.validationRules ?? []

      expect(collectErrors(rules, 5432)).toEqual([])
    })

    it('le défaut integer est coercé en nombre entier', () => {
      const { formData } = useDynamicForm({
        host_port: { type: 'integer', label: 'Port hôte', default: '5432', minimum: 1, maximum: 65535 },
      })
      expect(formData['host_port']).toBe(5432)
    })
  })

  describe('groupes récursifs', () => {
    const variables: Record<string, VariableDefinition> = {
      performance: {
        type: 'group',
        label: 'Performance',
        description: 'Réglages de performance',
        variables: {
          max_connections: {
            type: 'integer',
            label: 'Connexions max',
            default: 100,
            minimum: 1,
            maximum: 1000,
          },
        },
      },
    }

    it('les sous-variables utilisent la notation pointée avec bornes conservées', () => {
      const { fields } = useDynamicForm(variables)

      // Header de groupe
      const header = fields.value.find((f) => f.key === '__group_performance')
      expect(header?.isGroupHeader).toBe(true)
      expect(header?.label).toBe('Performance')

      // Sous-champ aplati en clé pointée
      const sub = fields.value.find((f) => f.key === 'performance.max_connections')
      expect(sub).toBeDefined()
      expect(sub?.minimum).toBe(1)
      expect(sub?.maximum).toBe(1000)
      expect(sub?.groupLabel).toBe('Performance')
    })

    it('les règles de bornes du sous-champ de groupe sont fonctionnelles', () => {
      const { fields } = useDynamicForm(variables)
      const sub = fields.value.find((f) => f.key === 'performance.max_connections')
      const rules = sub?.validationRules ?? []

      expect(collectErrors(rules, 0).some((e) => e.message.includes('>= 1'))).toBe(true)
      expect(collectErrors(rules, 5000).some((e) => e.message.includes('<= 1000'))).toBe(true)
      expect(collectErrors(rules, 500)).toEqual([])
    })

    it('le défaut du sous-champ est initialisé sous clé pointée', () => {
      const { formData } = useDynamicForm(variables)
      expect(formData['performance.max_connections']).toBe(100)
    })
  })

  describe('bornes legacy min/max ignorées (AC 3)', () => {
    it('des bornes min/max legacy ne génèrent aucune règle de validation', () => {
      // Simulation d'un payload legacy (pré-contrat STORY-171) : les clés
      // min/max ne font plus partie de VariableDefinition — elles doivent
      // être silencieusement ignorées, sans règle de borne.
      const legacyVariable = {
        type: 'integer' as const,
        label: 'Port hôte',
        default: 5432,
        min: 70000,
        max: 99999,
      }
      const { fields } = useDynamicForm({
        host_port: legacyVariable as unknown as VariableDefinition,
      })

      const field = fields.value.find((f) => f.key === 'host_port')
      expect(field).toBeDefined()
      expect(field?.minimum).toBeUndefined()
      expect(field?.maximum).toBeUndefined()

      // 0 serait refusé si `min: 70000` était encore lu — ici aucune erreur
      const rules = field?.validationRules ?? []
      expect(collectErrors(rules, 0)).toEqual([])
      expect(collectErrors(rules, 70000)).toEqual([])
    })
  })

  describe('visible', () => {
    it('une variable visible: false est exclue des champs générés', () => {
      const { fields } = useDynamicForm({
        secret_internal: { type: 'string', label: 'Interne', visible: false },
      })
      expect(fields.value.find((f) => f.key === 'secret_internal')).toBeUndefined()
    })
  })
})
