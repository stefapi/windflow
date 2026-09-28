"""
Client HTTP pour communiquer avec l'API WindFlow.

STORY-126.3 : l'API sert les enveloppes spec 09 — succès ``{"data": ...,
"message": ...}`` et erreurs ``{"error": {"code", "message"}}``. Le client
déplie centralement ``data`` (unwrap tolérant : un corps nu pré-126.2 passe
tel quel) et lit ``error.message`` avec fallback ``detail`` legacy.
"""

from typing import Any, Dict, Optional

import httpx

from cli.config import config_manager
from cli.session import session
from cli.utils import print_error


class APIClient:
    """Client HTTP pour l'API WindFlow avec gestion d'authentification."""

    def __init__(self):
        self.config = config_manager.load()
        self.session = session
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Obtient ou crée le client HTTP."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.api_url,
                timeout=self.config.api_timeout,
                headers=self._get_headers(),
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """Construit les en-têtes HTTP avec le token d'authentification."""
        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        token = self.session.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        """Gère la réponse HTTP, déplie l'enveloppe spec 09 et les erreurs."""
        try:
            response.raise_for_status()
            return self._unwrap_payload(response.json())
        except httpx.HTTPStatusError as e:
            message = self._extract_error_message(e)
            if e.response.status_code == 401:
                print_error(
                    "Non authentifié. Veuillez vous connecter avec "
                    "'windflow auth login'" + (f" ({message})" if message else "")
                )
            elif e.response.status_code == 403:
                print_error(
                    "Accès interdit. Vous n'avez pas les permissions nécessaires."
                    + (f" ({message})" if message else "")
                )
            elif e.response.status_code == 404:
                print_error(
                    "Ressource non trouvée" + (f" ({message})" if message else "")
                )
            else:
                print_error(
                    f"Erreur HTTP {e.response.status_code}: {message or str(e)}"
                )
            raise
        except httpx.RequestError as e:
            print_error(f"Erreur de connexion: {e}")
            raise

    @staticmethod
    def _unwrap_payload(payload: Any) -> Any:
        """Déplie l'enveloppe spec 09 ``{"data": ..., "message": ...}``.

        Détection stricte sur les clés d'enveloppe (``message`` pour
        ``APIResponse``, ``pagination`` pour ``PaginatedResponse``) : un
        payload métier contenant par hasard une clé ``data`` n'est jamais
        déplié par erreur. Un corps nu pré-126.2 passe tel quel.
        """
        if (
            isinstance(payload, dict)
            and "data" in payload
            and ("message" in payload or "pagination" in payload)
        ):
            return payload["data"]
        return payload

    @staticmethod
    def _extract_error_message(e: httpx.HTTPStatusError) -> Optional[str]:
        """Extrait ``error.message`` (spec 09), fallback ``detail`` legacy."""
        try:
            error_data = e.response.json()
        except Exception:
            return None
        if isinstance(error_data, dict):
            error_block = error_data.get("error")
            if isinstance(error_block, dict) and error_block.get("message"):
                return str(error_block["message"])
            if error_data.get("detail"):
                return str(error_data["detail"])
        return None

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Effectue une requête GET et retourne la charge utile (dépliée)."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.get(url, params=params)
        return self._handle_response(response)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """Effectue une requête POST et retourne la charge utile (dépliée)."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.post(url, json=data)
        return self._handle_response(response)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        """Effectue une requête PUT et retourne la charge utile (dépliée)."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.put(url, json=data)
        return self._handle_response(response)

    def delete(self, endpoint: str) -> Any:
        """Effectue une requête DELETE et retourne la charge utile (dépliée)."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.delete(url)
        return self._handle_response(response)

    def login(self, username: str, password: str) -> Any:
        """Authentifie l'utilisateur et stocke les tokens.

        Après unwrap spec 09, ``result`` est directement le dict de tokens
        (``access_token``, ``refresh_token``, ``expires_in``) — la clé
        ``"access_token"`` reste au même niveau qu'avant les enveloppes.
        """
        # L'endpoint de login n'utilise pas le préfixe API
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        result = self._handle_response(response)

        # Stocker les tokens
        if "access_token" in result:
            self.session.set_tokens(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                expires_in=result.get("expires_in"),
            )

            # Récupérer et stocker les infos utilisateur
            user_info = self.get("/auth/me")
            self.session.set_user_info(user_info)

        return result

    def logout(self) -> None:
        """Déconnecte l'utilisateur."""
        self.session.clear()

    def close(self) -> None:
        """Ferme le client HTTP."""
        if self._client:
            self._client.close()
            self._client = None


# Instance globale
api_client = APIClient()
