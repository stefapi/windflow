<template>
  <div class="stack-reviews">
    <!-- Statistiques des avis -->
    <div class="reviews-summary mb-6 p-6 bg-gray-50 rounded-lg">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Note moyenne -->
        <div class="flex items-center gap-4">
          <div class="text-center">
            <div class="text-5xl font-bold text-primary">{{ averageRating.toFixed(1) }}</div>
            <el-rate
              :model-value="averageRating"
              disabled
              show-score
              :colors="['#99A9BF', '#F7BA2A', '#FF9900']"
            />
            <div class="text-sm text-gray-600 mt-2">
              {{ totalReviews }} avis
            </div>
          </div>
        </div>

        <!-- Distribution des notes -->
        <div class="rating-bars">
          <div
            v-for="star in [5, 4, 3, 2, 1]"
            :key="star"
            class="flex items-center gap-2 mb-2"
          >
            <span class="text-sm w-8">{{ star }}★</span>
            <el-progress
              :percentage="getRatingPercentage(star)"
              :color="star >= 4 ? '#67C23A' : star >= 3 ? '#E6A23C' : '#F56C6C'"
              :show-text="false"
              class="flex-1"
            />
            <span class="text-sm text-gray-600 w-12 text-right">
              {{ ratingDistribution[star] || 0 }}
            </span>
          </div>
        </div>
      </div>

      <!-- Bouton pour ajouter un avis -->
      <div class="mt-6 text-center">
        <el-button
          v-if="!userHasReviewed"
          type="primary"
          :icon="Edit"
          @click="showReviewForm = true"
        >
          Donner votre avis
        </el-button>
        <el-tag v-else type="success">Vous avez déjà donné votre avis</el-tag>
      </div>
    </div>

    <!-- Formulaire d'ajout/modification d'avis -->
    <el-dialog
      v-model="showReviewForm"
      title="Votre avis"
      width="600px"
    >
      <el-form
        ref="reviewFormRef"
        :model="reviewForm"
        :rules="reviewRules"
        label-width="100px"
      >
        <el-form-item label="Note" prop="rating">
          <el-rate
            v-model="reviewForm.rating"
            :colors="['#99A9BF', '#F7BA2A', '#FF9900']"
            show-text
          />
        </el-form-item>

        <el-form-item label="Titre" prop="title">
          <el-input
            v-model="reviewForm.title"
            placeholder="Résumez votre expérience"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="Commentaire" prop="comment">
          <el-input
            v-model="reviewForm.comment"
            type="textarea"
            :rows="5"
            placeholder="Partagez votre expérience avec ce stack..."
            maxlength="2000"
            show-word-limit
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showReviewForm = false">Annuler</el-button>
        <el-button type="primary" :loading="submitting" @click="submitReview">
          Publier
        </el-button>
      </template>
    </el-dialog>

    <!-- Liste des avis -->
    <div class="reviews-list">
      <h3 class="text-lg font-semibold mb-4">Avis des utilisateurs</h3>

      <div v-if="loading" class="text-center py-8">
        <el-icon class="is-loading text-4xl"><Loading /></el-icon>
      </div>

      <div v-else-if="reviews.length === 0" class="text-center py-8 text-gray-500">
        <p>Aucun avis pour le moment. Soyez le premier à donner votre avis !</p>
      </div>

      <div v-else class="space-y-4">
        <div
          v-for="review in reviews"
          :key="review.id"
          class="review-card p-4 border border-gray-200 rounded-lg"
        >
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-center gap-3">
              <el-avatar :size="40">
                {{ review.user_username?.[0]?.toUpperCase() || 'U' }}
              </el-avatar>
              <div>
                <div class="font-medium">{{ review.user_full_name || review.user_username }}</div>
                <div class="text-sm text-gray-500">
                  {{ formatDate(review.created_at) }}
                </div>
              </div>
            </div>

            <el-rate
              :model-value="review.rating"
              disabled
              :colors="['#99A9BF', '#F7BA2A', '#FF9900']"
            />
          </div>

          <h4 class="font-medium mb-2">{{ review.title }}</h4>
          <p class="text-gray-700 whitespace-pre-wrap">{{ review.comment }}</p>

          <!-- Actions (si l'utilisateur est l'auteur) -->
          <div v-if="canManageReview(review)" class="mt-3 flex gap-2">
            <el-button size="small" @click="editReview(review)">
              Modifier
            </el-button>
            <el-button size="small" type="danger" @click="deleteReview(review.id)">
              Supprimer
            </el-button>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalReviews > pageSize" class="mt-6 text-center">
        <el-button
          v-if="hasMore"
          @click="loadMore"
          :loading="loading"
        >
          Charger plus d'avis
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Edit, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import axios from 'axios'

interface Props {
  stackId: string
}

const props = defineProps<Props>()

// État
const reviews = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const showReviewForm = ref(false)
const currentPage = ref(0)
const pageSize = ref(10)
const totalReviews = ref(0)
const averageRating = ref(0)
const ratingDistribution = ref<Record<number, number>>({})
const userHasReviewed = ref(false)
const editingReviewId = ref<string | null>(null)

const reviewFormRef = ref<FormInstance>()
const reviewForm = ref({
  rating: 0,
  title: '',
  comment: ''
})

const reviewRules = {
  rating: [{ required: true, message: 'Veuillez donner une note', trigger: 'change' }],
  title: [
    { required: true, message: 'Veuillez entrer un titre', trigger: 'blur' },
    { min: 1, max: 200, message: 'Le titre doit faire entre 1 et 200 caractères', trigger: 'blur' }
  ],
  comment: [
    { required: true, message: 'Veuillez entrer un commentaire', trigger: 'blur' },
    { min: 10, message: 'Le commentaire doit faire au moins 10 caractères', trigger: 'blur' }
  ]
}

const hasMore = computed(() => {
  return reviews.value.length < totalReviews.value
})

function getRatingPercentage(star: number): number {
  if (totalReviews.value === 0) return 0
  return ((ratingDistribution.value[star] || 0) / totalReviews.value) * 100
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('fr-FR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  }).format(date)
}

function canManageReview(review: any): boolean {
  // TODO: Vérifier avec l'utilisateur connecté
  return false
}

async function loadReviews(reset = false) {
  if (reset) {
    currentPage.value = 0
    reviews.value = []
  }

  loading.value = true

  try {
    const response = await axios.get(
      `/api/v1/stacks/${props.stackId}/reviews`,
      {
        params: {
          skip: currentPage.value * pageSize.value,
          limit: pageSize.value
        }
      }
    )

    if (reset) {
      reviews.value = response.data.data
    } else {
      reviews.value.push(...response.data.data)
    }

    totalReviews.value = response.data.total
    averageRating.value = response.data.average_rating
    ratingDistribution.value = response.data.rating_distribution

  } catch (error) {
    ElMessage.error('Erreur lors du chargement des avis')
    console.error(error)
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  currentPage.value++
  await loadReviews(false)
}

async function submitReview() {
  if (!reviewFormRef.value) return

  await reviewFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true

    try {
      if (editingReviewId.value) {
        // Mise à jour
        await axios.put(
          `/api/v1/stacks/${props.stackId}/reviews/${editingReviewId.value}`,
          reviewForm.value
        )
        ElMessage.success('Avis mis à jour')
      } else {
        // Création
        await axios.post(
          `/api/v1/stacks/${props.stackId}/reviews`,
          reviewForm.value
        )
        ElMessage.success('Avis publié')
        userHasReviewed.value = true
      }

      showReviewForm.value = false
      resetForm()
      await loadReviews(true)

    } catch (error: any) {
      ElMessage.error(error.response?.data?.detail || 'Erreur lors de la publication')
    } finally {
      submitting.value = false
    }
  })
}

function editReview(review: any) {
  editingReviewId.value = review.id
  reviewForm.value = {
    rating: review.rating,
    title: review.title,
    comment: review.comment
  }
  showReviewForm.value = true
}

async function deleteReview(reviewId: string) {
  try {
    await ElMessageBox.confirm(
      'Êtes-vous sûr de vouloir supprimer cet avis ?',
      'Confirmation',
      {
        confirmButtonText: 'Supprimer',
        cancelButtonText: 'Annuler',
        type: 'warning'
      }
    )

    await axios.delete(`/api/v1/stacks/${props.stackId}/reviews/${reviewId}`)
    ElMessage.success('Avis supprimé')
    await loadReviews(true)

  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('Erreur lors de la suppression')
    }
  }
}

function resetForm() {
  editingReviewId.value = null
  reviewForm.value = {
    rating: 0,
    title: '',
    comment: ''
  }
  reviewFormRef.value?.resetFields()
}

onMounted(() => {
  loadReviews(true)
})
</script>

<style scoped>
.rating-bars :deep(.el-progress-bar__inner) {
  transition: width 0.6s ease;
}

.review-card {
  transition: box-shadow 0.3s ease;
}

.review-card:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
</style>
