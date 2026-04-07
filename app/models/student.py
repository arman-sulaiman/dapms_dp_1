from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .user import User


@dataclass
class Student(User):
    row_fields: ClassVar[tuple[str, ...]] = User.row_fields + ('student_id', 'admission_term')

    student_id: str = ''
    admission_term: str = ''
    role: str = 'student'

    @property
    def default_password(self) -> str:
        return 'student123'

    def view_dashboard(self) -> dict:
        return {'student_id': self.student_id, 'name': self.name, 'role': self.role}
