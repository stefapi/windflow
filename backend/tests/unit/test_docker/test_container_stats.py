"""
Tests unitaires pour le module container_stats.

Teste les fonctions de calcul des statistiques Docker et le WebSocket endpoint.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# Import des fonctions à tester
from app.websocket.container_stats import (
    calculate_cpu_percent,
    calculate_memory_percent,
    calculate_network_io,
    calculate_block_io,
    format_stats_response,
)


class TestCalculateCpuPercent:
    """Tests pour la fonction calculate_cpu_percent."""

    def test_calculate_cpu_percent_basic(self):
        """Test basique du calcul CPU percent."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 1000000000,
                    "percpu_usage": [250000000, 250000000, 250000000, 250000000]
                },
                "system_cpu_usage": 2000000000,
                "online_cpus": 4
            },
            "precpu_stats": {
                "cpu_usage": {
                    "total_usage": 500000000,
                    "percpu_usage": [125000000, 125000000, 125000000, 125000000]
                },
                "system_cpu_usage": 1000000000,
                "online_cpus": 4
            }
        }

        result = calculate_cpu_percent(stats)
        # CPU delta = 500000000, System delta = 1000000000, CPUs = 4
        # percent = (500000000 / 1000000000) * 4 * 100 = 200%
        assert result == 200.0

    def test_calculate_cpu_percent_no_delta(self):
        """Test quand il n'y a pas de changement CPU."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 4
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 4
            }
        }

        result = calculate_cpu_percent(stats)
        assert result == 0.0

    def test_calculate_cpu_percent_zero_system_delta(self):
        """Test avec un delta système à zéro (évite division par zéro)."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 4
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 500000000},
                "system_cpu_usage": 2000000000,  # Même valeur = delta 0
                "online_cpus": 4
            }
        }

        result = calculate_cpu_percent(stats)
        assert result == 0.0

    def test_calculate_cpu_percent_missing_fields(self):
        """Test avec des champs manquants."""
        stats = {}
        result = calculate_cpu_percent(stats)
        assert result == 0.0

    def test_calculate_cpu_percent_single_cpu(self):
        """Test avec un seul CPU."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 2000000000},
                "system_cpu_usage": 4000000000,
                "online_cpus": 1
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 1
            }
        }

        result = calculate_cpu_percent(stats)
        # CPU delta = 1000000000, System delta = 2000000000, CPUs = 1
        # percent = (1000000000 / 2000000000) * 1 * 100 = 50%
        assert result == 50.0


class TestCalculateMemoryPercent:
    """Tests pour la fonction calculate_memory_percent (retourne tuple)."""

    def test_calculate_memory_percent_basic(self):
        """Test basique du calcul mémoire."""
        stats = {
            "memory_stats": {
                "usage": 536870912,  # 512 MB
                "limit": 1073741824  # 1 GB
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        # 512 MB / 1024 MB = 50%
        assert percent == 50.0
        assert used == 536870912
        assert limit == 1073741824

    def test_calculate_memory_percent_full(self):
        """Test avec mémoire pleine."""
        stats = {
            "memory_stats": {
                "usage": 1073741824,
                "limit": 1073741824
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        assert percent == 100.0
        assert used == 1073741824
        assert limit == 1073741824

    def test_calculate_memory_percent_zero_limit(self):
        """Test avec limite à zéro (évite division par zéro)."""
        stats = {
            "memory_stats": {
                "usage": 536870912,
                "limit": 0
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        assert percent == 0.0
        assert used == 536870912
        assert limit == 0

    def test_calculate_memory_percent_missing_fields(self):
        """Test avec des champs manquants."""
        stats = {}
        percent, used, limit = calculate_memory_percent(stats)
        assert percent == 0.0
        assert used == 0
        assert limit == 0


class TestCalculateNetworkIo:
    """Tests pour la fonction calculate_network_io."""

    def test_calculate_network_io_basic(self):
        """Test basique du calcul réseau."""
        stats = {
            "networks": {
                "eth0": {
                    "rx_bytes": 1048576,  # 1 MB
                    "tx_bytes": 2097152   # 2 MB
                }
            }
        }

        rx, tx = calculate_network_io(stats)
        assert rx == 1048576
        assert tx == 2097152

    def test_calculate_network_io_multiple_interfaces(self):
        """Test avec plusieurs interfaces réseau."""
        stats = {
            "networks": {
                "eth0": {
                    "rx_bytes": 1000000,
                    "tx_bytes": 2000000
                },
                "eth1": {
                    "rx_bytes": 500000,
                    "tx_bytes": 300000
                }
            }
        }

        rx, tx = calculate_network_io(stats)
        assert rx == 1500000  # 1000000 + 500000
        assert tx == 2300000  # 2000000 + 300000

    def test_calculate_network_io_no_networks(self):
        """Test sans données réseau."""
        stats = {}
        rx, tx = calculate_network_io(stats)
        assert rx == 0
        assert tx == 0

    def test_calculate_network_io_empty_networks(self):
        """Test avec réseaux vides."""
        stats = {"networks": {}}
        rx, tx = calculate_network_io(stats)
        assert rx == 0
        assert tx == 0


class TestCalculateBlockIo:
    """Tests pour la fonction calculate_block_io."""

    def test_calculate_block_io_basic(self):
        """Test basique du calcul I/O disque."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "read", "value": 1048576},
                    {"op": "write", "value": 2097152},
                    {"op": "read", "value": 524288},
                    {"op": "write", "value": 262144}
                ]
            }
        }

        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 1572864  # 1048576 + 524288
        assert write_bytes == 2359296  # 2097152 + 262144

    def test_calculate_block_io_no_stats(self):
        """Test sans données blkio."""
        stats = {}
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 0
        assert write_bytes == 0

    def test_calculate_block_io_empty_list(self):
        """Test avec liste vide."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": []
            }
        }
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 0
        assert write_bytes == 0

    def test_calculate_block_io_none(self):
        """Test avec io_service_bytes_recursive à None."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": None
            }
        }
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 0
        assert write_bytes == 0


class TestFormatStatsResponse:
    """Tests pour la fonction format_stats_response."""

    def test_format_stats_response_complete(self):
        """Test avec des stats complètes."""
        container_id = "abc123"
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 2000000000},
                "system_cpu_usage": 4000000000,
                "online_cpus": 2
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 2
            },
            "memory_stats": {
                "usage": 536870912,
                "limit": 1073741824
            },
            "networks": {
                "eth0": {
                    "rx_bytes": 1000000,
                    "tx_bytes": 2000000
                }
            },
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "read", "value": 500000},
                    {"op": "write", "value": 300000}
                ]
            }
        }

        result = format_stats_response(container_id, stats)

        assert result["container_id"] == container_id
        assert result["type"] == "stats"
        # CPU est dans un sous-objet
        assert "cpu" in result
        assert result["cpu"]["percent"] == 100.0
        # Memory est dans un sous-objet
        assert "memory" in result
        assert result["memory"]["percent"] == 50.0
        assert result["memory"]["used"] == 536870912
        assert result["memory"]["limit"] == 1073741824
        # Network
        assert "network" in result
        assert result["network"]["rx_bytes"] == 1000000
        assert result["network"]["tx_bytes"] == 2000000
        # Block I/O
        assert "block_io" in result
        assert result["block_io"]["read_bytes"] == 500000
        assert result["block_io"]["write_bytes"] == 300000

    def test_format_stats_response_empty(self):
        """Test avec des stats vides."""
        container_id = "empty"
        stats = {}

        result = format_stats_response(container_id, stats)

        assert result["container_id"] == container_id
        assert result["type"] == "stats"
        # CPU percent à 0
        assert result["cpu"]["percent"] == 0.0
        # Memory
        assert result["memory"]["percent"] == 0.0
        # Network
        assert result["network"]["rx_bytes"] == 0
        assert result["network"]["tx_bytes"] == 0
        # Block I/O
        assert result["block_io"]["read_bytes"] == 0
        assert result["block_io"]["write_bytes"] == 0
