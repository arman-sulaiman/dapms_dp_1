from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass
class Result(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = ('result_id', 'total_marks', 'grade', 'grade_point', 'published')

    result_id: int | None = None
    total_marks: float = 0.0
    grade: str = ''
    grade_point: float = 0.0
    published: bool = False
