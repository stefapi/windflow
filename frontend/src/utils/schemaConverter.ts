/**
 * Convertisseur de format simple vers JSON Schema pour JSONForms.
 *
 * Convertit le format de variables simple du backend en JSON Schema
 * pour être utilisé avec JSONForms.
 */

interface SimpleVariable {
  type: 'string' | 'number' | 'boolean' | 'password' | 'select'
  label: string
  description?: string
  default?: any
  required?: boolean
  min?: number
  max?: number
  min_length?: number
  max_length?: number
  options?: string[]
  placeholder?: string
  generate?: boolean
  pattern?: string
}

interface SimpleConfig {
  [key: string]: SimpleVariable
}

interface JsonSchema {
  type: string
  properties: Record<string, any>
  required?: string[]
}

interface UiSchema {
  type: string
  elements: any[]
}

interface ConvertedSchema {
  schema: JsonSchema
  uischema: UiSchema
  metadata: {
    generateableFields: string[]
  }
}

/**
 * Convertit le format simple backend en JSON Schema pour JSONForms.
 *
 * @param simpleConfig - Configuration simple depuis le backend
 * @returns Schema JSON, UI Schema et métadonnées
 *
 * @example
 * ```typescript
 * const simpleConfig = {
 *   db_password: {
 *     type: 'password',
 *     label: 'Mot de passe',
 *     min_length: 12,
 *     generate: true,
 *     required: true
 *   }
 * }
 *
 * const { schema, uischema } = convertToJsonSchema(simpleConfig)
 * // Utiliser avec JSONForms
 * ```
 */
export function convertToJsonSchema(simpleConfig: SimpleConfig): ConvertedSchema {
  const properties: Record<string, any> = {}
  const required: string[] = []
  const uiElements: any[] = []
  const generateableFields: string[] = []

  Object.entries(simpleConfig).forEach(([key, variable]) => {
    // Construire la propriété JSON Schema
    const property: any = {
      title: variable.label
    }

    if (variable.description) {
      property.description = variable.description
    }

    // Mapper le type simple vers JSON Schema
    switch (variable.type) {
      case 'string':
      case 'password':
        property.type = 'string'
        if (variable.type === 'password') {
          property.format = 'password'
        }
        if (variable.min_length) {
          property.minLength = variable.min_length
        }
        if (variable.max_length) {
          property.maxLength = variable.max_length
        }
        if (variable.pattern) {
          property.pattern = variable.pattern
        }
        if (variable.default !== undefined) {
          property.default = variable.default
        }
        break

      case 'number':
        property.type = 'integer'
        if (variable.min !== undefined) {
          property.minimum = variable.min
        }
        if (variable.max !== undefined) {
          property.maximum = variable.max
        }
        if (variable.default !== undefined) {
          property.default = variable.default
        }
        break

      case 'boolean':
        property.type = 'boolean'
        property.default = variable.default ?? false
        break

      case 'select':
        property.type = 'string'
        if (variable.options) {
          property.enum = variable.options
        }
        if (variable.default) {
          property.default = variable.default
        }
        break
    }

    properties[key] = property

    // Ajouter aux champs requis
    if (variable.required) {
      required.push(key)
    }

    // Construire l'UI Schema element
    const control: any = {
      type: 'Control',
      scope: `#/properties/${key}`
    }

    // Options UI spécifiques
    const options: any = {}

    if (variable.placeholder) {
      options.placeholder = variable.placeholder
    }

    if (variable.type === 'password') {
      options.format = 'password'
      options.showUnfocusedDescription = true
    }

    if (variable.type === 'number' && variable.min !== undefined && variable.max !== undefined) {
      options.slider = true
    }

    if (variable.generate) {
      options.showGenerateButton = true
      generateableFields.push(key)
    }

    if (Object.keys(options).length > 0) {
      control.options = options
    }

    uiElements.push(control)
  })

  return {
    schema: {
      type: 'object',
      properties,
      ...(required.length > 0 && { required })
    },
    uischema: {
      type: 'VerticalLayout',
      elements: uiElements
    },
    metadata: {
      generateableFields
    }
  }
}

/**
 * Extrait les valeurs par défaut d'un schema JSON.
 *
 * @param schema - Schema JSON
 * @returns Objet avec les valeurs par défaut
 */
export function extractDefaults(schema: JsonSchema): Record<string, any> {
  const defaults: Record<string, any> = {}

  Object.entries(schema.properties).forEach(([key, prop]) => {
    if (prop.default !== undefined) {
      defaults[key] = prop.default
    }
  })

  return defaults
}

/**
 * Valide les données contre un schema JSON.
 *
 * @param data - Données à valider
 * @param schema - Schema JSON
 * @returns True si valide, sinon liste des erreurs
 */
export function validateAgainstSchema(
  data: Record<string, any>,
  schema: JsonSchema
): { valid: boolean; errors: string[] } {
  const errors: string[] = []

  // Vérifier les champs requis
  if (schema.required) {
    schema.required.forEach(field => {
      if (data[field] === undefined || data[field] === null || data[field] === '') {
        errors.push(`Le champ '${field}' est requis`)
      }
    })
  }

  // Valider les propriétés
  Object.entries(data).forEach(([key, value]) => {
    const propSchema = schema.properties[key]
    if (!propSchema) return

    // Validation selon le type
    switch (propSchema.type) {
      case 'string':
        if (typeof value !== 'string') {
          errors.push(`Le champ '${key}' doit être une chaîne de caractères`)
        } else {
          if (propSchema.minLength && value.length < propSchema.minLength) {
            errors.push(`Le champ '${key}' doit contenir au moins ${propSchema.minLength} caractères`)
          }
          if (propSchema.maxLength && value.length > propSchema.maxLength) {
            errors.push(`Le champ '${key}' ne doit pas dépasser ${propSchema.maxLength} caractères`)
          }
          if (propSchema.pattern && !new RegExp(propSchema.pattern).test(value)) {
            errors.push(`Le champ '${key}' ne respecte pas le format attendu`)
          }
        }
        break

      case 'integer':
      case 'number':
        if (typeof value !== 'number') {
          errors.push(`Le champ '${key}' doit être un nombre`)
        } else {
          if (propSchema.minimum !== undefined && value < propSchema.minimum) {
            errors.push(`Le champ '${key}' doit être >= ${propSchema.minimum}`)
          }
          if (propSchema.maximum !== undefined && value > propSchema.maximum) {
            errors.push(`Le champ '${key}' doit être <= ${propSchema.maximum}`)
          }
        }
        break

      case 'boolean':
        if (typeof value !== 'boolean') {
          errors.push(`Le champ '${key}' doit être un booléen`)
        }
        break
    }
  })

  return {
    valid: errors.length === 0,
    errors
  }
}
