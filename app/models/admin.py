from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .user import User


@dataclass
class Admin(User):
    row_fields: ClassVar[tuple[str, ...]] = User.row_fields + ('admin_id', 'role_name')

    admin_id: str = ''
    role_name: str = 'Admin'
    role: str = 'admin'

    def create_term_payload(
        self,
        name: str,
        start_date: str,
        end_date: str,
        status: str = 'running',
        *,
        semester: str = '',
        year: str = '',
    ) -> dict:
        return {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'status': status,
            'semester': semester,
            'year': int(year) if str(year).isdigit() else None,
        }
