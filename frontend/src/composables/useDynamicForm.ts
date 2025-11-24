/**
 * Composable pour la génération dynamique de formulaires.
 *
 * Génère des champs de formulaire Element Plus depuis une définition de variables.
 */

import { reactive, computed, type ComputedRef } from 'vue'

export interface VariableDefinition {
  type: 'string' | 'password' | 'number' | 'boolean' | 'integer'
  label: string
  description?: string
  default?: any
  required?: boolean
  enum?: string[] | number[]
  min?: number
  max?: number
  pattern?: string
}

export interface FormField {
  key: string
  type: string
  label: string
  description?: string
  required: boolean
  enum?: string[] | number[]
  min?: number
  max?: number
  pattern?: string
  default?: any
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
    if (variable.min !== undefined) {
      rules.push({
        validator: (rule: any, value: any, callback: any) => {
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
        validator: (rule: any, value: any, callback: any) => {
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
      validator: (rule: any, value: any, callback: any) => {
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
   * Initialise les valeurs par défaut du formulaire.
   */
  const initializeDefaults = () => {
    // Réinitialiser le formulaire
    Object.keys(formData).forEach(key => {
      delete formData[key]
    })

    // Définir les valeurs par défaut
    for (const [key, variable] of Object.entries(variables)) {
      formData[key] = variable.default !== undefined ? variable.default : null
    }
  }

  /**
   * Génère la configuration des champs pour le rendu.
   */
  const fields: ComputedRef<FormField[]> = computed(() => {
    return Object.entries(variables).map(([key, variable]) => ({
      key,
      type: variable.type,
      label: variable.label,
      description: variable.description,
      required: variable.required || false,
      enum: variable.enum,
      min: variable.min,
      max: variable.max,
      pattern: variable.pattern,
      default: variable.default,
      validationRules: getValidationRules(variable)
    }))
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
