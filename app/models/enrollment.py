from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass
class Enrollment(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = ('id', 'section_id', 'student_user_id', 'term_id')

    id: int | None = None
    section_id: int | None = None
    student_user_id: int | None = None
    term_id: int | None = None
