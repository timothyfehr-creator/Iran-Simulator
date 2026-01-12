"""
Secret management for API keys.

Usage:
    from src.config.secrets import get_openai_key, get_anthropic_key

    # Will raise if key is missing
    key = get_openai_key()

CLI check:
    python -m src.config.secrets --check
"""

import os
import sys
from pathlib import Path

# Load .env file on module import
try:
    from dotenv import load_dotenv

    # Find .env file - walk up from this file to repo root
    _current = Path(__file__).resolve()
    _repo_root = _current.parent.parent.parent  # src/config/secrets.py -> repo root
    _env_path = _repo_root / ".env"

    if _env_path.exists():
        load_dotenv(_env_path)
    else:
        # Also try current working directory
        load_dotenv()

except ImportError:
    # python-dotenv not installed - env vars must be set externally
    pass


class MissingAPIKeyError(Exception):
    """Raised when a required API key is not configured."""
    pass


def get_openai_key() -> str:
    """
    Get OpenAI API key from environment.

    Returns:
        str: The API key

    Raises:
        MissingAPIKeyError: If OPENAI_API_KEY is not set
    """
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError(
            "OPENAI_API_KEY not found. "
            "Copy .env.example to .env and add your key."
        )
    return key


def get_anthropic_key() -> str:
    """
    Get Anthropic API key from environment.

    Returns:
        str: The API key

    Raises:
        MissingAPIKeyError: If ANTHROPIC_API_KEY is not set
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY not found. "
            "Copy .env.example to .env and add your key."
        )
    return key


def check_keys() -> dict:
    """
    Check which API keys are configured.

    Returns:
        dict: Status of each key ("OK" or "MISSING")
    """
    status = {}

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    status["OPENAI_API_KEY"] = "OK" if openai_key else "MISSING"

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    status["ANTHROPIC_API_KEY"] = "OK" if anthropic_key else "MISSING"

    return status


def _cli_check():
    """CLI entry point for --check flag."""
    status = check_keys()
    all_ok = True

    for key_name, key_status in status.items():
        print(f"{key_name}: {key_status}")
        if key_status == "MISSING":
            all_ok = False

    if not all_ok:
        print("\nTo configure keys:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your API keys to .env")
        sys.exit(1)
    else:
        print("\nAll keys configured.")
        sys.exit(0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Check API key configuration"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if API keys are configured"
    )

    args = parser.parse_args()

    if args.check:
        _cli_check()
    else:
        parser.print_help()
