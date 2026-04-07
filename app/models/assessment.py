from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from .base import BaseModel


@dataclass
class Assessment(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = (
        'id', 'section_id', 'type', 'title', 'percentage', 'total_marks', 'due_date', 'allow_submission', 'require_file', 'description', 'teacher_file_name', 'topic', 'posted_at'
    )

    id: int | None = None
    section_id: int | None = None
    type: str = ''
    title: str = ''
    percentage: float = 0.0
    total_marks: float = 0.0
    due_date: str = ''
    allow_submission: int = 0
    require_file: int = 0
    description: str = ''
    teacher_file_name: str = ''
    topic: str = ''
    posted_at: str = ''

    @property
    def can_submit(self) -> bool:
        return self.allow_submission == 1

    @property
    def file_required(self) -> bool:
        return self.require_file == 1

    @property
    def is_overdue(self) -> bool:
        if not self.due_date:
            return False
        try:
            due = datetime.strptime(self.due_date, '%Y-%m-%d')
            return datetime.now() > due
        except ValueError:
            return False

    def score_to_percentage(self, marks: float) -> float:
        if self.total_marks <= 0:
            return 0.0
        return (marks / self.total_marks) * self.percentage
