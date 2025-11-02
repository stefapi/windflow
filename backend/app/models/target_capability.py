"""Modèle TargetCapability pour stocker les capacités détectées."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    JSON,
    ForeignKey,
    Boolean,
    Enum as SQLEnum,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .target import Target


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


class TargetCapability(Base):
    """Capacité détectée pour une cible donnée."""

    __tablename__ = "target_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "target_id",
            "capability_type",
            name="uq_target_capability_type",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    target_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("targets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    capability_type: Mapped[CapabilityType] = mapped_column(
        SQLEnum(CapabilityType),
        nullable=False,
    )

    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Informations supplémentaires retournées par le scanner",
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Date de détection de la capacité",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    target: Mapped["Target"] = relationship(
        "Target",
        back_populates="capabilities",
    )

    def __repr__(self) -> str:
        return (
            f"<TargetCapability(id={self.id}, "
            f"target_id={self.target_id}, "
            f"type={self.capability_type}, "
            f"available={self.is_available})>"
        )
