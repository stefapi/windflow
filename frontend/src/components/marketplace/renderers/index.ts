/**
 * Renderers Element Plus personnalisés pour JSONForms.
 *
 * Ces renderers utilisent les composants Element Plus pour une meilleure
 * intégration visuelle avec le reste de l'interface WindFlow.
 */

import { rankWith, uiTypeIs } from '@jsonforms/core'
import StringControlRenderer, { stringControlRendererEntry } from './StringControlRenderer.vue'
import NumberControlRenderer from './NumberControlRenderer.vue'
import BooleanControlRenderer, { booleanControlRendererEntry } from './BooleanControlRenderer.vue'
import EnumControlRenderer, { enumControlRendererEntry } from './EnumControlRenderer.vue'
import PasswordControlRenderer, { passwordControlRendererEntry } from './PasswordControlRenderer.vue'
import TextAreaControlRenderer, { textAreaControlRendererEntry } from './TextAreaControlRenderer.vue'

// Tester personnalisé pour NumberControlRenderer qui matche à la fois number ET integer
const isNumberOrIntegerControl = (uischema: any, schema: any) => {
  const isControl = uiTypeIs('Control')(uischema, schema)
  const isNumberOrInteger = schema?.type === 'number' || schema?.type === 'integer'
  return isControl && isNumberOrInteger
}

// Entry pour NumberControlRenderer avec tester personnalisé
const numberControlRendererEntry = {
  renderer: NumberControlRenderer,
  tester: rankWith(3, isNumberOrIntegerControl)
}

/**
 * Tous les renderers disponibles.
 */
export const elementPlusRenderers = [
  stringControlRendererEntry,
  numberControlRendererEntry,
  booleanControlRendererEntry,
  enumControlRendererEntry,
  passwordControlRendererEntry,
  textAreaControlRendererEntry
]

/**
 * Export des composants individuels.
 */
export {
  StringControlRenderer,
  NumberControlRenderer,
  BooleanControlRenderer,
  EnumControlRenderer,
  PasswordControlRenderer,
  TextAreaControlRenderer
}

/**
 * Export des entries pour enregistrement manuel.
 */
export {
  stringControlRendererEntry,
  numberControlRendererEntry,
  booleanControlRendererEntry,
  enumControlRendererEntry,
  passwordControlRendererEntry,
  textAreaControlRendererEntry
}
