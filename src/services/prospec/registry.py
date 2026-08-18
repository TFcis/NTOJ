from typing import Any


def normalize_problem_type(value: Any):
    """Convert package/database problem type values to ``ProType``."""
    from services.pro import ProType

    if value is None:
        return ProType.BATCH
    if isinstance(value, ProType):
        return value
    if isinstance(value, int):
        return ProType(value)
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "").replace("_", "")
        aliases = {
            "1": ProType.BATCH,
            "batch": ProType.BATCH,
            "2": ProType.COMMUNICATION,
            "communication": ProType.COMMUNICATION,
            "3": ProType.TWOSTEP,
            "twostep": ProType.TWOSTEP,
            "twosteps": ProType.TWOSTEP,
            "4": ProType.OUTPUTONLY,
            "outputonly": ProType.OUTPUTONLY,
        }
        if normalized in aliases:
            return aliases[normalized]
    raise ValueError(f"Invalid problem type: {value!r}")


def get_problem_spec(problem_type):
    """Return the specification singleton for a supported problem type."""
    from services.pro import ProType

    problem_type = normalize_problem_type(problem_type)
    if problem_type == ProType.BATCH:
        from services.prospec.batch import batch_spec

        return batch_spec
    if problem_type == ProType.COMMUNICATION:
        from services.prospec.communication import communication_spec

        return communication_spec
    raise NotImplementedError(f"Problem type {problem_type.name} is not supported")
