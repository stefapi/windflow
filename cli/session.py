"""
Gestion de la session et des tokens d'authentification pour le CLI WindFlow.
"""

from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
import json


class Session:
    """Gestion de la session utilisateur avec stockage persistant des tokens."""

    def __init__(self):
        self.session_dir = Path.home() / ".windflow"
        self.session_file = self.session_dir / "session.json"
        self._session_data: Optional[Dict[str, Any]] = None

    def ensure_session_dir(self) -> None:
        """Assure que le répertoire de session existe."""
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Charge la session depuis le fichier."""
        if self._session_data is not None:
            return self._session_data

        if not self.session_file.exists():
            self._session_data = {}
            return self._session_data

        try:
            with open(self.session_file, 'r', encoding='utf-8') as f:
                self._session_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            self._session_data = {}

        return self._session_data

    def save(self, session_data: Dict[str, Any]) -> None:
        """Sauvegarde la session dans le fichier."""
        self.ensure_session_dir()

        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        self._session_data = session_data

    def set_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ) -> None:
        """Enregistre les tokens d'authentification."""
        session = self.load()
        session["access_token"] = access_token

        if refresh_token:
            session["refresh_token"] = refresh_token

        if expires_in:
            expiry = datetime.now() + timedelta(seconds=expires_in)
            session["expires_at"] = expiry.isoformat()

        self.save(session)

    def get_access_token(self) -> Optional[str]:
        """Récupère le token d'accès."""
        session = self.load()
        return session.get("access_token")

    def get_refresh_token(self) -> Optional[str]:
        """Récupère le token de rafraîchissement."""
        session = self.load()
        return session.get("refresh_token")

    def is_authenticated(self) -> bool:
        """Vérifie si l'utilisateur est authentifié."""
        token = self.get_access_token()
        if not token:
            return False

        # Vérifier l'expiration si disponible
        session = self.load()
        expires_at = session.get("expires_at")
        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)
                if datetime.now() >= expiry:
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Récupère les informations utilisateur stockées."""
        session = self.load()
        return session.get("user")

    def set_user_info(self, user: Dict[str, Any]) -> None:
        """Enregistre les informations utilisateur."""
        session = self.load()
        session["user"] = user
        self.save(session)

    def clear(self) -> None:
        """Efface la session."""
        self._session_data = {}
        if self.session_file.exists():
            self.session_file.unlink()


# Instance globale
session = Session()
