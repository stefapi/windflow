# EPIC-020 : Système de Thèmes

**Statut :** TODO
**Priorité :** Basse

## Vision
Support de thèmes clair/sombre et personnalisation. Les utilisateurs peuvent basculer entre les thèmes, choisir parmi plusieurs thèmes prédéfinis et leurs préférences sont persistées.

## Liste des Stories liées
- [ ] STORY-001 : Basculer entre thème clair et sombre
- [ ] STORY-002 : Le thème est persisté dans les préférences utilisateur
- [ ] STORY-003 : Choisir parmi plusieurs thèmes prédéfinis
- [ ] STORY-004 : Le thème s'applique à toute l'interface

## Notes de conception
- Utilisation de mode-watcher pour la détection du thème système
- Thèmes définis dans src/lib/themes.ts
- Persistance dans les préférences utilisateur (table user_preferences)
- Application via classes CSS sur l'élément html
- Support des thèmes personnalisés via CSS variables
- Transition fluide entre les thèmes
- Icône de bascule dans la barre latérale
