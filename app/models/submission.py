from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .base import BaseModel


@dataclass
class Submission(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = ('id', 'assessment_id', 'enrollment_id', 'file_name', 'submitted_at')

    id: int | None = None
    assessment_id: int | None = None
    enrollment_id: int | None = None
    file_name: str = ''
    submitted_at: str = ''
