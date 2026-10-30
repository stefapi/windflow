"""
Schémas Pydantic pour les packages de plugins téléchargés.

Contrat de sortie interne de ``PluginPackageService`` (STORY-169.1) :
résultat du pipeline download sécurisé → checksum SHA-256 → extraction
durcie. Consommé par la validation du contenu extrait (STORY-169.2) et
l'orchestration/rollback (STORY-169.3).

Non exposé en HTTP — champs non sensibles uniquement (rules 40 : ni URL
complète ni contenu de package).
"""

from pydantic import BaseModel, ConfigDict, Field


class PluginPackageResult(BaseModel):
    """Résultat du téléchargement et de l'extraction d'un package plugin.

    Produit par ``PluginPackageService.download_and_extract`` après
    validation SSRF de l'URL, téléchargement streaming borné, vérification
    du checksum SHA-256 (obligatoire, rejet sur écart) et extraction
    sécurisée (anti path-traversal/symlink/bombe) vers
    ``plugins_base_dir/{name}/``.
    """

    name: str = Field(..., description="Nom du plugin (kebab-case)")
    version: str = Field(..., description="Version du plugin (semver)")
    checksum_sha256: str = Field(
        ..., description="Checksum SHA-256 vérifié du package (hex 64)"
    )
    package_size_bytes: int = Field(
        ..., ge=0, description="Taille du package téléchargé en octets"
    )
    extracted_path: str = Field(
        ...,
        description=(
            "Chemin absolu du répertoire extrait sous plugins_base_dir/{name}/"
        ),
    )
    files_count: int = Field(
        ..., ge=0, description="Nombre de membres extraits de l'archive"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "traefik",
                    "version": "1.2.0",
                    "checksum_sha256": "a" * 64,
                    "package_size_bytes": 20480,
                    "extracted_path": "./data/plugins/traefik",
                    "files_count": 12,
                }
            ]
        }
    )
