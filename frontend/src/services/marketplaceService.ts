/**
 * Service API pour la marketplace WindFlow.
 *
 * Gère tous les appels API vers les endpoints marketplace.
 */

import axios from 'axios'
import type {
  MarketplaceStack,
  StackDetails,
  StacksList,
  DeploymentConfig,
  DeploymentResponse
} from '@/types/marketplace'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/**
 * Service marketplace
 */
class MarketplaceService {
  /**
   * Liste les stacks de la marketplace.
   *
   * @param params - Paramètres de recherche et pagination
   * @returns Liste paginée de stacks
   */
  async listStacks(params?: {
    category?: string
    search?: string
    skip?: number
    limit?: number
  }): Promise<StacksList> {
    const response = await axios.get<StacksList>(
      `${API_BASE_URL}/api/v1/marketplace/stacks`,
      { params }
    )
    return response.data
  }

  /**
   * Récupère les détails complets d'un stack.
   *
   * @param stackId - ID du stack
   * @returns Détails du stack avec template et variables
   */
  async getStackDetails(stackId: string): Promise<StackDetails> {
    const response = await axios.get<StackDetails>(
      `${API_BASE_URL}/api/v1/marketplace/stacks/${stackId}`
    )
    return response.data
  }

  /**
   * Liste les catégories disponibles.
   *
   * @returns Liste des catégories
   */
  async getCategories(): Promise<string[]> {
    const response = await axios.get<string[]>(
      `${API_BASE_URL}/api/v1/marketplace/categories`
    )
    return response.data
  }

  /**
   * Récupère les stacks les plus populaires.
   *
   * @param limit - Nombre de stacks à retourner
   * @returns Liste des stacks populaires
   */
  async getPopularStacks(limit = 10): Promise<MarketplaceStack[]> {
    const response = await axios.get<MarketplaceStack[]>(
      `${API_BASE_URL}/api/v1/marketplace/stacks/popular`,
      { params: { limit } }
    )
    return response.data
  }

  /**
   * Récupère les stacks récemment ajoutés.
   *
   * @param limit - Nombre de stacks à retourner
   * @returns Liste des stacks récents
   */
  async getRecentStacks(limit = 10): Promise<MarketplaceStack[]> {
    const response = await axios.get<MarketplaceStack[]>(
      `${API_BASE_URL}/api/v1/marketplace/stacks/recent`,
      { params: { limit } }
    )
    return response.data
  }

  /**
   * Déploie un stack depuis la marketplace.
   *
   * @param stackId - ID du stack à déployer
   * @param config - Configuration du déploiement
   * @returns Réponse du déploiement
   */
  async deployStack(
    stackId: string,
    config: Omit<DeploymentConfig, 'stack_id'>
  ): Promise<DeploymentResponse> {
    const response = await axios.post<DeploymentResponse>(
      `${API_BASE_URL}/api/v1/marketplace/stacks/${stackId}/deploy`,
      {
        stack_id: stackId,
        ...config
      }
    )
    return response.data
  }

  /**
   * Copie un stack public dans l'organisation de l'utilisateur.
   *
   * @param stackId - ID du stack à installer
   * @returns Stack copié
   */
  async installStack(stackId: string): Promise<StackDetails> {
    const response = await axios.post<StackDetails>(
      `${API_BASE_URL}/api/v1/marketplace/stacks/${stackId}/install`
    )
    return response.data
  }
}

// Export singleton
export const marketplaceService = new MarketplaceService()
export default marketplaceService
