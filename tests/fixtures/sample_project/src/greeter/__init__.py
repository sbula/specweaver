"""Greeter module — generates personalized greetings.

Clean module that passes all lint and complexity checks.
Used as the 'good code' fixture for integration tests.
"""

__all__ = ["Greeter", "format_greeting"]

from specweaver_sample.greeter.core import Greeter
from specweaver_sample.greeter.utils import format_greeting
