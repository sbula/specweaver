"""Core greeter logic — clean, typed, documented."""

TEMPLATES: dict[str, str] = {
    "en": "Hello, {name}!",
    "de": "Hallo, {name}!",
    "fr": "Bonjour, {name}!",
}


class Greeter:
    """Generates personalized greetings.

    Attributes:
        locale: Language code for greeting templates.
    """

    def __init__(self, locale: str = "en") -> None:
        self.locale = locale

    def greet(self, name: str) -> str:
        """Generate a greeting for the given name.

        Args:
            name: The person to greet.

        Returns:
            Formatted greeting string.

        Raises:
            ValueError: If name is empty.
        """
        if not name.strip():
            msg = "Name must not be empty"
            raise ValueError(msg)

        template = TEMPLATES.get(self.locale, TEMPLATES["en"])
        return template.format(name=name)
