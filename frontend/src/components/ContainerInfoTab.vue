<template>
  <div class="info-sections">
    <!-- Informations générales (bleu) -->
    <el-card
      class="info-card card-info-general"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-blue">
          <el-icon><InfoFilled /></el-icon>
          <span>Informations générales</span>
        </div>
      </template>
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item label="ID">
          <template #default>
            <div class="id-with-copy">
              <code>{{ truncateId(detail?.id) }}</code>
              <el-button
                link
                size="small"
                @click="copyId"
              >
                <el-icon><CopyDocument /></el-icon>
              </el-button>
            </div>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Image">
          <template #default>
            <code>{{ detail?.image || '-' }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Créé le">
          <template #default>
            {{ formatDate(detail?.created) }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Commande">
          <template #default>
            <code class="command-text">{{ detail?.path }} {{ detail?.args?.join(' ') }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Stack parente">
          <template #default>
            <el-tag
              v-if="parentStack"
              size="small"
            >
              {{ parentStack }}
            </el-tag>
            <span
              v-else
              class="text-muted"
            >-</span>
          </template>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- État du container (orange) -->
    <el-card
      class="info-card card-info-state"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-orange">
          <el-icon><Warning /></el-icon>
          <span>État du container</span>
          <el-tag
            :type="stateTagType"
            size="small"
            effect="dark"
            class="ml-2"
          >
            {{ state?.status ?? '-' }}
          </el-tag>
        </div>
      </template>
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item label="En cours d'exécution">
          <template #default>
            <el-tag
              :type="state?.running ? 'success' : 'info'"
              size="small"
            >
              {{ state?.running ? 'Oui' : 'Non' }}
            </el-tag>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Démarré le">
          <template #default>
            {{ formatDockerDate(state?.started_at) }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Arrêté le">
          <template #default>
            {{ formatDockerDate(state?.finished_at) }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="state?.exit_code != null"
          label="Code de sortie"
        >
          <template #default>
            <code :class="{ 'text-red-500': state.exit_code !== 0 }">{{ state.exit_code }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="state?.error"
          label="Erreur"
        >
          <template #default>
            <span class="text-red-500">{{ state.error }}</span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="state?.oom_killed"
          label="OOM Killed"
        >
          <template #default>
            <el-tag
              type="danger"
              size="small"
            >
              OUI
            </el-tag>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="state?.paused"
          label="En pause"
        >
          <template #default>
            <el-tag
              type="warning"
              size="small"
            >
              Oui
            </el-tag>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="state?.restarting"
          label="Redémarrage"
        >
          <template #default>
            <el-tag
              type="warning"
              size="small"
            >
              En cours
            </el-tag>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="state?.dead"
          label="Mort"
        >
          <template #default>
            <el-tag
              type="danger"
              size="small"
            >
              OUI
            </el-tag>
          </template>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Health Check Info -->
      <div
        v-if="state?.health"
        class="mt-4"
      >
        <h4 class="m-0 mb-2 text-sm font-semibold text-[var(--color-text-primary)]">
          Health Check
        </h4>
        <el-descriptions
          :column="2"
          border
          size="small"
        >
          <el-descriptions-item label="Santé">
            <template #default>
              <el-tag
                :type="healthTagType"
                size="small"
              >
                {{ state.health.status ?? '-' }}
              </el-tag>
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="state.health.failing_streak != null"
            label="Échecs consécutifs"
          >
            <template #default>
              <span :class="{ 'text-red-500': (state.health.failing_streak ?? 0) > 0 }">
                {{ state.health.failing_streak }}
              </span>
            </template>
          </el-descriptions-item>
        </el-descriptions>

        <el-table
          v-if="state.health.log && state.health.log.length > 0"
          :data="state.health.log"
          stripe
          size="small"
          class="mt-2"
          max-height="200"
        >
          <el-table-column
            label="Début"
            width="180"
          >
            <template #default="{ row }">
              {{ formatDockerDate(row.start) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Fin"
            width="180"
          >
            <template #default="{ row }">
              {{ formatDockerDate(row.end) }}
            </template>
          </el-table-column>
          <el-table-column
            label="Exit Code"
            width="100"
          >
            <template #default="{ row }">
              <code :class="{ 'text-red-500': row.exit_code !== 0 }">{{ row.exit_code }}</code>
            </template>
          </el-table-column>
          <el-table-column
            label="Sortie"
            min-width="200"
          >
            <template #default="{ row }">
              <code class="text-xs">{{ row.output || '-' }}</code>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- Configuration du container (violet) -->
    <el-card
      class="info-card card-info-config"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-purple">
          <el-icon><Setting /></el-icon>
          <span>Configuration du container</span>
        </div>
      </template>
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item label="Hostname">
          <template #default>
            <code>{{ config?.hostname ?? '-' }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Utilisateur">
          <template #default>
            {{ config?.user || '-' }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Répertoire de travail">
          <template #default>
            <code>{{ config?.working_dir || '-' }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="TTY">
          <template #default>
            {{ config?.tty ? 'Oui' : 'Non' }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Stdin ouvert">
          <template #default>
            {{ config?.open_stdin ? 'Oui' : 'Non' }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="config?.entrypoint && config.entrypoint.length > 0"
          label="Entrypoint"
          :span="2"
        >
          <template #default>
            <code class="command-text">{{ config.entrypoint.join(' ') }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="config?.cmd && config.cmd.length > 0"
          label="Commande (Cmd)"
          :span="2"
        >
          <template #default>
            <code class="command-text">{{ config.cmd.join(' ') }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Signal d'arrêt">
          <template #default>
            {{ config?.stop_signal || '-' }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="config?.stop_timeout != null"
          label="Délai d'arrêt (s)"
        >
          <template #default>
            {{ config.stop_timeout }}
          </template>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- Labels (gris) -->
    <el-card
      v-if="config?.labels && Object.keys(config.labels!).length > 0"
      class="info-card card-info-labels"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-grey">
          <div class="card-header-left">
            <el-icon><PriceTag /></el-icon>
            <span>Labels</span>
            <el-tag
              size="small"
              type="info"
              class="ml-2"
            >
              {{ Object.keys(config.labels!).length }}
            </el-tag>
          </div>
          <el-input
            v-model="labelSearch"
            placeholder="Rechercher..."
            size="small"
            clearable
            class="header-search"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>
      <el-table
        :data="filteredLabels"
        empty-text="Aucun label"
        stripe
        size="small"
        max-height="300"
      >
        <el-table-column
          prop="key"
          label="Clé"
          min-width="250"
        >
          <template #default="{ row }">
            <code class="text-xs">{{ row.key }}</code>
          </template>
        </el-table-column>
        <el-table-column
          prop="value"
          label="Valeur"
          min-width="300"
        >
          <template #default="{ row }">
            <code class="text-xs">{{ row.value || '-' }}</code>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Configuration hôte & Ressources (rouge) -->
    <el-card
      class="info-card card-info-host"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-red">
          <el-icon><Cpu /></el-icon>
          <span>Configuration hôte & Ressources</span>
        </div>
      </template>
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item label="Restart Policy">
          <template #default>
            <el-tag
              size="small"
              :type="restartPolicyTagType"
            >
              {{ hostConfig?.restart_policy?.name || 'no' }}
            </el-tag>
            <span
              v-if="hostConfig?.restart_policy?.maximum_retry_count"
              class="ml-2 text-xs text-[var(--color-text-secondary)]"
            >
              (max {{ hostConfig.restart_policy.maximum_retry_count }})
            </span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Mode réseau">
          <template #default>
            <code>{{ hostConfig?.network_mode || '-' }}</code>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Mode privilégié">
          <template #default>
            <el-tag
              v-if="hostConfig?.privileged"
              type="danger"
              size="small"
            >
              Oui
            </el-tag>
            <span v-else>Non</span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Read-only rootfs">
          <template #default>
            <el-tag
              v-if="hostConfig?.readonly_rootfs"
              type="warning"
              size="small"
            >
              Oui
            </el-tag>
            <span v-else>Non</span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Auto-remove">
          <template #default>
            {{ hostConfig?.auto_remove ? 'Oui' : 'Non' }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Log Driver">
          <template #default>
            {{ hostConfig?.log_config?.type || '-' }}
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="logConfigOptions.length > 0"
          label="Log Options"
          :span="2"
        >
          <template #default>
            <div class="flex flex-wrap gap-2">
              <el-tag
                v-for="opt in logConfigOptions"
                :key="opt.key"
                size="small"
                type="info"
              >
                {{ opt.key }}={{ opt.value }}
              </el-tag>
            </div>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Runtime">
          <template #default>
            {{ hostConfig?.runtime || '-' }}
          </template>
        </el-descriptions-item>
      </el-descriptions>

      <!-- Resource Limits -->
      <div
        v-if="hasResourceLimits"
        class="mt-4"
      >
        <h4 class="m-0 mb-2 text-sm font-semibold text-[var(--color-text-primary)]">
          Limites de ressources
        </h4>
        <el-descriptions
          :column="2"
          border
          size="small"
        >
          <el-descriptions-item
            v-if="resources?.memory != null"
            label="Mémoire (limite)"
          >
            <template #default>
              {{ formatBytes(resources.memory) }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.memory_reservation != null"
            label="Mémoire (réservation)"
          >
            <template #default>
              {{ formatBytes(resources.memory_reservation) }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.memory_swap != null"
            label="Swap"
          >
            <template #default>
              {{ resources.memory_swap === -1 ? 'Illimité' : formatBytes(resources.memory_swap) }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.cpu_shares != null && resources.cpu_shares > 0"
            label="CPU Shares"
          >
            <template #default>
              {{ resources.cpu_shares }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.cpu_period != null"
            label="CPU Period (µs)"
          >
            <template #default>
              {{ resources.cpu_period }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.cpu_quota != null"
            label="CPU Quota (µs)"
          >
            <template #default>
              {{ resources.cpu_quota }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.cpus != null"
            label="CPUs"
          >
            <template #default>
              {{ (resources.cpus / 1e9).toFixed(2) }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.cpuset_cpus"
            label="CPU Set"
          >
            <template #default>
              <code>{{ resources.cpuset_cpus }}</code>
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="resources?.pids_limit != null"
            label="PIDs Limit"
          >
            <template #default>
              {{ resources.pids_limit === 0 ? 'Illimité' : resources.pids_limit }}
            </template>
          </el-descriptions-item>
          <el-descriptions-item
            v-if="hostConfig?.shm_size != null"
            label="SHM Size"
          >
            <template #default>
              {{ formatBytes(hostConfig.shm_size) }}
            </template>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <!-- Sécurité & Capabilities (rouge) -->
    <el-card
      v-if="(hostConfig?.security_opt && hostConfig.security_opt.length > 0) || (hostConfig?.cap_add && hostConfig.cap_add.length > 0) || (hostConfig?.cap_drop && hostConfig.cap_drop.length > 0)"
      class="info-card card-info-security"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-red">
          <el-icon><Lock /></el-icon>
          <span>Sécurité & Capabilities</span>
        </div>
      </template>
      <div
        v-if="hostConfig?.security_opt && hostConfig.security_opt.length > 0"
        class="mb-3"
      >
        <h4 class="m-0 mb-2 text-sm font-semibold text-[var(--color-text-primary)]">
          Options de sécurité
        </h4>
        <div class="flex flex-wrap gap-1">
          <el-tag
            v-for="opt in hostConfig.security_opt"
            :key="opt"
            size="small"
            type="info"
            class="mr-1 mb-1"
          >
            <code class="text-xs">{{ opt }}</code>
          </el-tag>
        </div>
      </div>
      <div
        v-if="(hostConfig?.cap_add && hostConfig.cap_add.length > 0) || (hostConfig?.cap_drop && hostConfig.cap_drop.length > 0)"
      >
        <h4 class="m-0 mb-2 text-sm font-semibold text-[var(--color-text-primary)]">
          Capabilities
        </h4>
        <div class="flex gap-4 flex-wrap">
          <div v-if="hostConfig?.cap_add && hostConfig.cap_add.length > 0">
            <span class="text-xs text-[var(--color-text-secondary)] mr-1">Ajoutées :</span>
            <el-tag
              v-for="cap in hostConfig.cap_add"
              :key="'add-' + cap"
              type="warning"
              size="small"
              class="mr-1 mb-1"
            >
              {{ cap }}
            </el-tag>
          </div>
          <div v-if="hostConfig?.cap_drop && hostConfig.cap_drop.length > 0">
            <span class="text-xs text-[var(--color-text-secondary)] mr-1">Retirées :</span>
            <el-tag
              v-for="cap in hostConfig.cap_drop"
              :key="'drop-' + cap"
              type="info"
              size="small"
              class="mr-1 mb-1"
            >
              {{ cap }}
            </el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Occupation disque (gris) -->
    <el-card
      v-if="detail?.size_rw != null || detail?.size_root_fs != null"
      class="info-card card-info-disk"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-grey">
          <el-icon><Coin /></el-icon>
          <span>Occupation disque</span>
        </div>
      </template>
      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item
          v-if="detail?.size_rw != null"
          label="Taille modifiable (SizeRw)"
        >
          <template #default>
            {{ formatBytes(detail.size_rw) }}
            <span class="text-xs text-[var(--color-text-secondary)] ml-1">
              ({{ detail.size_rw.toLocaleString() }} bytes)
            </span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="detail?.size_root_fs != null"
          label="Taille totale (SizeRootFs)"
        >
          <template #default>
            {{ formatBytes(detail.size_root_fs) }}
            <span class="text-xs text-[var(--color-text-secondary)] ml-1">
              ({{ detail.size_root_fs.toLocaleString() }} bytes)
            </span>
          </template>
        </el-descriptions-item>
      </el-descriptions>
      <!-- Progress bar for visual -->
      <div
        v-if="detail?.size_rw != null && detail?.size_root_fs != null && detail.size_root_fs > 0"
        class="mt-3"
      >
        <div class="flex items-center gap-3">
          <el-progress
            :percentage="writablePercentage"
            :stroke-width="12"
            :format="() => `${writablePercentage.toFixed(1)}%`"
            style="flex: 1"
          />
          <span class="text-xs text-[var(--color-text-secondary)]">
            Espace modifiable / total
          </span>
        </div>
      </div>
    </el-card>

    <!-- Ports (violet) -->
    <el-card
      class="info-card card-info-ports"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-purple">
          <el-icon><Connection /></el-icon>
          <span>Ports</span>
          <el-tag
            v-if="parsedPorts.length > 0"
            size="small"
            type="info"
            class="ml-2"
          >
            {{ parsedPorts.length }}
          </el-tag>
        </div>
      </template>
      <el-table
        :data="parsedPorts"
        empty-text="Aucun port exposé"
        stripe
        size="small"
      >
        <el-table-column
          prop="hostIp"
          label="Host IP"
          width="140"
        />
        <el-table-column
          prop="hostPort"
          label="Host Port"
          width="120"
        />
        <el-table-column
          prop="containerPort"
          label="Container Port"
          width="140"
        />
        <el-table-column
          prop="protocol"
          label="Protocole"
          width="100"
        />
      </el-table>
    </el-card>

    <!-- Volumes (vert) -->
    <el-card
      class="info-card card-info-volumes"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-green">
          <el-icon><FolderOpened /></el-icon>
          <span>Volumes</span>
          <el-tag
            v-if="parsedMounts.length > 0"
            size="small"
            type="info"
            class="ml-2"
          >
            {{ parsedMounts.length }}
          </el-tag>
        </div>
      </template>
      <el-table
        :data="parsedMounts"
        empty-text="Aucun volume monté"
        stripe
        size="small"
      >
        <el-table-column
          prop="type"
          label="Type"
          width="100"
        >
          <template #default="{ row }">
            <el-tag size="small">
              {{ row.type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="source"
          label="Source"
          min-width="200"
        />
        <el-table-column
          prop="destination"
          label="Destination"
          min-width="200"
        />
        <el-table-column
          prop="mode"
          label="Mode"
          width="80"
        />
      </el-table>
    </el-card>

    <!-- Réseau (vert) -->
    <el-card
      class="info-card card-info-network"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-green">
          <el-icon><Share /></el-icon>
          <span>Réseau</span>
          <el-tag
            v-if="parsedNetworks.length > 0"
            size="small"
            type="info"
            class="ml-2"
          >
            {{ parsedNetworks.length }}
          </el-tag>
        </div>
      </template>
      <el-table
        :data="parsedNetworks"
        empty-text="Aucune information réseau"
        stripe
        size="small"
      >
        <el-table-column
          prop="networkName"
          label="Réseau"
          width="150"
        />
        <el-table-column
          prop="ipAddress"
          label="Adresse IP"
          width="150"
        />
        <el-table-column
          prop="macAddress"
          label="Adresse MAC"
          width="180"
        />
        <el-table-column
          prop="gateway"
          label="Passerelle"
          width="150"
        />
      </el-table>
    </el-card>

    <!-- Variables d'environnement (gris) -->
    <el-card
      class="info-card card-info-env"
      shadow="hover"
    >
      <template #header>
        <div class="card-header header-grey">
          <div class="card-header-left">
            <el-icon><Document /></el-icon>
            <span>Variables d'environnement</span>
            <el-tag
              v-if="parsedEnvVars.length > 0"
              size="small"
              type="info"
              class="ml-2"
            >
              {{ parsedEnvVars.length }}
            </el-tag>
          </div>
          <el-input
            v-model="envSearch"
            placeholder="Rechercher..."
            size="small"
            clearable
            class="header-search"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>
      <el-table
        :data="filteredEnvVars"
        empty-text="Aucune variable d'environnement"
        stripe
        size="small"
        max-height="400"
      >
        <el-table-column
          prop="key"
          label="Variable"
          min-width="200"
        >
          <template #default="{ row }">
            <code>{{ row.key }}</code>
            <el-tag
              v-if="row.isSecret"
              type="warning"
              size="small"
              class="secret-tag"
            >
              Secret
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="Valeur"
          min-width="300"
        >
          <template #default="{ row }">
            <div class="value-cell">
              <code v-if="!row.isSecret || isRevealed(row.key)">{{ row.value }}</code>
              <code
                v-else
                class="masked-value"
              >{{ maskValue(row.value) }}</code>
              <el-button
                v-if="row.isSecret"
                link
                size="small"
                @click="toggleSecret(row.key)"
              >
                <el-icon>
                  <View v-if="!isRevealed(row.key)" />
                  <Hide v-else />
                </el-icon>
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  CopyDocument,
  Search,
  View,
  Hide,
  InfoFilled,
  Warning,
  Setting,
  PriceTag,
  Lock,
  Coin,
  Connection,
  FolderOpened,
  Share,
  Document,
  Cpu,
} from '@element-plus/icons-vue'
import { isSecretKey, maskValue, useSecretMasker } from '@/composables/useSecretMasker'
import { formatBytes } from '@/utils/format'
import type {
  ContainerDetail,
  ContainerEnvVar,
  ContainerPortMapping,
  ContainerMount,
  ContainerNetworkInfo,
} from '@/types/api'

const props = defineProps<{
  detail: ContainerDetail | null
}>()

// Secret masker
const { toggleSecret, isRevealed } = useSecretMasker()

// Local state
const envSearch = ref('')
const labelSearch = ref('')

// Shortcuts
const state = computed(() => props.detail?.state ?? null)
const config = computed(() => props.detail?.config ?? null)
const hostConfig = computed(() => props.detail?.host_config ?? null)
const resources = computed(() => hostConfig.value?.resources ?? null)

// Computed
const parentStack = computed(() => {
  return props.detail?.config?.labels?.['com.docker.compose.project'] ?? null
})

const stateTagType = computed(() => {
  const s = state.value?.status
  if (s === 'running') return 'success'
  if (s === 'paused') return 'warning'
  if (s === 'exited' || s === 'dead') return 'danger'
  if (s === 'restarting') return 'warning'
  return 'info'
})

const healthTagType = computed(() => {
  const h = state.value?.health?.status
  if (h === 'healthy') return 'success'
  if (h === 'unhealthy') return 'danger'
  if (h === 'starting') return 'warning'
  return 'info'
})

const restartPolicyTagType = computed(() => {
  const policy = hostConfig.value?.restart_policy?.name
  if (policy === 'always' || policy === 'unless-stopped') return 'success'
  if (policy === 'on-failure') return 'warning'
  return 'info'
})

const hasResourceLimits = computed(() => {
  const r = resources.value
  if (!r) return false
  return (
    r.memory != null ||
    r.memory_reservation != null ||
    r.memory_swap != null ||
    (r.cpu_shares != null && r.cpu_shares > 0) ||
    r.cpu_period != null ||
    r.cpu_quota != null ||
    r.cpus != null ||
    r.cpuset_cpus != null ||
    r.pids_limit != null
  )
})

const writablePercentage = computed(() => {
  const rw = props.detail?.size_rw
  const total = props.detail?.size_root_fs
  if (rw == null || total == null || total === 0) return 0
  return Math.min((rw / total) * 100, 100)
})

const logConfigOptions = computed(() => {
  const opts = hostConfig.value?.log_config?.config
  if (!opts) return []
  return Object.entries(opts).map(([key, value]) => ({ key, value }))
})

const labelsList = computed(() => {
  const labels = config.value?.labels
  if (!labels) return []
  return Object.entries(labels).map(([key, value]) => ({ key, value }))
})

const filteredLabels = computed(() => {
  if (!labelSearch.value.trim()) {
    return labelsList.value
  }
  const search = labelSearch.value.toLowerCase()
  return labelsList.value.filter(
    (label: { key: string; value: string }) => label.key.toLowerCase().includes(search),
  )
})

// Parse ports from container details
const parsedPorts = computed<ContainerPortMapping[]>(() => {
  const portBindings = hostConfig.value?.port_bindings
  if (!portBindings) return []

  const ports: ContainerPortMapping[] = []
  for (const [containerPort, bindings] of Object.entries(portBindings)) {
    if (bindings && bindings.length > 0) {
      for (const binding of bindings) {
        const match = containerPort.match(/^(\d+)\/(tcp|udp)$/i)
        ports.push({
          hostIp: binding.HostIp || '0.0.0.0',
          hostPort: binding.HostPort,
          containerPort: match?.[1] ?? containerPort,
          protocol: match?.[2]?.toUpperCase() ?? 'TCP',
        })
      }
    }
  }
  return ports
})

// Parse mounts from container details
const parsedMounts = computed<ContainerMount[]>(() => {
  const mounts = props.detail?.mounts
  if (!mounts || !Array.isArray(mounts)) return []

  return mounts.map((mount: Record<string, unknown>) => ({
    type: String(mount['Type'] || mount['type'] || 'unknown'),
    source: String(mount['Source'] || mount['source'] || '-'),
    destination: String(mount['Destination'] || mount['destination'] || '-'),
    mode: String(mount['Mode'] || mount['mode'] || 'rw'),
    name: mount['Name'] !== undefined ? String(mount['Name']) : mount['name'] !== undefined ? String(mount['name']) : undefined,
  }))
})

// Parse networks from container details
const parsedNetworks = computed<ContainerNetworkInfo[]>(() => {
  const networks = props.detail?.network_settings?.networks
  if (!networks) return []

  return Object.entries(networks).map(([networkName, endpoint]) => ({
    networkId: endpoint.network_id ?? '-',
    networkName,
    ipAddress: endpoint.ip_address ?? '-',
    macAddress: endpoint.mac_address ?? '-',
    gateway: endpoint.gateway ?? '-',
  }))
})

// Parse environment variables
const parsedEnvVars = computed<ContainerEnvVar[]>(() => {
  const envArray = config.value?.env
  if (!envArray || !Array.isArray(envArray)) return []

  return envArray.map(env => {
    const equalIndex = env.indexOf('=')
    if (equalIndex === -1) {
      return { key: env, value: '', isSecret: false }
    }
    const key = env.substring(0, equalIndex)
    const value = env.substring(equalIndex + 1)
    return {
      key,
      value,
      isSecret: isSecretKey(key),
    }
  })
})

// Filtered environment variables
const filteredEnvVars = computed(() => {
  if (!envSearch.value.trim()) {
    return parsedEnvVars.value
  }
  const search = envSearch.value.toLowerCase()
  return parsedEnvVars.value.filter(
    env => env.key.toLowerCase().includes(search),
  )
})

// Methods
function truncateId(id: string | undefined): string {
  if (!id) return '-'
  return id.length > 12 ? id.substring(0, 12) : id
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('fr-FR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateStr
  }
}

function formatDockerDate(dateStr: string | null | undefined): string {
  if (!dateStr || dateStr === '0001-01-01T00:00:00Z') return '-'
  return formatDate(dateStr)
}


async function copyId(): Promise<void> {
  const id = props.detail?.id
  if (!id) return
  try {
    await window.navigator.clipboard.writeText(id)
    ElMessage.success('ID copié dans le presse-papier')
  } catch {
    ElMessage.error('Erreur lors de la copie')
  }
}
</script>

<style scoped>
.info-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ─── Card header pattern (same as ContainerOverviewTab) ─── */
.info-card :deep(.el-card__header) {
  padding: 12px 16px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 14px;
}

.card-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-search {
  width: 200px;
}

/* ─── Header color classes ─── */
.header-blue {
  color: var(--el-color-primary);
}

.header-green {
  color: var(--el-color-success);
}

.header-purple {
  color: #9b59b6;
}

.header-orange {
  color: var(--el-color-warning);
}

.header-red {
  color: var(--el-color-danger);
}

.header-grey {
  color: var(--el-color-info);
  justify-content: space-between;
}

/* ─── Card border-bottom colors ─── */
.card-info-general :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-primary);
}

.card-info-state :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-warning);
}

.card-info-config :deep(.el-card__header) {
  border-bottom: 3px solid #9b59b6;
}

.card-info-labels :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-info);
}

.card-info-host :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-danger);
}

.card-info-security :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-danger);
}

.card-info-disk :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-info);
}

.card-info-ports :deep(.el-card__header) {
  border-bottom: 3px solid #9b59b6;
}

.card-info-volumes :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-success);
}

.card-info-network :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-success);
}

.card-info-env :deep(.el-card__header) {
  border-bottom: 3px solid var(--el-color-info);
}

/* ─── Utility classes ─── */
.id-with-copy {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.command-text {
  font-family: monospace;
  font-size: 12px;
  word-break: break-all;
}

.text-muted {
  color: var(--color-text-secondary);
}

.value-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.masked-value {
  color: var(--color-text-secondary);
  letter-spacing: 2px;
}

.secret-tag {
  margin-left: 6px;
}

.text-red-500 {
  color: var(--el-color-danger);
  font-weight: 600;
}

.text-xs {
  font-size: 12px;
}

code {
  font-family: monospace;
  font-size: 12px;
}

.ml-2 {
  margin-left: 8px;
}

@media (width <= 768px) {
  .header-search {
    width: 100%;
  }

  .card-header {
    flex-wrap: wrap;
  }
}
</style>
