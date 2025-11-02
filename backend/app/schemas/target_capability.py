"""Schemas Pydantic pour les capacités de cibles détectées."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class CapabilityType(str, Enum):
    """Types de capacités détectées sur une cible."""

    # Virtualisation
    LIBVIRT = "libvirt"
    VIRTUALBOX = "virtualbox"
    VAGRANT = "vagrant"
    PROXMOX = "proxmox"
    QEMU_KVM = "qemu_kvm"

    # Conteneurisation
    DOCKER = "docker"
    DOCKER_COMPOSE = "docker_compose"
    DOCKER_SWARM = "docker_swarm"
    PODMAN = "podman"

    # Kubernetes / Orchestration
    KUBECTL = "kubectl"
    KUBEADM = "kubeadm"
    K3S = "k3s"
    MICROK8S = "microk8s"


class TargetCapabilityBase(BaseModel):
    """Schéma de base pour représenter une capacité détectée."""

    capability_type: CapabilityType = Field(
        ...,
        description="Type de capacité détectée sur la cible"
    )
    is_available: bool = Field(
        default=False,
        description="Indique si la capacité est disponible sur la cible"
    )
    version: Optional[str] = Field(
        default=None,
        description="Version de l'outil détectée lorsque disponible"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Informations supplémentaires retournées par le scanner"
    )


class TargetCapabilityResponse(TargetCapabilityBase):
    """Schéma de réponse pour une capacité détectée."""

    id: str = Field(..., description="Identifiant unique de la capacité")
    target_id: str = Field(..., description="Identifiant de la cible associée")
    detected_at: datetime = Field(..., description="Date de détection de la capacité")
    created_at: datetime = Field(..., description="Date de création de l'entrée")
    updated_at: datetime = Field(..., description="Date de dernière mise à jour")

    model_config = ConfigDict(from_attributes=True)
