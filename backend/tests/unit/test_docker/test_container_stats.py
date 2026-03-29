"""
Tests unitaires pour le module container_stats.

Teste les fonctions de calcul des statistiques Docker et le WebSocket endpoint.
"""

# Import des fonctions à tester
from app.websocket.container_stats import (
    _sum_blkio_entries,
    calculate_block_io,
    calculate_cpu_percent,
    calculate_memory_percent,
    calculate_network_io,
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
                    "percpu_usage": [250000000, 250000000, 250000000, 250000000],
                },
                "system_cpu_usage": 2000000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {
                    "total_usage": 500000000,
                    "percpu_usage": [125000000, 125000000, 125000000, 125000000],
                },
                "system_cpu_usage": 1000000000,
                "online_cpus": 4,
            },
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
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 4,
            },
        }

        result = calculate_cpu_percent(stats)
        assert result == 0.0

    def test_calculate_cpu_percent_zero_system_delta(self):
        """Test avec un delta système à zéro (évite division par zéro)."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 500000000},
                "system_cpu_usage": 2000000000,  # Même valeur = delta 0
                "online_cpus": 4,
            },
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
                "online_cpus": 1,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 1,
            },
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
            "memory_stats": {"usage": 536870912, "limit": 1073741824}  # 512 MB  # 1 GB
        }

        percent, used, limit = calculate_memory_percent(stats)
        # 512 MB / 1024 MB = 50%
        assert percent == 50.0
        assert used == 536870912
        assert limit == 1073741824

    def test_calculate_memory_percent_full(self):
        """Test avec mémoire pleine."""
        stats = {"memory_stats": {"usage": 1073741824, "limit": 1073741824}}

        percent, used, limit = calculate_memory_percent(stats)
        assert percent == 100.0
        assert used == 1073741824
        assert limit == 1073741824

    def test_calculate_memory_percent_zero_limit(self):
        """Test avec limite à zéro (évite division par zéro)."""
        stats = {"memory_stats": {"usage": 536870912, "limit": 0}}

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

    def test_calculate_memory_percent_cgroups_v1_stats_cache(self):
        """Test cgroups v1 avec cache dans memory_stats.stats.cache."""
        stats = {
            "memory_stats": {
                "usage": 536870912,  # 512 MB
                "limit": 1073741824,  # 1 GB
                "stats": {"cache": 134217728},  # 128 MB
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        # used = 512 MB - 128 MB = 384 MB
        # percent = 384 MB / 1024 MB = 37.5%
        assert used == 536870912 - 134217728
        assert percent == 37.5
        assert limit == 1073741824

    def test_calculate_memory_percent_cgroups_v2_inactive_file(self):
        """Test cgroups v2 avec inactive_file au lieu de cache."""
        stats = {
            "memory_stats": {
                "usage": 536870912,  # 512 MB
                "limit": 1073741824,  # 1 GB
                "stats": {
                    # Pas de champ "cache" sous cgroups v2
                    "inactive_file": 134217728  # 128 MB
                },
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        # used = 512 MB - 128 MB = 384 MB
        # percent = 384 MB / 1024 MB = 37.5%
        assert used == 536870912 - 134217728
        assert percent == 37.5
        assert limit == 1073741824

    def test_calculate_memory_percent_cgroups_v2_no_cache_no_inactive_file(self):
        """Test cgroups v2 sans cache ni inactive_file (fallback usage brut)."""
        stats = {
            "memory_stats": {
                "usage": 536870912,
                "limit": 1073741824,
                "stats": {
                    # Ni cache ni inactive_file
                    "pgfault": 12345
                },
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        # cache = 0, used = usage brut
        assert used == 536870912
        assert percent == 50.0

    def test_calculate_memory_percent_cgroups_v1_top_level_cache(self):
        """Test cgroups v1 avec cache au niveau supérieur de memory_stats."""
        stats = {
            "memory_stats": {
                "usage": 536870912,  # 512 MB
                "cache": 268435456,  # 256 MB
                "limit": 1073741824,  # 1 GB
            }
        }

        percent, used, limit = calculate_memory_percent(stats)
        # used = 512 MB - 256 MB = 256 MB
        assert used == 536870912 - 268435456
        assert percent == 25.0


class TestCalculateNetworkIo:
    """Tests pour la fonction calculate_network_io."""

    def test_calculate_network_io_basic(self):
        """Test basique du calcul réseau."""
        stats = {
            "networks": {
                "eth0": {"rx_bytes": 1048576, "tx_bytes": 2097152}  # 1 MB  # 2 MB
            }
        }

        rx, tx = calculate_network_io(stats)
        assert rx == 1048576
        assert tx == 2097152

    def test_calculate_network_io_multiple_interfaces(self):
        """Test avec plusieurs interfaces réseau."""
        stats = {
            "networks": {
                "eth0": {"rx_bytes": 1000000, "tx_bytes": 2000000},
                "eth1": {"rx_bytes": 500000, "tx_bytes": 300000},
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
                    {"op": "write", "value": 262144},
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
        stats = {"blkio_stats": {"io_service_bytes_recursive": []}}
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 0
        assert write_bytes == 0

    def test_calculate_block_io_none(self):
        """Test avec io_service_bytes_recursive à None."""
        stats = {"blkio_stats": {"io_service_bytes_recursive": None}}
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 0
        assert write_bytes == 0

    def test_calculate_block_io_cgroups_v2_all_null(self):
        """Test cgroups v2 avec tous les champs blkio à None."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": None,
                "io_serviced_recursive": None,
                "io_queue_recursive": None,
                "io_service_time_recursive": None,
                "io_wait_time_recursive": None,
                "io_merged_recursive": None,
                "io_time_recursive": None,
                "sectors_recursive": None,
            }
        }
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 0
        assert write_bytes == 0

    def test_calculate_block_io_throttle_service_bytes_fallback(self):
        """Test fallback vers throttle_io_service_bytes_recursive (en bytes)."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": None,
                "throttle_io_service_bytes_recursive": [
                    {"op": "read", "value": 4096},
                    {"op": "write", "value": 8192},
                ],
            }
        }
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 4096
        assert write_bytes == 8192

    def test_calculate_block_io_primary_takes_precedence_over_fallback(self):
        """Test que io_service_bytes_recursive a priorité sur le fallback."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "read", "value": 1000},
                    {"op": "write", "value": 2000},
                ],
                "throttle_io_service_bytes_recursive": [
                    {"op": "read", "value": 9999},
                    {"op": "write", "value": 9999},
                ],
            }
        }
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 1000
        assert write_bytes == 2000

    def test_calculate_block_io_uppercase_ops(self):
        """Test avec les opérations en majuscules (format Docker variable)."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "Read", "value": 1024},
                    {"op": "Write", "value": 2048},
                    {"op": "Sync", "value": 512},
                    {"op": "Async", "value": 256},
                    {"op": "Total", "value": 3840},
                ]
            }
        }
        read_bytes, write_bytes = calculate_block_io(stats)
        assert read_bytes == 1024
        assert write_bytes == 2048


class TestSumBlkioEntries:
    """Tests pour la fonction helper _sum_blkio_entries."""

    def test_sum_blkio_entries_none(self):
        """Test avec None."""
        assert _sum_blkio_entries(None) == (0, 0)

    def test_sum_blkio_entries_empty(self):
        """Test avec liste vide."""
        assert _sum_blkio_entries([]) == (0, 0)

    def test_sum_blkio_entries_basic(self):
        """Test basique."""
        entries = [
            {"op": "read", "value": 100},
            {"op": "write", "value": 200},
        ]
        assert _sum_blkio_entries(entries) == (100, 200)

    def test_sum_blkio_entries_invalid_entries(self):
        """Test avec des entrées invalides (non-dict)."""
        entries = [None, "invalid", 42, {"op": "read", "value": 100}]
        assert _sum_blkio_entries(entries) == (100, 0)

    def test_sum_blkio_entries_missing_value(self):
        """Test avec value manquante ou None."""
        entries = [
            {"op": "read"},
            {"op": "write", "value": None},
        ]
        assert _sum_blkio_entries(entries) == (0, 0)


class TestFormatStatsResponse:
    """Tests pour la fonction format_stats_response."""

    def test_format_stats_response_complete(self):
        """Test avec des stats complètes."""
        container_id = "abc123"
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 2000000000},
                "system_cpu_usage": 4000000000,
                "online_cpus": 2,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 1000000000},
                "system_cpu_usage": 2000000000,
                "online_cpus": 2,
            },
            "memory_stats": {"usage": 536870912, "limit": 1073741824},
            "networks": {"eth0": {"rx_bytes": 1000000, "tx_bytes": 2000000}},
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"op": "read", "value": 500000},
                    {"op": "write", "value": 300000},
                ]
            },
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
