# Protocole d'une unité exécutable

Le protocole partagé de WindFlow est [docs/dev/protocole-execution.md](../../../../docs/dev/protocole-execution.md). Le présent chemin historique est conservé pour les skills qui le référencent ; il ne définit aucune règle supplémentaire.

Lire le protocole pour analyser, réaliser ou vérifier une epic directe, une story, une sous-story ou un bug. Les règles du projet restent normatives ; appliquer la partie utile à l'action autorisée, sans transformer une demande d'analyse en autorisation de coder.

Une epic directe conserve son contrat, son analyse et ses preuves dans sa section « Exécution directe », sans story miroir. Une epic découpée coordonne ses stories ; une parente coordonne ses enfants sans reproduire leur périmètre. Les contrats, identifiants et preuves historiques sont conservés lors des reprises et découpages.

Pour les transitions et la clôture, utiliser `finalise-story` pour une story et `finalise-epic` puis `close-epic` pour une epic. Aucune validation sensible manquante ne peut être remplacée par ce routage.
