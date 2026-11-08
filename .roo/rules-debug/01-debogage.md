# Mode Debug — correction d'anomalies

- Partir d'un bug `BUG-XXX` (statut `NEW` ou `CONFIRMED`) ; s'il n'existe pas, le créer depuis `.backlog/_models/bug.md` et l'inscrire au registre (`01` §3).
- Étapes :
  1. reproduire (passer `NEW → CONFIRMED`) ;
  2. écrire un test qui échoue au niveau où le défaut est observable, y compris en intégration pour une concurrence, transaction ou interaction réelle ;
  3. identifier la cause racine ;
  4. corriger la cause à portée maîtrisée, avec refactoring local si nécessaire (`01` §12) ;
  5. vérifier que le nouveau test passe et que rien d'autre ne régresse (`make check` avant acceptation) ;
  6. renseigner « Cause racine réelle », « Réparation cible » et les tests de non-régression dans la section « Résolution » de `.backlog/bugs/BUG-XXX-slug.md`.
- Pas de correctif sans test qui reproduit le bug. Pas de contournement (exception avalée, contrôle désactivé) à la place d'une correction.
- Si une famille de défauts revient, qu'une correction déplace le problème, que les hypothèses échouent ou que les exceptions se dispersent : suspendre les correctifs concernés, réexaminer responsabilités, flux, transactions et ressources selon le [protocole commun](../../docs/dev/protocole-execution.md). Garder les contraintes approuvées ; comparer les options avant un nouveau patch. Demander l'arbitrage sur une proposition concrète si elle est structurante ou sensible, poursuivre les travaux indépendants autorisés.
- Bug touchant la sécurité (auth, RBAC, secrets) : revue humaine obligatoire (`02` §7) et checklist de `40` §8.
- Si des données réelles semblent nécessaires : ne pas les demander ; construire un cas fictif équivalent, ou demander au propriétaire un cas anonymisé.
- Réponse au gabarit d'exécution (`60` §3).
