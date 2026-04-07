from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from .base import BaseModel


@dataclass
class Section(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = (
        'id', 'section_no', 'room_no', 'schedule', 'term_id', 'course_id', 'teacher_user_id'
    )

    id: int | None = None
    section_no: str = ''
    room_no: str = ''
    schedule: str = ''
    term_id: int | None = None
    course_id: int | None = None
    teacher_user_id: int | None = None
    students: list = field(default_factory=list, repr=False)

    def add_student(self, student) -> None:
        self.students.append(student)

    def get_roster(self):
        return list(self.students)
