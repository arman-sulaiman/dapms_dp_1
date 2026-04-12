from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Iterable, Optional


@dataclass
class BaseModel:


    row_fields: ClassVar[tuple[str, ...]] = tuple()

    @classmethod
    def from_row(cls, row: Any):
        if row is None:
            return None
        if hasattr(row, 'keys'):
            data = {key: row[key] for key in row.keys() if key in cls.row_fields}
            return cls(**data)
        if isinstance(row, dict):
            data = {key: row[key] for key in cls.row_fields if key in row}
            return cls(**data)
        raise TypeError(f'Unsupported row type for {cls.__name__}: {type(row)!r}')

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def update(self, **kwargs: Any):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self
