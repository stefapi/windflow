# EPIC-027 : Profil Utilisateur

**Statut :** TODO
**Priorité :** Moyenne

## Vision
Gestion du profil utilisateur permettant aux utilisateurs de modifier leurs informations personnelles, changer leur mot de passe, gérer l'authentification à deux facteurs et uploader un avatar.

## Liste des Stories liées
- [ ] STORY-001 : Voir et modifier les informations du profil (nom, email, nom d'affichage)
- [ ] STORY-002 : Changer le mot de passe
- [ ] STORY-003 : Configurer l'authentification à deux facteurs (MFA/TOTP)
- [ ] STORY-004 : Désactiver l'authentification à deux facteurs
- [ ] STORY-005 : Uploader et recadrer un avatar
- [ ] STORY-006 : Voir les sessions actives

## Notes de conception
- Page profile/+page.svelte avec onglets (informations, sécurité, sessions)
- Modal ChangePasswordModal.svelte pour le changement de mot de passe
- Modal MfaSetupModal.svelte pour la configuration MFA
- Modal DisableMfaModal.svelte pour la désactivation MFA
- Modal AvatarCropper.svelte pour le recadrage d'avatar
- Validation de la force du mot de passe (PasswordStrengthIndicator)
- QR code pour la configuration TOTP
- Codes de secours affichés une seule fois
- Support des formats d'image pour l'avatar (JPEG, PNG, WebP)
