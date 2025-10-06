"""
Utilitaires pour le CLI WindFlow.

Fonctions d'aide pour le formatage, l'affichage et la manipulation des données.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import sys
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import print as rich_print

# Console Rich globale
console = Console()


def format_timestamp(timestamp: str) -> str:
    """Formate un timestamp ISO pour l'affichage."""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, AttributeError):
        return timestamp


def format_json(data: Any, indent: int = 2) -> str:
    """Formate des données en JSON lisible."""
    return json.dumps(data, indent=indent, ensure_ascii=False)


def print_json(data: Any, indent: int = 2) -> None:
    """Affiche des données en JSON formaté."""
    print(format_json(data, indent))


def print_table(headers: List[str], rows: List[List[Any]]) -> None:
    """Affiche des données sous forme de tableau avec Rich."""
    if not rows:
        console.print("[yellow]Aucune donnée à afficher[/yellow]")
        return

    table = Table(show_header=True, header_style="bold cyan")

    # Ajouter les colonnes
    for header in headers:
        table.add_column(header)

    # Ajouter les lignes
    for row in rows:
        table.add_row(*[str(cell) if cell is not None else "" for cell in row])

    console.print(table)


def print_error(message: str) -> None:
    """Affiche un message d'erreur avec Rich."""
    console.print(f"[bold red]✗ Erreur:[/bold red] {message}", style="red")


def print_success(message: str) -> None:
    """Affiche un message de succès avec Rich."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_warning(message: str) -> None:
    """Affiche un message d'avertissement avec Rich."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_info(message: str) -> None:
    """Affiche un message d'information avec Rich."""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def print_panel(content: str, title: str = "", style: str = "cyan") -> None:
    """Affiche un panneau avec Rich."""
    panel = Panel(content, title=title, border_style=style)
    console.print(panel)


def print_json_rich(data: Any) -> None:
    """Affiche du JSON avec coloration syntaxique."""
    json_str = format_json(data)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(syntax)


def create_progress() -> Progress:
    """Crée une barre de progression Rich."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )


def confirm(prompt: str, default: bool = False) -> bool:
    """Demande une confirmation à l'utilisateur."""
    default_str = "O/n" if default else "o/N"
    response = input(f"{prompt} [{default_str}]: ").strip().lower()

    if not response:
        return default

    return response in ('o', 'oui', 'y', 'yes')


def truncate(text: str, max_length: int = 50) -> str:
    """Tronque un texte si nécessaire."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
