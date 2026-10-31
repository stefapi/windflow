"""Enum canonique des familles de workloads (spec 02 — STORY-174.1).

Les trois familles du modèle directeur (chapitre 02 § Le principe à trois
familles) et l'entité Cluster. Consommé par l'ABC
:class:`~app.services.workloads.base.WorkloadAdapter` (``family()``).
"""

from enum import Enum


class WorkloadFamily(str, Enum):
    """Famille d'appartenance d'un workload (spec 02 § Définition des familles).

    - ``APP`` : workload de type service applicatif (containers, stacks
      Compose, releases Helm, manifests K8s) ;
    - ``MACHINE`` : workload de type machine virtuelle (KVM, LXD, Incus,
      LXC, VirtualBox — adapters Roadmap) ;
    - ``HOST`` : substrat d'hébergement (baremetal, Proxmox, Docker
      distant — adapters Roadmap) ;
    - ``CLUSTER`` : grappe multi-nœuds de premier rang (Kubernetes,
      Swarm, Proxmox — adapters Roadmap).
    """

    APP = "app"
    MACHINE = "machine"
    HOST = "host"
    CLUSTER = "cluster"
