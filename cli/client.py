"""
Client HTTP pour communiquer avec l'API WindFlow.
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
                headers=self._get_headers()
            )
        return self._client

    def _get_headers(self) -> Dict[str, str]:
        """Construit les en-têtes HTTP avec le token d'authentification."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        token = self.session.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Gère la réponse HTTP et les erreurs."""
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                print_error("Non authentifié. Veuillez vous connecter avec 'windflow auth login'")
            elif e.response.status_code == 403:
                print_error("Accès interdit. Vous n'avez pas les permissions nécessaires.")
            elif e.response.status_code == 404:
                print_error("Ressource non trouvée")
            else:
                try:
                    error_data = e.response.json()
                    message = error_data.get("detail", str(e))
                except Exception:
                    message = str(e)
                print_error(f"Erreur HTTP {e.response.status_code}: {message}")
            raise
        except httpx.RequestError as e:
            print_error(f"Erreur de connexion: {e}")
            raise

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Effectue une requête GET."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.get(url, params=params)
        return self._handle_response(response)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Effectue une requête POST."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.post(url, json=data)
        return self._handle_response(response)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Effectue une requête PUT."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.put(url, json=data)
        return self._handle_response(response)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Effectue une requête DELETE."""
        url = f"{self.config.api_prefix}{endpoint}"
        response = self.client.delete(url)
        return self._handle_response(response)

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authentifie l'utilisateur et stocke les tokens."""
        # L'endpoint de login n'utilise pas le préfixe API
        response = self.client.post(
            "/api/v1/auth/login",
            data={
                "username": username,
                "password": password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        result = self._handle_response(response)

        # Stocker les tokens
        if "access_token" in result:
            self.session.set_tokens(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                expires_in=result.get("expires_in")
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
