from __future__ import annotations

from werkzeug.security import generate_password_hash

from app.models import User


class AuthManager:
    def __init__(self, db):
        self.db = db

    def find_user_by_email(self, email: str):
        row = self.db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        return User.from_row(row)

    def find_user_by_id(self, user_id: int):
        row = self.db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        return User.from_row(row)

    def authenticate(self, email: str, password: str):
        user = self.find_user_by_email(email)
        if user and user.check_password(password):
            return user
        return None

    def change_password(self, user_id: int, current_password: str, new_password: str) -> tuple[bool, str]:
        user = self.find_user_by_id(user_id)
        if not user:
            return False, 'User not found.'
        if not user.check_password(current_password):
            return False, 'Current password is incorrect.'
        if len(new_password or '') < 6:
            return False, 'New password must be at least 6 characters.'
        user.set_password(new_password)
        self.db.execute('UPDATE users SET password_hash=? WHERE id=?', (user.password_hash, user_id))
        self.db.commit()
        return True, 'Password updated successfully.'

    def request_password_reset(self, email: str, note: str = '') -> tuple[bool, str]:
        row = self.db.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
        if not row:
            return False, 'No account found with that email.'
        self.db.execute('INSERT INTO password_reset_requests(user_email,note,status) VALUES(?,?,?)', (email, note, 'pending'))
        self.db.commit()
        return True, 'Password reset request submitted. Please contact admin.'

    def user_profile(self, user_id: int):
        return self.db.execute('''
            SELECT users.*, students.student_id, teachers.teacher_id, admins.admin_id, admins.role_name
            FROM users
            LEFT JOIN students ON students.user_id = users.id
            LEFT JOIN teachers ON teachers.user_id = users.id
            LEFT JOIN admins ON admins.user_id = users.id
            WHERE users.id=?
        ''', (user_id,)).fetchone()

    def update_profile(self, user_id: int, name: str, department: str):
        self.db.execute('UPDATE users SET name=?, department=? WHERE id=?', (name, department, user_id))
        self.db.commit()

    def admin_reset_password(self, user_id: int, new_password: str):
        self.db.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(new_password), user_id))
        self.db.commit()
