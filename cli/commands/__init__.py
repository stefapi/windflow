"""
Commandes CLI pour WindFlow.
"""

from cli.commands.auth import handle_auth_command, setup_auth_parser
from cli.commands.config_cmd import handle_config_command, setup_config_parser
from cli.commands.deploy import handle_deploy_command, setup_deploy_parser
from cli.commands.env import handle_env_command, setup_env_parser
from cli.commands.org import handle_org_command, setup_org_parser

__all__ = [
    "setup_auth_parser",
    "handle_auth_command",
    "setup_config_parser",
    "handle_config_command",
    "setup_org_parser",
    "handle_org_command",
    "setup_env_parser",
    "handle_env_command",
    "setup_deploy_parser",
    "handle_deploy_command",
]
