"""
Integration Registry
====================

Tracks and manages enabled integrations for the second brain system.

The registry maintains a mapping of integration names to their module paths,
allowing dynamic import and instantiation of integrations without hard-coding
them into the application.

Pre-registered integrations (built-in):
  - gmail: Gmail/Google Workspace email integration
  - github: GitHub issues and PRs integration
  - gcal: Google Calendar events integration
"""

import importlib
import sys
import types
from pathlib import Path
from typing import Optional, Dict, List

# Setup sys.path for importable integrations modules
_SCRIPTS_DIR = Path(__file__).parent.parent  # .claude/scripts/
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# Registry: name -> module path
# Format: module paths are relative to the main package for importlib
_REGISTRY: Dict[str, str] = {}


# ============================================================================
# REGISTRY FUNCTIONS
# ============================================================================

def register(name: str, module_path: str) -> None:
    """
    Register an integration in the registry.

    Args:
      name: Human-readable integration name (e.g., 'gmail', 'github').
      module_path: Python module path as string (e.g., 'integrations.gmail').

    Raises:
      ValueError: If an integration with this name is already registered.
    """
    if name in _REGISTRY:
        raise ValueError(
            f"Integration '{name}' is already registered. "
            f"Use a different name."
        )
    _REGISTRY[name] = module_path


def get(name: str) -> Optional[types.ModuleType]:
    """
    Import and return a registered integration module.

    This function dynamically imports the module associated with the given name.
    If the module cannot be found or import fails, returns None gracefully.

    Args:
      name: Integration name (e.g., 'gmail', 'github').

    Returns:
      The imported module object, or None if not found or import failed.

    Example:
      gmail_module = get('gmail')
      if gmail_module:
          config = gmail_module.IntegrationConfig.from_env()
          items = gmail_module.list_items(config)
    """
    if name not in _REGISTRY:
        return None

    module_path = _REGISTRY[name]
    try:
        return importlib.import_module(module_path)
    except (ImportError, ModuleNotFoundError, TypeError):
        return None


def list_registered() -> List[str]:
    """
    Return a sorted list of all registered integration names.

    Returns:
      List of integration names in alphabetical order.
    """
    return sorted(_REGISTRY.keys())


def is_registered(name: str) -> bool:
    """
    Check if an integration is registered.

    Args:
      name: Integration name.

    Returns:
      True if the integration is in the registry, False otherwise.
    """
    return name in _REGISTRY


# ============================================================================
# PRE-REGISTER BUILT-IN INTEGRATIONS
# ============================================================================

# Gmail: Email integration
register("gmail", "integrations.gmail")

# GitHub: Issues and pull requests integration
register("github", "integrations.github")

# Google Calendar: Calendar and events integration (shares OAuth with Gmail)
register("gcal", "integrations.gcal")
