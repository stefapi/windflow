/**
 * Composable pour la génération dynamique de formulaires.
 *
 * Génère des champs de formulaire Element Plus depuis une définition de variables.
 */

import { reactive, computed, type ComputedRef } from 'vue'

export interface VariableDefinition {
  type: 'string' | 'password' | 'number' | 'boolean' | 'integer' | 'group'
  label: string
  description?: string
  default?: any
  required?: boolean
  visible?: boolean
  enum?: string[] | number[]
  enum_labels?: Record<string, string>
  min?: number
  max?: number
  pattern?: string
  has_macro?: boolean
  macro_template?: string
  variables?: Record<string, VariableDefinition>  // Sous-variables pour les groupes
}

export interface FormField {
  key: string
  type: string
  label: string
  description?: string
  required: boolean
  visible: boolean
  enum?: string[] | number[]
  enum_labels?: Record<string, string>
  min?: number
  max?: number
  pattern?: string
  default?: any
  validationRules: ValidationRule[]
  has_macro?: boolean
  macro_template?: string
  groupLabel?: string  // Label du groupe parent (pour l'affichage)
  isGroupHeader?: boolean  // Indique si c'est un header de groupe
}

export interface ValidationRule {
  required?: boolean
  message?: string
  trigger?: string | string[]
  min?: number
  max?: number
  pattern?: RegExp
  validator?: (rule: any, value: any, callback: any) => void
}

function coerceInteger(value: unknown): number {
  if (typeof value === 'number') return Math.trunc(value)
  if (typeof value === 'string') return parseInt(value, 10)
  return Math.trunc(Number(value))
}

function coerceNumber(value: unknown): number {
  if (typeof value === 'number') return value
  if (typeof value === 'string') return parseFloat(value)
  return Number(value)
}

/**
 * Génère les règles de validation Element Plus depuis une définition de variable.
 */
function getValidationRules(variable: VariableDefinition): ValidationRule[] {
  const rules: ValidationRule[] = []

  // Règle required
  if (variable.required) {
    rules.push({
      required: true,
      message: `${variable.label} est requis`,
      trigger: ['blur', 'change']
    })
  }

  // Validation de type number/integer
  if (variable.type === 'number' || variable.type === 'integer') {
    if (variable.type === 'integer') {
      rules.push({
        // Note: `rule` is unused but kept by Element Plus signature.
        validator: (_rule: any, value: any, callback: any) => {
          if (value === undefined || value === null || value === '') {
            callback()
            return
          }

          if (typeof value !== 'number' || !Number.isInteger(value)) {
            callback(new Error(`${variable.label} doit être un entier`))
            return
          }

          callback()
        },
        trigger: ['blur', 'change']
      })
    }

    if (variable.min !== undefined) {
      rules.push({
        validator: (_rule: any, value: any, callback: any) => {
          if (value !== undefined && value !== null && value < variable.min!) {
            callback(new Error(`${variable.label} doit être >= ${variable.min}`))
          } else {
            callback()
          }
        },
        trigger: 'blur'
      })
    }

    if (variable.max !== undefined) {
      rules.push({
        validator: (_rule: any, value: any, callback: any) => {
          if (value !== undefined && value !== null && value > variable.max!) {
            callback(new Error(`${variable.label} doit être <= ${variable.max}`))
          } else {
            callback()
          }
        },
        trigger: 'blur'
      })
    }
  }

  // Validation pattern pour les strings
  if (variable.type === 'string' && variable.pattern) {
    rules.push({
      validator: (_rule: any, value: any, callback: any) => {
        // Si valeur vide ou null
        if (!value || value === '') {
          // OK pour les champs non-requis, sinon géré par la règle required
          callback()
          return
        }

        // Tester le pattern uniquement si valeur présente
        try {
          const regex = new RegExp(variable.pattern!)
          if (!regex.test(value)) {
            callback(new Error(`${variable.label} ne correspond pas au format attendu`))
          } else {
            callback()
          }
        } catch (error) {
          console.error(`Pattern regex invalide pour ${variable.label}:`, variable.pattern, error)
          callback(new Error(`Configuration invalide du champ ${variable.label}`))
        }
      },
      trigger: 'blur'
    })
  }

  return rules
}

/**
 * Hook pour gérer un formulaire dynamique basé sur des définitions de variables.
 *
 * @param variables - Définitions des variables depuis l'API Stack
 * @returns Objet contenant les données du formulaire, les champs et les méthodes
 */
export function useDynamicForm(variables: Record<string, VariableDefinition>) {
  // Données du formulaire (réactif)
  const formData = reactive<Record<string, any>>({})

  /**
   * Initialise récursivement les valeurs par défaut pour un groupe et ses sous-groupes.
   *
   * @param variables - Variables à traiter
   * @param prefix - Préfixe pour la notation pointée (ex: "performance" ou "performance.advanced")
   */
  const initializeGroupDefaults = (variables: Record<string, VariableDefinition>, prefix: string = '') => {
    for (const [key, variable] of Object.entries(variables)) {
      const fullKey = prefix ? `${prefix}.${key}` : key

      // Gérer les groupes (récursif)
      if (variable.type === 'group' && variable.variables) {
        // Récursion pour les sous-variables du groupe
        initializeGroupDefaults(variable.variables, fullKey)
        continue
      }

      // Variables normales
      if (variable.default === undefined) {
        formData[fullKey] = null
        continue
      }

      if (variable.type === 'integer') {
        formData[fullKey] = coerceInteger(variable.default)
        continue
      }

      if (variable.type === 'number') {
        formData[fullKey] = coerceNumber(variable.default)
        continue
      }

      formData[fullKey] = variable.default
    }
  }

  /**
   * Initialise les valeurs par défaut du formulaire.
   * Gère les variables groupées en créant des clés avec notation pointée.
   * Supporte les groupes imbriqués à plusieurs niveaux.
   */
  const initializeDefaults = () => {
    // Réinitialiser le formulaire
    Object.keys(formData).forEach(key => {
      delete formData[key]
    })

    // Définir les valeurs par défaut (avec support récursif des groupes)
    initializeGroupDefaults(variables)
  }

  /**
   * Génère récursivement les champs pour un groupe et ses sous-groupes.
   *
   * @param variables - Variables à traiter
   * @param prefix - Préfixe pour la notation pointée (ex: "performance" ou "performance.advanced")
   * @param groupLabel - Label du groupe parent (pour l'affichage)
   * @returns Liste des champs générés
   */
  const generateGroupFields = (
    variables: Record<string, VariableDefinition>,
    prefix: string = '',
    groupLabel?: string
  ): FormField[] => {
    const result: FormField[] = []

    for (const [key, variable] of Object.entries(variables)) {
      if (variable.visible === false) continue

      const fullKey = prefix ? `${prefix}.${key}` : key

      // Gérer les groupes (récursif)
      if (variable.type === 'group' && variable.variables) {
        // Ajouter un header de groupe
        result.push({
          key: `__group_${fullKey}`,
          type: 'group',
          label: variable.label,
          description: variable.description,
          required: false,
          visible: true,
          validationRules: [],
          isGroupHeader: true
        })

        // Récursion pour les sous-champs du groupe
        result.push(...generateGroupFields(variable.variables, fullKey, variable.label))
      } else {
        // Variable normale
        result.push({
          key: fullKey,
          type: variable.type,
          label: variable.label,
          description: variable.description,
          required: variable.required || false,
          visible: variable.visible !== false,
          enum: variable.enum,
          enum_labels: variable.enum_labels,
          min: variable.min,
          max: variable.max,
          pattern: variable.pattern,
          default: variable.default,
          validationRules: getValidationRules(variable),
          has_macro: variable.has_macro || false,
          macro_template: variable.macro_template,
          groupLabel
        })
      }
    }

    return result
  }

  /**
   * Génère la configuration des champs pour le rendu.
   * Filtre les champs invisibles (visible: false).
   * Aplatit les groupes en créant des champs avec notation pointée.
   * Supporte les groupes imbriqués à plusieurs niveaux.
   */
  const fields: ComputedRef<FormField[]> = computed(() => {
    return generateGroupFields(variables)
  })

  /**
   * Récupère les règles de validation pour un champ.
   */
  const getFieldRules = (fieldKey: string): ValidationRule[] => {
    const variable = variables[fieldKey]
    return variable ? getValidationRules(variable) : []
  }

  /**
   * Valide que toutes les valeurs requises sont présentes.
   */
  const validateRequired = (): { valid: boolean; errors: string[] } => {
    const errors: string[] = []

    for (const [key, variable] of Object.entries(variables)) {
      if (variable.required) {
        const value = formData[key]
        if (value === null || value === undefined || value === '') {
          errors.push(`${variable.label} est requis`)
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors
    }
  }

  /**
   * Récupère uniquement les valeurs modifiées par rapport aux defaults.
   */
  const getChanges = (): Record<string, any> => {
    const changes: Record<string, any> = {}

    for (const [key, variable] of Object.entries(variables)) {
      const currentValue = formData[key]
      const defaultValue = variable.default

      // Inclure si la valeur a changé ou si elle est requise
      if (currentValue !== defaultValue || variable.required) {
        changes[key] = currentValue
      }
    }

    return changes
  }

  /**
   * Récupère toutes les valeurs du formulaire.
   */
  const getAllValues = (): Record<string, any> => {
    return { ...formData }
  }

  // Initialiser automatiquement les valeurs par défaut
  initializeDefaults()

  return {
    formData,
    fields,
    initializeDefaults,
    getFieldRules,
    validateRequired,
    getChanges,
    getAllValues
  }
}
