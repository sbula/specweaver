"""Utility functions for the greeter module."""


def format_greeting(greeting: str, *, uppercase: bool = False) -> str:
    """Format a greeting string.

    Args:
        greeting: The greeting to format.
        uppercase: If True, convert to uppercase.

    Returns:
        Formatted greeting.
    """
    result = greeting.strip()
    if uppercase:
        return result.upper()
    return result


def is_supported_locale(locale: str) -> bool:
    """Check if a locale is supported.

    Args:
        locale: Language code to check.

    Returns:
        True if the locale has a greeting template.
    """
    supported = {"en", "de", "fr"}
    return locale.lower() in supported
