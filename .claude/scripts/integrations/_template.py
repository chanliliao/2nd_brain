"""
Integration Template
====================

Copy this file and rename it to your integration name (e.g., 'gmail.py', 'github.py').
Then fill in the TODO sections to implement your specific integration.

This template provides the structure and interface expected by the integration registry.
Each integration should:
  1. Define a config dataclass that loads from environment variables
  2. Implement authentication
  3. Provide query functions to fetch/search data
  4. Format context for the second brain
  5. Support CLI dispatch for manual testing

Module naming convention: Use the integration name in lowercase (gmail, github, gcal, etc.)
"""

import sys
import os
from dataclasses import dataclass
from typing import Optional, Any, List
from datetime import datetime

from dotenv import load_dotenv


# ============================================================================
# CONFIG DATACLASS
# ============================================================================

@dataclass
class IntegrationConfig:
    """
    Configuration for the integration.

    TODO: Rename this class to match your integration (e.g., GmailConfig, GithubConfig).
    TODO: Add fields for credentials, API endpoints, or other config.
    TODO: Each field should map to an environment variable.

    Example:
      client_id: str
      client_secret: str
      refresh_token: Optional[str] = None
    """

    # TODO: Add your config fields here
    pass

    @classmethod
    def from_env(cls) -> "IntegrationConfig":
        """
        Load configuration from environment variables using python-dotenv.

        This method is called by the registry to instantiate your config.
        Make sure to load the .env file first:
          from dotenv import load_dotenv
          load_dotenv()

        TODO: Implement this to read your specific env vars and instantiate the config.

        Returns:
          IntegrationConfig instance with values from environment.

        Raises:
          ValueError: If required environment variables are missing.

        Example implementation:
          load_dotenv()
          client_id = os.getenv("MY_CLIENT_ID")
          if not client_id:
              raise ValueError("MY_CLIENT_ID environment variable is required")
          return cls(client_id=client_id, ...)
        """
        # TODO: Implement env var loading
        load_dotenv()
        return cls()


# ============================================================================
# AUTHENTICATION
# ============================================================================

def auth(config: IntegrationConfig) -> None:
    """
    Authenticate with the integration service.

    This function should handle:
      - OAuth2 flows (redirecting user to login URL, exchanging code for token)
      - API key validation
      - Token refresh logic
      - Saving credentials back to .env or secure storage

    TODO: Implement authentication for your integration.

    Args:
      config: IntegrationConfig instance with necessary credentials.

    Raises:
      Exception: If authentication fails (include helpful error message).

    Example OAuth2 flow:
      1. Generate auth URL with state parameter
      2. Print URL for user to visit
      3. Wait for callback (via local HTTP server or manual code entry)
      4. Exchange code for access token
      5. Test the token with a simple API call
      6. Save tokens to config/env
    """
    raise NotImplementedError(
        "Authentication not yet implemented for this integration. "
        "See the docstring above for guidance on implementing OAuth2 or API key auth."
    )


# ============================================================================
# QUERY FUNCTIONS
# ============================================================================

def list_items(config: IntegrationConfig, since: Optional[datetime] = None) -> List[Any]:
    """
    Fetch a list of items from the integration.

    This function should retrieve all relevant data items from the service.
    For large result sets, consider pagination.

    TODO: Implement item listing for your integration.

    Args:
      config: IntegrationConfig instance.
      since: Optional datetime to fetch only items modified/created after this time.
             If None, fetch all items (or recent items if service limits apply).

    Returns:
      List of item objects/dicts. Structure depends on the service.
      Example: [{"id": "msg123", "subject": "Hello", "from": "user@example.com"}, ...]

    Raises:
      NotImplementedError: This is a stub.

    Example implementations:
      - Gmail: Fetch recent emails with query filtering
      - GitHub: Fetch issues/PRs for user's repos
      - Google Calendar: Fetch upcoming events
    """
    raise NotImplementedError(
        "list_items() not implemented for this integration. "
        "Implement this method to fetch items from the service API."
    )


def get_item(config: IntegrationConfig, item_id: str) -> Any:
    """
    Fetch a single item by ID.

    TODO: Implement item fetching by ID for your integration.

    Args:
      config: IntegrationConfig instance.
      item_id: Unique identifier for the item (service-specific format).

    Returns:
      Item object/dict with full details.

    Raises:
      NotImplementedError: This is a stub.
      ValueError: If item_id is invalid or item not found.

    Example:
      - Gmail: Fetch full email message by message ID
      - GitHub: Fetch full issue/PR details by number
      - Google Calendar: Fetch full event details by event ID
    """
    raise NotImplementedError(
        f"get_item() not implemented for this integration. "
        f"Requested item ID: {item_id}"
    )


def needs_action(config: IntegrationConfig, item: Any) -> bool:
    """
    Determine if an item requires action (for prioritization/filtering).

    This function helps filter items into "needs attention" vs "informational".
    Used by the second brain to highlight urgent items.

    TODO: Implement action detection for your integration.

    Args:
      config: IntegrationConfig instance.
      item: Item object/dict from list_items() or get_item().

    Returns:
      True if the item needs user action, False otherwise.

    Example heuristics:
      - Gmail: Unread emails, emails marked as flagged
      - GitHub: Open issues assigned to you, PRs awaiting your review
      - Google Calendar: Events happening soon that aren't confirmed
    """
    raise NotImplementedError(
        "needs_action() not implemented for this integration. "
        "Implement logic to determine if an item requires user attention."
    )


# ============================================================================
# FORMATTING FOR CONTEXT
# ============================================================================

def format_context(items: List[Any]) -> str:
    """
    Convert a list of items into plain-text context for the second brain.

    This function formats items into a readable, consumable format that can be
    included in Claude prompts or stored as context. The output should be:
      - Plain text (no special formatting)
      - Structured but readable
      - Concise but informative
      - Easy to parse and search

    TODO: Implement formatting for your integration's items.

    Args:
      items: List of item objects/dicts from list_items() or similar.

    Returns:
      Plain-text string representation suitable for prompts/storage.

    Example output:
      ```
      EMAIL #1: From: alice@example.com, Subject: Project Update
        Date: 2024-04-23T10:30:00Z
        Unread: Yes
        Preview: We've completed the Phase 4 design...

      EMAIL #2: From: bob@example.com, Subject: Review Request
        Date: 2024-04-23T09:15:00Z
        Unread: No
        Preview: Please review the attached proposal...
      ```
    """
    raise NotImplementedError(
        "format_context() not implemented for this integration. "
        "Implement this to format items into readable, prompt-friendly text."
    )


# ============================================================================
# CLI DISPATCH
# ============================================================================

def cli_dispatch(args: List[str]) -> None:
    """
    Command-line dispatch for manual testing and interaction.

    This function handles subcommands for testing the integration from the command line.
    Typical subcommands:
      - auth: Run authentication flow
      - list: Fetch and display items
      - get <id>: Fetch and display single item
      - format: Fetch items and show formatted output

    TODO: Implement CLI dispatch for your integration.

    Args:
      args: Command-line arguments (sys.argv[1:]).
            First element is the subcommand, rest are subcommand args.

    Example usage:
      python gmail.py auth              # Run OAuth2 flow
      python gmail.py list              # List recent emails
      python gmail.py list --since 7d   # List emails from last 7 days
      python gmail.py get msg123        # Get specific email
      python gmail.py format            # Fetch and format all items
    """
    raise NotImplementedError(
        "cli_dispatch() not implemented for this integration. "
        "Implement this to support command-line testing (auth, list, get, format)."
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    """
    Entry point for CLI usage.

    When this file is run directly, dispatch to the appropriate CLI handler
    based on command-line arguments.

    Usage:
      python _template.py <command> [args...]

    To test after renaming:
      python gmail.py auth
      python gmail.py list
    """
    try:
        cli_dispatch(sys.argv[1:])
    except NotImplementedError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
