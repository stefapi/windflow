"""
Exceptions de base pour l'application WindFlow.

Toutes les exceptions métier doivent hériter de :class:`WindFlowException`.

Hiérarchie (STORY-127, spec 09 § Gestion des erreurs) :

- ``WindFlowException`` — base, 500 ``INTERNAL_ERROR`` par défaut ;
- ``APIError`` — racine des erreurs API typées ;
- ``NotFoundError`` — 404 ``NOT_FOUND`` (signature ``(resource, resource_id)``) ;
- ``ConflictError`` — 409 ``CONFLICT`` ;
- ``InvalidInputError`` — 400 ``INVALID_INPUT`` ;
- ``UnprocessableEntityError`` — 422 ``VALIDATION_ERROR`` ;
- ``PermissionDeniedError`` — 403 ``PERMISSION_DENIED`` ;
- ``AuthenticationError`` — 401 ``INVALID_OR_EXPIRED_TOKEN`` + ``WWW-Authenticate`` ;
- ``RateLimitError`` — 429 ``TOO_MANY_ATTEMPTS`` ;
- ``ServiceUnavailableError`` — 503 ``SERVICE_UNAVAILABLE``.

Exceptions techniques spécialisées (non destinées à être exposées telles
quelles en HTTP) : ``CommandExecutionError``, ``SecretEncryptionError``,
``SecretDecryptionError``, ``InvalidRefreshTokenError``,
``InvalidApiKeyError`` — une non-interception remonte en 500 enveloppé
``INTERNAL_ERROR`` via le handler global de ``main.py``.

``core/`` reste framework-agnostic (rules 55) : aucune dépendance
FastAPI/Starlette ici — la traduction HTTP (statut, headers, enveloppe
spec 09 ``{"error": {"code", "message"}}``) est faite par le handler
global enregistré dans ``main.py``.
"""

from __future__ import annotations

from typing import ClassVar


class WindFlowException(Exception):
    """Exception de base pour toutes les erreurs WindFlow.

    Attributes:
        message: Message lisible (jamais de donnée sensible — rules 40).
        details: Contexte structuré optionnel (dict, défaut ``{}``).
        status_code: Statut HTTP cible utilisé par le handler global
            de ``main.py`` (défaut ``500``).
        error_code: Code machine spec 09 (défaut ``INTERNAL_ERROR``).
        headers: Headers HTTP par défaut de la classe (ex.
            ``WWW-Authenticate`` pour les 401) — aucun par défaut.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, message: str = "", *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class APIError(WindFlowException):
    """Racine des erreurs API typées (spec 09 § Classes d'erreur).

    Les sous-classes ancrent le couple (statut HTTP, code machine) via
    les attributs de classe ``status_code``/``error_code`` ; le handler
    global de ``main.py`` convertit toute instance non interceptée en
    enveloppe ``{"error": {"code", "message", "details"?}}`` en
    préservant le ``correlation_id``.

    Args:
        message: Message lisible transporté dans ``error.message``.
        details: Contexte structuré optionnel (``error.details``).
        code: Override du code machine pour cette instance (ex.
            ``INVALID_CREDENTIALS`` sur le login) — prime sur le
            ``error_code`` de la classe.
        headers: Headers HTTP additionnels (ex. ``Retry-After``) —
            sinon les headers par défaut de la classe s'appliquent.
    """

    def __init__(
        self,
        message: str = "",
        *,
        details: dict | None = None,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message, details=details)
        self.code = code or type(self).error_code
        default_headers = type(self).headers
        self.http_headers = (
            headers
            if headers is not None
            else (dict(default_headers) if default_headers is not None else None)
        )


class NotFoundError(APIError):
    """Levée lorsqu'une ressource demandée est introuvable — 404.

    Sémantique ``404 NOT_FOUND`` générique. Utilisée pour les
    lectures/révoquations **scoped** : une ressource appartenant à un
    autre utilisateur est traitée comme inexistante (on ne révèle pas
    son existence — anti-énumération, rules 40). La ressource visée
    est identifiée par son type et son id dans ``details`` (jamais par
    un secret).

    Deux formes d'appel :

    - ``NotFoundError(resource, resource_id)`` — signature historique
      (STORY-124, consommateurs services) : message
      ``f"{resource} not found: {resource_id}"`` et ``details``
      ``{"resource", "resource_id"}`` ;
    - ``NotFoundError(message)`` — forme message libre (sweep
      STORY-127) : préserve au caractère près le message textuel
      historique de l'``HTTPException`` remplacée (convention « même
      statut / même message », non-régression stricte).
    """

    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(
        self,
        resource_or_message: str,
        resource_id: str | None = None,
    ) -> None:
        if resource_id is not None:
            self.resource = resource_or_message
            self.resource_id = resource_id
            super().__init__(
                f"{resource_or_message} not found: {resource_id}",
                details={
                    "resource": resource_or_message,
                    "resource_id": resource_id,
                },
            )
        else:
            self.resource = ""
            self.resource_id = ""
            super().__init__(resource_or_message)


class ConflictError(APIError):
    """Levée en cas de conflit de ressource — 409 ``CONFLICT``.

    Ex. slug dupliqué, plugin déjà installé, conteneur déjà géré par
    WindFlow (docker.py).
    """

    status_code = 409
    error_code = "CONFLICT"


class InvalidInputError(APIError):
    """Levée pour une entrée invalide — 400 ``INVALID_INPUT``.

    Format/paramètre invalide, JSON illisible, valeur incohérente
    (distinct de la validation de schéma Pydantic → 422).
    """

    status_code = 400
    error_code = "INVALID_INPUT"


class UnprocessableEntityError(APIError):
    """Levée pour une entité non traitable — 422 ``VALIDATION_ERROR``.

    Validation sémantique au-delà du schéma. Nom choisi pour éviter la
    collision d'import avec ``pydantic.ValidationError``.
    """

    status_code = 422
    error_code = "VALIDATION_ERROR"


class PermissionDeniedError(APIError):
    """Levée pour un accès refusé — 403 ``PERMISSION_DENIED``.

    Rôle insuffisant (RBAC — source de vérité API, spec 08), compte
    inactif, ressource appartenant à une autre organisation.
    """

    status_code = 403
    error_code = "PERMISSION_DENIED"


class AuthenticationError(APIError):
    """Levée pour un défaut d'authentification — 401.

    Porte par défaut le header ``WWW-Authenticate: Bearer`` (spec 09).
    Code de classe ``INVALID_OR_EXPIRED_TOKEN`` ; sur ``/auth/login``,
    lever avec ``code="INVALID_CREDENTIALS"`` (l'override d'instance
    prime, et le handler global applique de toute façon la
    spécialisation login de ``_status_to_code``).
    """

    status_code = 401
    error_code = "INVALID_OR_EXPIRED_TOKEN"
    headers = {"WWW-Authenticate": "Bearer"}


class RateLimitError(APIError):
    """Levée en cas de quota dépassé — 429 ``TOO_MANY_ATTEMPTS``.

    Passer ``headers={"Retry-After": "..."}`` le cas échéant pour
    informer le client du délai avant nouvel essai.
    """

    status_code = 429
    error_code = "TOO_MANY_ATTEMPTS"


class ServiceUnavailableError(APIError):
    """Levée lorsqu'une dépendance est indisponible — 503.

    Ex. daemon Docker injoignable (ping), connexion perdue.
    """

    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"


class CommandExecutionError(WindFlowException):
    """Levée lorsqu'une commande système échoue (local ou distant).

    Attributes:
        command: La commande ayant échoué.
        exit_status: Code de retour du processus.
        stderr: Sortie d'erreur standard (déstrippée) — jamais
            exposée dans le payload HTTP (le handler global la retire
            des ``details`` ; rules 40).
    """

    def __init__(
        self,
        command: str,
        exit_status: int,
        stderr: str,
    ):
        self.command = command
        self.exit_status = exit_status
        self.stderr = stderr.strip()
        message = (
            f"La commande '{command}' a échoué avec le code {exit_status}. "
            f"Stderr : {self.stderr}"
        )
        super().__init__(
            message,
            details={
                "command": command,
                "exit_status": exit_status,
                "stderr": self.stderr,
            },
        )


class SecretEncryptionError(WindFlowException):
    """Levée lorsqu'une opération de chiffrement de secret échoue.

    Le message ne contient jamais de matériel cryptographique
    (ni clé maîtresse, ni valeur chiffrée/déchiffrée).
    """


class SecretDecryptionError(WindFlowException):
    """Levée lorsqu'une opération de déchiffrement de secret échoue.

    Typiquement : mauvaise clé maîtresse, ciphertext corrompu ou
    altéré (Fernet invalide la signature HMAC). Le message ne contient
    jamais de matériel cryptographique.
    """


class InvalidRefreshTokenError(WindFlowException):
    """Levée lorsqu'un refresh token est invalide (STORY-123.2).

    Token inconnu, expiré, consommé ou malformé. Refus sémantique
    ``401 INVALID_OR_EXPIRED_TOKEN`` (spec 09) — le message ne divulgue
    ni la valeur du token ni la raison exacte (anti-énumération) :
    l'appelant (STORY-123.3) mappe systématiquement à 401.
    """

    def __init__(self, reason: str = "Invalid or expired refresh token") -> None:
        self.reason = reason
        super().__init__(reason)


class InvalidApiKeyError(WindFlowException):
    """Levée lorsqu'une clé API est invalide (STORY-124.2).

    Clé inconnue, malformée, révoquée, expirée ou propriétaire inactif.
    Refus sémantique ``401`` sans divulgation (anti-énumération, rules
    40) : le message ne distingue jamais « clé inconnue » de « clé
    révoquée/expirée » — l'appelant (STORY-124.3) mappe
    systématiquement à 401.
    """

    def __init__(self, reason: str = "Invalid API key") -> None:
        self.reason = reason
        super().__init__(reason)


class SSHHostKeyNotAcceptedError(WindFlowException):
    """Levée quand la clé d'hôte SSH présentée n'est pas acceptée (STORY-131.3).

    TOFU (*Trust On First Use*, spec 15 § Hosts distants) : l'empreinte
    présentée est **inconnue** (première connexion — une ligne PENDING
    ``accepted=False`` a été enregistrée par le helper
    ``ssh_connection``) ou **enregistrée mais non acceptée**
    (acceptation explicite toujours attendue via ``POST
    /targets/{id}/ssh-fingerprints/accept``). La session est bloquée :
    jamais d'ajout silencieux au known_hosts (anti-MITM).

    Exception **technique runtime** (elle n'est pas destinée à être
    exposée telle quelle en HTTP) : les callers la traduisent — scan →
    ``CommandExecutionError``, test-connection → réponse structurée
    avec ``fingerprint_status``. Le message est générique côté client
    (rules 40 : pas de secret, l'empreinte d'hôte étant publique par
    nature elle peut figurer dans ``details``).

    Attributes:
        fingerprint: Empreinte présentée ``SHA256:<base64nopad>``.
        target_id: Cible vérifiée (``None`` hors contexte cible
            persistée — ex. discovery avant création).
    """

    def __init__(
        self,
        message: str = "",
        *,
        details: dict | None = None,
        fingerprint: str | None = None,
        target_id: str | None = None,
    ) -> None:
        self.fingerprint = fingerprint
        self.target_id = target_id
        super().__init__(
            message
            or (
                "Empreinte de clé d'hôte SSH inconnue ou non acceptée — "
                "acceptation explicite requise avant toute connexion"
            ),
            details=details,
        )


class SSHHostKeyMismatchError(WindFlowException):
    """Levée en cas de divergence d'empreinte de clé d'hôte SSH (STORY-131.3).

    Anti-MITM (spec 15) : l'empreinte présentée **diffère** de
    l'empreinte acceptée enregistrée pour ``(hostname, port, key_type)``
    — l'hôte a été reconfiguré **ou** la connexion est usurpée
    (man-in-the-middle). La connexion est bloquée systématiquement et
    l'empreinte acceptée n'est **jamais écrasée** : une ré-acceptation
    délibérée (reset + accept) est requise si le changement est légitime.

    Exception **technique runtime** — traduite par les callers (message
    générique côté client, détails internes loggés sans donnée
    sensible, rules 40). Un événement
    ``TARGET_SSH_FINGERPRINT_DIVERGENCE`` et une ligne d'audit
    ``target.fingerprint_divergence`` sont émis au point de blocage.

    Attributes:
        fingerprint: Empreinte présentée (divergente).
        expected_fingerprint: Empreinte acceptée faisant autorité.
        target_id: Cible vérifiée (``None`` hors contexte cible
            persistée).
    """

    def __init__(
        self,
        message: str = "",
        *,
        details: dict | None = None,
        fingerprint: str | None = None,
        expected_fingerprint: str | None = None,
        target_id: str | None = None,
    ) -> None:
        self.fingerprint = fingerprint
        self.expected_fingerprint = expected_fingerprint
        self.target_id = target_id
        super().__init__(
            message
            or (
                "Empreinte de clé d'hôte SSH divergente — hôte reconfiguré "
                "ou usurpation possible (MITM) ; ré-acceptation délibérée requise"
            ),
            details=details,
        )


class GateDeniedError(WindFlowException):
    """Levée par le pipeline quand une gate pre-deploy refuse (STORY-170.2).

    Exception **interne pipeline** : elle est interceptée par le
    ``except`` existant de ``deploy_stack_async``
    (:mod:`app.tasks.background_tasks`) qui passe le déploiement en
    ``FAILED`` via ``DeploymentService.update_status`` — les endpoints ne
    l'exposent **jamais** en réponse HTTP (un refus de gate s'exprime
    comme un échec de déploiement classique, spec 11 § Hooks de
    déploiement). Aucun mapping HTTP dédié n'est donc nécessaire.

    Le ``details`` structure la trace typée consommée par les lignes
    ``deployment_events`` (STORY-167) et l'événement bus
    ``deployment.failed`` (STORY-162) :

    - ``error_type``: ``"gate_denied"`` (marqueur du volet) ;
    - ``code``: ``"GATE_DENIED"`` (refus explicite) |
      ``"GATE_TIMEOUT"`` (timeout, refus prudent) |
      ``"gate_error"`` (handler en erreur, refus prudent — divergence
      n°4) ;
    - ``plugin``: nom du plugin dont la gate a refusé ;
    - ``reason``: raison lisible (jamais de secret — rules 40).

    Args:
        plugin_name: Nom du plugin dont la gate a refusé.
        code: ``GATE_DENIED`` | ``GATE_TIMEOUT`` | ``gate_error``.
        reason: Raison lisible du refus (sans donnée sensible).
    """

    def __init__(
        self,
        plugin_name: str,
        code: str = "GATE_DENIED",
        reason: str = "",
    ) -> None:
        self.plugin_name = plugin_name
        self.code = code
        self.reason = reason
        super().__init__(
            f"Déploiement refusé par la gate du plugin {plugin_name} "
            f"({code}) : {reason}",
            details={
                "error_type": "gate_denied",
                "code": code,
                "plugin": plugin_name,
                "reason": reason,
            },
        )


class InvalidEventTypeNameError(WindFlowException):
    """Levée quand un type d'événement hors ``EventType`` est passé au bus.

    STORY-162 (AC 4) : ``Bus.emit`` accepte exclusivement des membres de
    :class:`~app.core.events.EventType` — l'ancienne réencapsulation
    silencieuse en ``system.error`` (fragilité §4 de WEBSOCKET-REAL-TIME)
    est remplacée par cette erreur explicite. Exception **technique**
    (pas destinée à être exposée en HTTP : interception par les émetteurs
    best-effort).
    """

    def __init__(
        self,
        message: str = "Invalid event type name (EventType member required)",
        *,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details=details)


__all__ = [
    "APIError",
    "AuthenticationError",
    "CommandExecutionError",
    "ConflictError",
    "GateDeniedError",
    "InvalidApiKeyError",
    "InvalidEventTypeNameError",
    "InvalidInputError",
    "InvalidRefreshTokenError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "SSHHostKeyMismatchError",
    "SSHHostKeyNotAcceptedError",
    "SecretDecryptionError",
    "SecretEncryptionError",
    "ServiceUnavailableError",
    "UnprocessableEntityError",
    "WindFlowException",
]
