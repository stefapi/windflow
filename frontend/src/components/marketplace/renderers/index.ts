/**
 * Renderers Element Plus personnalisés pour JSONForms.
 *
 * Ces renderers utilisent les composants Element Plus pour une meilleure
 * intégration visuelle avec le reste de l'interface WindFlow.
 */

import StringControlRenderer, { stringControlRendererEntry } from './StringControlRenderer.vue'
import NumberControlRenderer, { numberControlRendererEntry } from './NumberControlRenderer.vue'
import BooleanControlRenderer, { booleanControlRendererEntry } from './BooleanControlRenderer.vue'
import EnumControlRenderer, { enumControlRendererEntry } from './EnumControlRenderer.vue'
import PasswordControlRenderer, { passwordControlRendererEntry } from './PasswordControlRenderer.vue'
import TextAreaControlRenderer, { textAreaControlRendererEntry } from './TextAreaControlRenderer.vue'

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
