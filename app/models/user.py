from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from werkzeug.security import check_password_hash, generate_password_hash

from .base import BaseModel


@dataclass
class User(BaseModel):
    row_fields: ClassVar[tuple[str, ...]] = ('id', 'role', 'name', 'email', 'department', 'password_hash')

    id: int | None = None
    role: str = ''
    name: str = ''
    email: str = ''
    department: str = ''
    password_hash: str = field(default='', repr=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def dashboard_endpoint(self) -> str:
        return f'{self.role}.dashboard'

    def update_profile(self, **kwargs):
        allowed = {'name', 'email', 'department'}
        for key, value in kwargs.items():
            if key in allowed:
                setattr(self, key, value)
        return self
