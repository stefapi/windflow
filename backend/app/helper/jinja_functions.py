"""
Fonctions Jinja2 génériques pour templates de déploiement.

Ces fonctions sont disponibles dans tous les templates (Docker, Docker Compose, etc.)
et permettent de générer dynamiquement des valeurs sécurisées et utilitaires.
"""

import secrets
import string
import uuid
import base64
import hashlib
from typing import Optional, Literal


class JinjaFunctions:
    """Collection de fonctions utilitaires pour templates Jinja2."""

    @staticmethod
    def generate_password(length: int = 24, include_special: bool = True) -> str:
        """
        Génère un mot de passe sécurisé aléatoire.

        Args:
            length: Longueur du mot de passe (défaut: 24)
            include_special: Inclure des caractères spéciaux (défaut: True)

        Returns:
            Mot de passe aléatoire sécurisé

        Example:
            >>> pwd = JinjaFunctions.generate_password(32)
            >>> len(pwd)
            32
            >>> pwd = JinjaFunctions.generate_password(16, include_special=False)
            >>> all(c.isalnum() for c in pwd)
            True
        """
        if include_special:
            # Lettres, chiffres et caractères spéciaux sûrs
            characters = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
        else:
            # Uniquement lettres et chiffres
            characters = string.ascii_letters + string.digits

        password = ''.join(secrets.choice(characters) for _ in range(length))
        return password

    @staticmethod
    def generate_secret(length: int = 32) -> str:
        """
        Génère un secret hexadécimal aléatoire.

        Utile pour les clés secrètes, tokens, etc.

        Args:
            length: Longueur du secret en caractères hex (défaut: 32)

        Returns:
            Secret hexadécimal en minuscules

        Example:
            >>> secret = JinjaFunctions.generate_secret(64)
            >>> len(secret)
            64
            >>> all(c in '0123456789abcdef' for c in secret)
            True
        """
        # Génère length/2 bytes puis convertit en hex
        num_bytes = (length + 1) // 2
        random_bytes = secrets.token_bytes(num_bytes)
        hex_string = random_bytes.hex()
        return hex_string[:length]

    @staticmethod
    def random_string(
        length: int,
        charset: Literal["alphanumeric", "alpha", "numeric", "hex"] = "alphanumeric"
    ) -> str:
        """
        Génère une chaîne aléatoire selon un charset spécifique.

        Args:
            length: Longueur de la chaîne
            charset: Type de caractères à utiliser
                - "alphanumeric": Lettres et chiffres
                - "alpha": Lettres uniquement
                - "numeric": Chiffres uniquement
                - "hex": Hexadécimal (0-9, a-f)

        Returns:
            Chaîne aléatoire

        Example:
            >>> s = JinjaFunctions.random_string(8, "alpha")
            >>> len(s)
            8
            >>> s.isalpha()
            True
        """
        charset_map = {
            "alphanumeric": string.ascii_letters + string.digits,
            "alpha": string.ascii_letters,
            "numeric": string.digits,
            "hex": "0123456789abcdef"
        }

        if charset not in charset_map:
            raise ValueError(f"Charset invalide: {charset}. Options: {list(charset_map.keys())}")

        characters = charset_map[charset]
        result = ''.join(secrets.choice(characters) for _ in range(length))
        return result

    @staticmethod
    def generate_uuid() -> str:
        """
        Génère un UUID v4 aléatoire.

        Returns:
            UUID au format string (avec tirets)

        Example:
            >>> uid = JinjaFunctions.generate_uuid()
            >>> len(uid)
            36
            >>> uid.count('-')
            4
        """
        return str(uuid.uuid4())

    @staticmethod
    def generate_uuid_short() -> str:
        """
        Génère un UUID v4 court (sans tirets).

        Returns:
            UUID au format string sans tirets

        Example:
            >>> uid = JinjaFunctions.generate_uuid_short()
            >>> len(uid)
            32
            >>> '-' in uid
            False
        """
        return str(uuid.uuid4()).replace('-', '')

    @staticmethod
    def base64_encode(value: str) -> str:
        """
        Encode une valeur en base64.

        Args:
            value: Valeur à encoder

        Returns:
            Valeur encodée en base64

        Example:
            >>> encoded = JinjaFunctions.base64_encode("hello")
            >>> encoded
            'aGVsbG8='
        """
        value_bytes = value.encode('utf-8')
        encoded_bytes = base64.b64encode(value_bytes)
        return encoded_bytes.decode('utf-8')

    @staticmethod
    def base64_decode(value: str) -> str:
        """
        Décode une valeur base64.

        Args:
            value: Valeur base64 à décoder

        Returns:
            Valeur décodée

        Example:
            >>> decoded = JinjaFunctions.base64_decode("aGVsbG8=")
            >>> decoded
            'hello'
        """
        value_bytes = value.encode('utf-8')
        decoded_bytes = base64.b64decode(value_bytes)
        return decoded_bytes.decode('utf-8')

    @staticmethod
    def hash_value(
        value: str,
        algorithm: Literal["sha256", "sha512", "md5", "sha1"] = "sha256"
    ) -> str:
        """
        Hash une valeur avec l'algorithme spécifié.

        Args:
            value: Valeur à hasher
            algorithm: Algorithme de hash (défaut: sha256)

        Returns:
            Hash hexadécimal

        Example:
            >>> hashed = JinjaFunctions.hash_value("hello", "sha256")
            >>> len(hashed)
            64
        """
        algorithm_map = {
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
            "md5": hashlib.md5,
            "sha1": hashlib.sha1
        }

        if algorithm not in algorithm_map:
            raise ValueError(f"Algorithme invalide: {algorithm}. Options: {list(algorithm_map.keys())}")

        hash_func = algorithm_map[algorithm]
        value_bytes = value.encode('utf-8')
        hashed = hash_func(value_bytes).hexdigest()
        return hashed

    @staticmethod
    def random_port(min_port: int = 10000, max_port: int = 65535) -> int:
        """
        Génère un numéro de port aléatoire dans une plage.

        Args:
            min_port: Port minimum (défaut: 10000)
            max_port: Port maximum (défaut: 65535)

        Returns:
            Numéro de port aléatoire

        Example:
            >>> port = JinjaFunctions.random_port(8000, 9000)
            >>> 8000 <= port <= 9000
            True
        """
        return secrets.randbelow(max_port - min_port + 1) + min_port

    @staticmethod
    def env(var_name: str, default: str = "") -> str:
        """
        Récupère une variable d'environnement.

        Args:
            var_name: Nom de la variable d'environnement
            default: Valeur par défaut si non trouvée

        Returns:
            Valeur de la variable ou valeur par défaut

        Example:
            >>> import os
            >>> os.environ['TEST_VAR'] = 'test_value'
            >>> JinjaFunctions.env('TEST_VAR')
            'test_value'
            >>> JinjaFunctions.env('NON_EXISTENT', 'default')
            'default'
        """
        import os
        return os.environ.get(var_name, default)

    @staticmethod
    def now(format: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        Retourne la date/heure actuelle formatée.

        Args:
            format: Format de date (strftime)

        Returns:
            Date/heure formatée

        Example:
            >>> timestamp = JinjaFunctions.now("%Y-%m-%d")
            >>> len(timestamp)
            10
        """
        from datetime import datetime
        return datetime.utcnow().strftime(format)

    @staticmethod
    def random_choice(*choices: str) -> str:
        """
        Choix aléatoire parmi plusieurs options.

        Args:
            *choices: Options disponibles

        Returns:
            Une option choisie aléatoirement

        Example:
            >>> choice = JinjaFunctions.random_choice("option1", "option2", "option3")
            >>> choice in ("option1", "option2", "option3")
            True
        """
        if not choices:
            raise ValueError("Au moins une option doit être fournie")

        return secrets.choice(choices)


# Dictionnaire des fonctions disponibles pour Jinja2
JINJA_FUNCTIONS = {
    'generate_password': JinjaFunctions.generate_password,
    'generate_secret': JinjaFunctions.generate_secret,
    'random_string': JinjaFunctions.random_string,
    'generate_uuid': JinjaFunctions.generate_uuid,
    'generate_uuid_short': JinjaFunctions.generate_uuid_short,
    'base64_encode': JinjaFunctions.base64_encode,
    'base64_decode': JinjaFunctions.base64_decode,
    'hash_value': JinjaFunctions.hash_value,
    'random_port': JinjaFunctions.random_port,
    'env': JinjaFunctions.env,
    'now': JinjaFunctions.now,
    'random_choice': JinjaFunctions.random_choice,
}
