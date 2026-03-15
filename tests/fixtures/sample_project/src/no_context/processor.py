"""Record processor — public symbols for inference testing."""

from dataclasses import dataclass


@dataclass
class Record:
    """A data record to process."""

    id: int
    name: str
    value: float


class RecordProcessor:
    """Processes records through a validation pipeline."""

    def validate(self, record: Record) -> bool:
        """Check if a record is valid.

        Args:
            record: The record to validate.

        Returns:
            True if the record passes validation.
        """
        return record.id > 0 and len(record.name) > 0


def summarize(records: list[Record]) -> dict[str, float]:
    """Compute summary statistics for a list of records.

    Args:
        records: Records to summarize.

    Returns:
        Dictionary with 'count', 'total', and 'average' keys.
    """
    if not records:
        return {"count": 0, "total": 0.0, "average": 0.0}

    total = sum(r.value for r in records)
    return {
        "count": float(len(records)),
        "total": total,
        "average": total / len(records),
    }


def _internal_helper() -> None:
    """Private helper — should NOT appear in inferred exposes."""
