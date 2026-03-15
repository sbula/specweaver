"""Module with high cyclomatic complexity — triggers C901.

DO NOT SIMPLIFY — this is a test fixture for integration tests.
"""


def overly_complex(x: int) -> str:  # noqa: C901 — deliberately complex for testing
    """Classify a number with too many branches.

    This function has cyclomatic complexity > 10 by design.
    """
    if x == 0:
        return "zero"
    elif x == 1:
        return "one"
    elif x == 2:
        return "two"
    elif x == 3:
        return "three"
    elif x == 4:
        return "four"
    elif x == 5:
        return "five"
    elif x == 6:
        return "six"
    elif x == 7:
        return "seven"
    elif x == 8:
        return "eight"
    elif x == 9:
        return "nine"
    elif x == 10:
        return "ten"
    elif x < 0:
        return "negative"
    return "large"
