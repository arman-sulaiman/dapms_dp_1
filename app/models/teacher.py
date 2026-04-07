from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .user import User


@dataclass
class Teacher(User):
    row_fields: ClassVar[tuple[str, ...]] = User.row_fields + ('teacher_id',)

    teacher_id: str = ''
    role: str = 'teacher'

    @property
    def default_password(self) -> str:
        return 'teacher123'
