---
name: create-refactoring
description: Cadre un refactoring avec objectifs observables et non-régression ; crée un contrat distinct seulement si sa portée le justifie.
---

# create-refactoring

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Appliquer le [protocole commun](../../../docs/dev/protocole-execution.md) dans le périmètre de cette skill.

Lire `01` (contrats et identifiants), `02` (gouvernance) et le contrat en cours. Cette skill cadre le travail ; elle n'implémente pas le refactoring.

## Choisir la bonne portée

Un refactoring local nécessaire à une réalisation autorisée peut rester dans son contrat selon `01` §12 : noter le motif, le résultat structurel attendu et les contrôles de non-régression, sans story supplémentaire. Une demande explicite de contrat est respectée.

Pour un changement transversal, une nouvelle frontière ou une décision structurante, préparer des options fondées sur le code et une recommandation avant l'arbitrage requis. Un nom de pattern ne tient pas lieu de justification. Appliquer la règle d'architecture `20` §9 si une abstraction ou un moteur est envisagé.

Lorsque le travail mérite son propre contrat, choisir une epic directe bornée ou une story rattachée à une epic découpée selon `01` §2. Utiliser `create-epic` ou `create-stories` si nécessaire ; ne pas ajouter une story concurrente à une epic qui resterait directe. Ne pas rouvrir une epic terminée sans autorisation ; référencer un successeur si nécessaire.

## Écrire un contrat utile

Partir du gabarit approprié de `.backlog/_models/` ; réserver l'identifiant dans `.backlog/identifiants.md` en rapprochant registre, contrats conservés et historique, selon `01` §3. Ne jamais réutiliser ou supprimer un identifiant historique. Synchroniser parent et suivi (`make backlog`) dans le même changement.

Renseigner le problème observé et ses preuves, le résultat structurel recherché, inclus/exclus, dépendances, contraintes de comportement et AC observables. Préserver exigences sources et décisions applicables. Si le comportement doit changer, le nommer et le faire arbitrer comme changement de besoin plutôt que le cacher dans un refactoring.

Préférer des critères vérifiables : responsabilité explicite, chemin d'exécution unique, absence de dépendance interdite, tests de non-régression conservés. « Respecte SOLID » ou une couverture inchangée ne suffit pas à démontrer le résultat.

Explorer assez le code pour justifier la proposition, sans figer chaque fichier et signature. L'analyse proportionnée et les contrôles détaillés relèvent ensuite de `analyse-story`. Si la demande autorise un traitement complet, poursuivre le workflow autorisé ; sinon livrer le cadrage et les décisions restantes.
