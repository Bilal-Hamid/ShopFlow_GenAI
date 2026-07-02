import enum


def enum_values(obj: type[enum.Enum]) -> list[str]:
    """Use each member's string .value (not its .name) as the Postgres enum label."""
    return [member.value for member in obj]
