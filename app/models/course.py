from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseModel


@dataclass
class Course(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = ('id', 'course_code', 'title', 'credit')

    id: int | None = None
    course_code: str = ''
    title: str = ''
    credit: int = 0
    sections: list = field(default_factory=list, repr=False)

    def add_section(self, section) -> None:
        self.sections.append(section)
