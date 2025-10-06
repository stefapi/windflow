"""
Script de test simple pour valider le fichier baserow.yaml.
"""

import yaml
from pathlib import Path

def test_baserow_yaml():
    """Teste le chargement et la validation du fichier baserow.yaml."""

    print("\n" + "=" * 60)
    print("  Test du fichier baserow.yaml")
    print("=" * 60 + "\n")

    # Chemin vers le fichier
    yaml_path = Path(__file__).parent.parent / "stacks_definitions" / "baserow.yaml"

    print(f"📁 Chemin: {yaml_path}")
    print(f"✓ Fichier existe: {yaml_path.exists()}\n")

    if not yaml_path.exists():
        print("❌ Fichier non trouvé!")
        return False

    # Charger le YAML
    print("📋 Chargement du fichier YAML...")
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        print("✓ YAML chargé avec succès\n")
    except Exception as e:
        print(f"❌ Erreur de chargement: {e}\n")
        return False

    # Vérifier la structure
    print("🔍 Validation de la structure...\n")

    errors = []

    # Métadonnées
    if "metadata" not in data:
        errors.append("Section 'metadata' manquante")
    else:
        metadata = data["metadata"]
        print("📦 Métadonnées:")
        print(f"  • Nom: {metadata.get('name', 'N/A')}")
        print(f"  • Version: {metadata.get('version', 'N/A')}")
        print(f"  • Catégorie: {metadata.get('category', 'N/A')}")
        print(f"  • Auteur: {metadata.get('author', 'N/A')}")
        print(f"  • Licence: {metadata.get('license', 'N/A')}")
        print(f"  • Public: {metadata.get('is_public', False)}")
        print(f"  • Tags: {len(metadata.get('tags', []))}")
        print()

        required_meta = ["name", "version", "description"]
        for field in required_meta:
            if not metadata.get(field):
                errors.append(f"Métadonnée requise manquante: {field}")

    # Template
    if "template" not in data:
        errors.append("Section 'template' manquante")
    else:
        template = data["template"]
        print("🐳 Template Docker Compose:")
        services = template.get("services", {})
        print(f"  • Services: {len(services)}")
        for service_name in services.keys():
            print(f"    - {service_name}")

        volumes = template.get("volumes", {})
        print(f"  • Volumes: {len(volumes)}")

        networks = template.get("networks", {})
        print(f"  • Networks: {len(networks)}")
        print()

        if not services:
            errors.append("Template doit contenir au moins un service")

    # Variables
    if "variables" not in data:
        errors.append("Section 'variables' manquante")
    else:
        variables = data["variables"]
        print(f"⚙️  Variables configurables: {len(variables)}\n")

        valid_types = ["string", "number", "boolean", "password", "enum", "textarea"]

        for var_name, var_config in variables.items():
            if not isinstance(var_config, dict):
                errors.append(f"Configuration invalide pour variable {var_name}")
                continue

            var_type = var_config.get("type")
            var_label = var_config.get("label", "N/A")
            var_default = var_config.get("default", "N/A")
            var_required = var_config.get("required", False)

            print(f"  • {var_name}")
            print(f"    Type: {var_type}")
            print(f"    Label: {var_label}")
            print(f"    Défaut: {var_default}")
            print(f"    Requis: {var_required}")

            if "group" in var_config:
                print(f"    Groupe: {var_config['group']}")

            if not var_type:
                errors.append(f"Type manquant pour variable {var_name}")
            elif var_type not in valid_types:
                errors.append(f"Type invalide '{var_type}' pour variable {var_name}")

            print()

    # Résultat
    print("=" * 60)
    if errors:
        print(f"\n❌ {len(errors)} erreur(s) trouvée(s):\n")
        for error in errors:
            print(f"  • {error}")
        print()
        return False
    else:
        print("\n✅ Fichier baserow.yaml valide!")
        print("\n📊 Résumé:")
        print(f"  • Métadonnées: OK")
        print(f"  • Template: OK ({len(data['template'].get('services', {}))} services)")
        print(f"  • Variables: OK ({len(data['variables'])} variables)")
        print()
        return True

if __name__ == "__main__":
    import sys
    success = test_baserow_yaml()
    sys.exit(0 if success else 1)
