"""Tests des helpers purs du recreate sécurisé (STORY-174.2 — spec 02 § mise à jour)."""

from __future__ import annotations

from app.services.docker_client_service import (
    mask_secret_env,
    rebase_by_value,
    rebase_command,
    rebase_labels_by_value,
    resolve_masked_env,
)


class TestRebaseEnv:
    def test_rebase_env_identical_follows_new_image(self):
        """spec 02 l.249 : identique à l'ancienne image → suit la nouvelle."""
        current = ["TZ=UTC", "MODE=prod"]
        old = ["TZ=UTC", "MODE=dev"]
        new = ["TZ=Europe/Paris", "MODE=dev2"]
        assert rebase_by_value(current, old, new) == [
            "TZ=Europe/Paris",  # suit la nouvelle
            "MODE=prod",  # modifiée par l'utilisateur → conservée
        ]

    def test_rebase_env_modified_is_kept(self):
        current = ["TZ=Custom"]
        old = ["TZ=UTC"]
        new = ["TZ=New"]
        assert rebase_by_value(current, old, new) == ["TZ=Custom"]

    def test_rebase_env_user_added_is_kept(self):
        """spec 02 l.251 : absente de l'ancienne image (ajout) → conservée."""
        current = ["EXTRA=1"]
        old = []
        new = ["OTHER=2"]
        assert rebase_by_value(current, old, new) == ["EXTRA=1"]

    def test_rebase_env_absent_from_new_image_dropped(self):
        """« suit la nouvelle image » : absente de new (mais identique à old) → supprimée."""
        current = ["LEGACY=1"]
        old = ["LEGACY=1"]
        new = []
        assert rebase_by_value(current, old, new) == []


class TestRebaseLabels:
    def test_rebase_labels_matrix(self):
        current = {"keep.mod": "x", "follow": "old", "add": "1"}
        old = {"follow": "old", "keep.mod": "other"}
        new = {"follow": "new"}
        assert rebase_labels_by_value(current, old, new) == {
            "keep.mod": "x",  # modifiée → conservée
            "follow": "new",  # identique → suit new
            "add": "1",  # ajout → conservé
        }


class TestRebaseCmd:
    def test_rebase_cmd_baked_follows_image_user_cmd_survives(self):
        old_cmd = ["nginx", "-g", "daemon off;"]
        new_cmd = ["nginx", "-new"]
        # cuite (identique à old) → suit new
        assert rebase_command(old_cmd, old_cmd, new_cmd) == new_cmd
        # commande utilisateur (différente) → survit
        assert rebase_command(["my", "cmd"], old_cmd, new_cmd) == ["my", "cmd"]

    def test_rebase_cmd_none_takes_new(self):
        assert rebase_command(None, ["a"], ["b"]) == ["b"]
        assert rebase_command(None, ["a"], None) is None


class TestMaskSecrets:
    def test_mask_secret_env_masks_password_token_key_secret(self):
        values = [
            "PATH=/usr/bin",
            "POSTGRES_PASSWORD=s3cr3t",
            "API_TOKEN=abc",
            "SSH_KEY=zzz",
            "CLIENT_SECRET=qqq",
            "MY_KEYWORD=x",  # KEYWORD ne finit pas par KEY → non masqué
        ]
        masked = mask_secret_env(values)
        assert masked == [
            "PATH=/usr/bin",
            "POSTGRES_PASSWORD=***",
            "API_TOKEN=***",
            "SSH_KEY=***",
            "CLIENT_SECRET=***",
            "MY_KEYWORD=x",
        ]

    def test_mask_secret_env_case_insensitive(self):
        assert mask_secret_env(["db_password=x"]) == ["db_password=***"]

    def test_resolve_masked_env_replaces_placeholders_from_real(self):
        submitted = ["PATH=/bin", "POSTGRES_PASSWORD=***", "NEW=1"]
        real = ["PATH=/usr/bin", "POSTGRES_PASSWORD=s3cr3t"]
        assert resolve_masked_env(submitted, real) == [
            "PATH=/bin",  # édité par l'utilisateur → conservé
            "POSTGRES_PASSWORD=s3cr3t",  # résolu depuis le réel
            "NEW=1",
        ]

    def test_resolve_masked_env_unknown_key_kept(self):
        submitted = ["GHOST=***"]
        real = []
        assert resolve_masked_env(submitted, real) == ["GHOST=***"]
