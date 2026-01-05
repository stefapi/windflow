/**
 * Types pour la marketplace WindFlow.
 */

/**
 * Stack de la marketplace (liste)
 */
export interface MarketplaceStack {
  id: string
  name: string
  description: string | null
  version: string
  category: string | null
  tags: string[]
  icon_url: string | null
  screenshots: string[]
  author: string | null
  license: string | null
  downloads: number
  rating: number
  created_at: string
  updated_at: string
}

/**
 * Stack complet avec template et variables
 */
export interface StackDetails extends MarketplaceStack {
  template: Record<string, any>
  variables: Record<string, StackVariable>
  organization_id: string
  is_public: boolean
  documentation_url: string | null
}

/**
 * Variable de configuration d'un stack
 */
export interface StackVariable {
  type: 'string' | 'number' | 'integer' | 'boolean' | 'password' | 'select' | 'group'
  label: string
  description?: string
  default?: any
  required?: boolean
  visible?: boolean
  min?: number
  max?: number
  min_length?: number
  max_length?: number
  options?: string[]
  enum_labels?: Record<string, string>
  placeholder?: string
  generate?: boolean
  pattern?: string
  variables?: Record<string, StackVariable>  // Sous-variables pour les groupes
}

/**
 * Configuration de déploiement
 */
export interface DeploymentConfig {
  stack_id: string
  target_id: string
  configuration: Record<string, any>
  name?: string
}

/**
 * Réponse de déploiement
 */
export interface DeploymentResponse {
  deployment_id: string
  status: string
  message: string
}

/**
 * Liste paginée de stacks
 */
export interface StacksList {
  data: MarketplaceStack[]
  total: number
  skip: number
  limit: number
}

/**
 * Cible de déploiement
 */
export interface Target {
  id: string
  name: string
  type: 'docker' | 'kubernetes' | 'vm' | 'physical'
  host: string
  description?: string
  status?: string
}

/**
 * État du déploiement
 */
export interface DeploymentStatus {
  id: string
  name: string
  status: 'pending' | 'running' | 'success' | 'failed'
  stack_id: string
  stack_name?: string
  target_id: string
  started_at?: string
  completed_at?: string
  error?: string
  logs?: string[]
}
