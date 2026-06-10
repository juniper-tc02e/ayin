"""Column type helpers."""

import enum

from sqlalchemy import Enum


def str_enum(e: type[enum.Enum]) -> Enum:
    """VARCHAR + CHECK constraint (no native PG enum): additive value changes
    stay simple migrations. Values (not names) are stored."""
    return Enum(
        e,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda x: [m.value for m in x],
        length=32,
    )
