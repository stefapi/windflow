"""
Commandes CLI pour WindFlow.
"""

from cli.commands.auth import setup_auth_parser, handle_auth_command
from cli.commands.config_cmd import setup_config_parser, handle_config_command
from cli.commands.org import setup_org_parser, handle_org_command
from cli.commands.env import setup_env_parser, handle_env_command
from cli.commands.deploy import setup_deploy_parser, handle_deploy_command

__all__ = [
    'setup_auth_parser',
    'handle_auth_command',
    'setup_config_parser',
    'handle_config_command',
    'setup_org_parser',
    'handle_org_command',
    'setup_env_parser',
    'handle_env_command',
    'setup_deploy_parser',
    'handle_deploy_command',
]
