# STORY-026 : Frontend — Onglet État & Configuration détaillés

**Statut :** TODO
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'administrateur, je veux voir toutes les informations détaillées du container dans un onglet structuré — état complet (exit code, OOM, health check), configuration (user, entrypoint, labels), limites ressources (restart policy, memory, CPU, privileged), et taille — afin de pouvoir diagnostiquer et comprendre le comportement du container.

## Contexte technique
L'onglet "Infos" actuel affiche une liste plate `el-descriptions` avec ID, Image, Created, Command, Stack parente, Ports, Volumes, Réseaux et Env vars. Il manque toutes les informations d'état détaillées (exit code, health), les limites de ressources, les labels, la config de logs, le mode privileged, etc.

Cette story dépend des schémas structurés de STORY-024 pour recevoir des données pré-formatées. En attendant, les données peuvent être lues depuis les dicts bruts existants.

## Critères d'acceptation (AC)
- [ ] AC 1 : Une section **État** affiche : Status, Running, Paused, Restarting, OOMKilled, Dead, ExitCode, Error, StartedAt, FinishedAt
- [ ] AC 2 : Si un **health check** est configuré, afficher : Health Status (avec badge coloré healthy/unhealthy/starting), FailingStreak, et les derniers résultats du log (Start, End, ExitCode, Output)
- [ ] AC 3 : Une section **Configuration** affiche : User, WorkingDir, Entrypoint (distinct de Cmd), TTY, StdinOpen, StopSignal, StopTimeout
- [ ] AC 4 : Une section **Labels** affiche tous les labels du container dans une table clé/valeur avec masquage/expansion si > 10 labels
- [ ] AC 5 : Une section **Restart Policy** affiche : Type (no, always, on-failure, unless-stopped), MaximumRetryCount
- [ ] AC 6 : Une section **Limites de ressources** affiche : Memory limit, MemorySwap, MemoryReservation, CPU Shares, CPU Period, CPU Quota, CPUs, CpusetCpus, PidsLimit
- [ ] AC 7 : Une section **Sécurité** affiche : Privileged (badge danger si true), ReadonlyRootfs, CapAdd, CapDrop, SecurityOpt
- [ ] AC 8 : Une section **Log Configuration** affiche : Driver, Options (max-size, max-file, etc.)
- [ ] AC 9 : Une section **Taille** affiche : SizeRw, SizeRootFs (en MB/GB lisibles)
- [ ] AC 10 : Les sections sont organisées dans des `el-collapse` panels pour ne pas surcharger la page (ouvertes par défaut : État, Limites ; fermées : Sécurité, Log Config)

## Dépendances
- STORY-024 (schémas Pydantic structurés) — pour recevoir les données structurées. Alternative : parser les dicts bruts existants en attendant.

## État d'avancement technique
- [ ] Remplacer l'onglet "Infos" par un onglet structuré avec sections
- [ ] Ajouter la section État (exit code, OOM, health check)
- [ ] Ajouter la section Configuration (user, entrypoint, TTY, labels)
- [ ] Ajouter la section Restart Policy
- [ ] Ajouter la section Limites de ressources
- [ ] Ajouter la section Sécurité
- [ ] Ajouter la section Log Configuration
- [ ] Ajouter la section Taille

## Tâches d'implémentation détaillées
<!-- Section remplie par la skill analyse-story -->

## Tests à écrire
<!-- Section remplie par la skill analyse-story -->
