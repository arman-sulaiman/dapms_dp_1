from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass
class Term(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = ('id', 'name', 'start_date', 'end_date', 'status')

    id: int | None = None
    name: str = ''
    start_date: str = ''
    end_date: str = ''
    status: str = 'running'

    @property
    def is_running(self) -> bool:
        return self.status == 'running'
