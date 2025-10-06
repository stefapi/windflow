/**
 * Types pour les renderers JSONForms personnalisés avec Element Plus.
 */

import type { ControlElement, UISchemaElement } from '@jsonforms/core'
import type { RendererProps } from '@jsonforms/vue'

/**
 * Props de base pour tous les renderers Element Plus.
 */
export interface ElementPlusRendererProps extends RendererProps {
  control: ControlElement
  uischema: UISchemaElement
  schema: any
  path: string
  enabled: boolean
  visible: boolean
  errors: string
  label?: string
  required?: boolean
  description?: string
}

/**
 * Options de configuration pour les renderers.
 */
export interface RendererOptions {
  placeholder?: string
  size?: 'large' | 'default' | 'small'
  clearable?: boolean
  disabled?: boolean
  readonly?: boolean
}

/**
 * Métadonnées de renderer.
 */
export interface RendererMetadata {
  name: string
  tester: (uischema: UISchemaElement, schema: any) => number
  renderer: any
}
