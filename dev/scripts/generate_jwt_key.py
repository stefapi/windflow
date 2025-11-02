#!/usr/bin/env python3
"""
Script utilitaire pour générer des clés JWT sécurisées.

Usage:
    python dev/scripts/generate_jwt_key.py

Output:
    Génère une clé JWT de 256 bits (32 caractères hexadécimaux)
    compatible avec les exigences de sécurité de WindFlow.
"""

import secrets
import sys
from pathlib import Path


def generate_jwt_secret_key() -> str:
    """Génère une clé JWT sécurisée de 256 bits."""
    return secrets.token_hex(32)


def main():
    """Point d'entrée principal du script."""
    print("🔐 Génération de clé JWT sécurisée pour WindFlow")
    print("=" * 50)

    # Générer la clé
    secret_key = generate_jwt_secret_key()

    print(f"✅ Clé JWT générée: {secret_key}")
    print(f"📏 Longueur: {len(secret_key)} caractères")
    print(f"🔒 Sécurité: 256 bits ({len(secret_key) * 4} bits)")

    # Vérifier la longueur minimale recommandée
    if len(secret_key) < 32:
        print("❌ ERREUR: Clé trop courte (minimum 32 caractères)")
        sys.exit(1)

    print("\n📝 Instructions d'utilisation:")
    print("1. Ajoutez cette ligne à votre fichier .env:")
    print(f"   JWT_SECRET_KEY={secret_key}")
    print("2. Redémarrez votre serveur WindFlow")
    print("3. Supprimez ce script après utilisation")

    print("\n🔧 Configuration recommandée dans .env:")
    print(f"JWT_SECRET_KEY={secret_key}")
    print("JWT_ALGORITHM=HS256")
    print("ACCESS_TOKEN_EXPIRE_MINUTES=60")
    print("REFRESH_TOKEN_EXPIRE_DAYS=7")

    print("\n✅ Clé générée avec succès!")


if __name__ == "__main__":
    main()
