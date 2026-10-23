"""Hygiène de journalisation SQL — BUG-004 (rules 40, non-régression).

Verrouille les deux niveaux de la défense en profondeur :

1. **Runtime** : pendant l'exécution de tout test, la fixture autouse
   ``_silence_sqlalchemy_engine`` (``tests/conftest.py``) maintient le
   logger ``sqlalchemy.engine`` à WARNING — ses émissions INFO (SQL avec
   paramètres bindés) ne peuvent donc fuir dans ``caplog``.
2. **Structurel** : ``app/main.py`` ne doit plus contenir le
   ``setLevel(getattr(logging, settings.log_level))`` inconditionnel
   (qui activait la fuite à ``LOG_LEVEL=INFO``, défaut du Settings et
   valeur documentée ``.env.prod.example``) mais le bridage
   WARNING-sauf-DEBUG (pattern d'introspection de source
   ``test_lifespan_wiring_and_existing_loops_preserved``).
"""

import logging
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def test_sqlalchemy_engine_bridged_to_warning_during_tests():
    """La fixture autouse est effective : pendant tout test, les loggers
    qui échappent le SQL bindé (``sqlalchemy.engine`` à INFO, ``aiosqlite``
    à DEBUG — sink adjacent découvert en validation) sont à WARNING
    (T2 — herméticité caplog, indépendamment du cwd et du ``LOG_LEVEL``
    local)."""
    for name in ("sqlalchemy.engine", "aiosqlite"):
        assert logging.getLogger(name).level == logging.WARNING, name


def test_main_bridges_sqlalchemy_engine_unless_debug():
    """Garde-fou structurel (T3) : ``main.py`` bride ``sqlalchemy.engine``
    à WARNING sauf ``LOG_LEVEL=DEBUG`` — le positionnement inconditionnel
    au niveau Settings (fuite à INFO) ne doit pas réapparaître."""
    source = (BACKEND_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    # Le bridage inconditionnel fautif est absent…
    assert "setLevel(getattr(logging, settings.log_level))" not in source
    # …et le bridage conditionnel WARNING-sauf-DEBUG est présent.
    assert (
        'logging.getLogger("sqlalchemy.engine").setLevel(\n'
        '    logging.DEBUG if settings.log_level == "DEBUG" else logging.WARNING\n'
        ")" in source
    )
