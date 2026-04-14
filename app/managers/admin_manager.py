from __future__ import annotations

from app.models import Admin, Course, Section, Student, Teacher, Term
from app.services.id_generators import DEPARTMENT_CODES, build_term_name, next_student_id, next_teacher_id


class AdminManager:
    def __init__(self, db):
        self.db = db

    def dashboard_stats(self) -> dict:
        active_term = self.db.execute("SELECT * FROM terms WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
        pending_results = self.db.execute("SELECT COUNT(*) c FROM results WHERE status='submitted'").fetchone()['c']
        pending_resets = self.db.execute("SELECT COUNT(*) c FROM password_reset_requests WHERE status='pending'").fetchone()['c']
        return {
            'students': self.db.execute("SELECT COUNT(*) c FROM users WHERE role='student'").fetchone()['c'],
            'teachers': self.db.execute("SELECT COUNT(*) c FROM users WHERE role='teacher'").fetchone()['c'],
            'courses': self.db.execute('SELECT COUNT(*) c FROM courses').fetchone()['c'],
            'sections': self.db.execute('SELECT COUNT(*) c FROM sections').fetchone()['c'],
            'active_term': active_term,
            'pending_results': pending_results,
            'pending_resets': pending_resets,
        }

    def create_term(self, admin: Admin, year: str, semester: str, start_date: str, end_date: str, status: str = 'running') -> Term:
        name = build_term_name(year, semester)
        payload = admin.create_term_payload(name, start_date, end_date, status=status, semester=semester, year=year)
        if payload['status'] == 'running':
            self.db.execute("UPDATE terms SET status='completed' WHERE status='running'")
        self.db.execute(
            'INSERT INTO terms(name,start_date,end_date,status,semester,year) VALUES(?,?,?,?,?,?)',
            (payload['name'], payload['start_date'], payload['end_date'], payload['status'], payload['semester'], payload['year'])
        )
        self.db.commit()
        term_id = self.db.execute('SELECT last_insert_rowid() id').fetchone()['id']
        return Term(id=term_id, **payload)

    def get_terms(self):
        return self.db.execute('SELECT * FROM terms ORDER BY year DESC, id DESC').fetchall()

    def get_active_terms(self):
        return self.db.execute("SELECT * FROM terms WHERE status IN ('running','upcoming') ORDER BY year DESC, id DESC").fetchall()

    def current_running_term(self):
        return self.db.execute("SELECT * FROM terms WHERE status='running' ORDER BY year DESC, id DESC LIMIT 1").fetchone()

    def update_term_status(self, term_id: int, status: str) -> None:
        if status == 'running':
            self.db.execute("UPDATE terms SET status='completed' WHERE status='running' AND id<>?", (term_id,))
        self.db.execute('UPDATE terms SET status=? WHERE id=?', (status, term_id))
        self.db.commit()

    def complete_term(self, term_id: int) -> None:
        self.db.execute("UPDATE terms SET status='completed' WHERE id=?", (term_id,))
        self.db.commit()

    def create_student(self, student: Student, raw_password: str | None = None, *, year: str, semester: str) -> Student:
        student_id, admission_term = next_student_id(self.db, student.department, year, semester)
        student.student_id = student_id
        student.admission_term = admission_term
        password = raw_password or student.default_password
        student.set_password(password)
        self.db.execute(
            'INSERT INTO users(role,name,email,password_hash,department) VALUES(?,?,?,?,?)',
            ('student', student.name, student.email, student.password_hash, student.department)
        )
        user_id = self.db.execute('SELECT id FROM users WHERE email=?', (student.email,)).fetchone()['id']
        self.db.execute('INSERT INTO students(user_id,student_id,admission_term) VALUES(?,?,?)', (user_id, student.student_id, student.admission_term))
        self.db.commit()
        student.id = user_id
        return student

    def create_teacher(self, teacher: Teacher, raw_password: str | None = None) -> Teacher:
        teacher.teacher_id = next_teacher_id(self.db, teacher.department)
        password = raw_password or teacher.default_password
        teacher.set_password(password)
        self.db.execute(
            'INSERT INTO users(role,name,email,password_hash,department) VALUES(?,?,?,?,?)',
            ('teacher', teacher.name, teacher.email, teacher.password_hash, teacher.department)
        )
        user_id = self.db.execute('SELECT id FROM users WHERE email=?', (teacher.email,)).fetchone()['id']
        self.db.execute('INSERT INTO teachers(user_id,teacher_id) VALUES(?,?)', (user_id, teacher.teacher_id))
        self.db.commit()
        teacher.id = user_id
        return teacher

    def create_course(self, course: Course) -> Course:
        self.db.execute('INSERT INTO courses(course_code,title,credit) VALUES(?,?,?)', (course.course_code, course.title, int(course.credit)))
        self.db.commit()
        course.id = self.db.execute('SELECT last_insert_rowid() id').fetchone()['id']
        return course

    def get_courses(self):
        return self.db.execute('SELECT * FROM courses ORDER BY course_code').fetchall()

    def get_teachers(self):
        return self.db.execute('SELECT users.id, users.name, users.department, teachers.teacher_id FROM users JOIN teachers ON teachers.user_id=users.id ORDER BY users.name').fetchall()

    def create_section(self, section: Section) -> None:
        term = self.db.execute('SELECT status, name FROM terms WHERE id=?', (int(section.term_id),)).fetchone()
        if not term:
            raise ValueError('Selected term not found.')
        if term['status'] == 'completed':
            raise ValueError('Cannot create a section in a completed term.')
        self.db.execute('INSERT INTO sections(section_no,room_no,schedule,term_id,course_id,teacher_user_id) VALUES(?,?,?,?,?,?)', (section.section_no, section.room_no, section.schedule, int(section.term_id), int(section.course_id), int(section.teacher_user_id)))
        self.db.commit()

    def list_students(self):
        return self.db.execute('''SELECT users.id, users.name, users.email, users.department, students.student_id, students.admission_term FROM users JOIN students ON students.user_id=users.id ORDER BY students.student_id''').fetchall()

    def list_teachers(self):
        return self.db.execute('''SELECT users.id, users.name, users.email, users.department, teachers.teacher_id FROM users JOIN teachers ON teachers.user_id=users.id ORDER BY teachers.teacher_id''').fetchall()

    def list_sections(self):
        return self.db.execute('''SELECT sections.id, courses.course_code, courses.title, sections.section_no, terms.name as term_name, terms.status as term_status, users.name as teacher_name FROM sections JOIN courses ON courses.id=sections.course_id JOIN terms ON terms.id=sections.term_id JOIN users ON users.id=sections.teacher_user_id ORDER BY terms.year DESC, terms.id DESC, courses.course_code''').fetchall()

    def pending_result_sections(self):
        return self.db.execute('''SELECT DISTINCT sections.id, courses.course_code, courses.title, sections.section_no, terms.name as term_name, results.status FROM results JOIN sections ON sections.id=results.section_id JOIN courses ON courses.id=sections.course_id JOIN terms ON terms.id=sections.term_id WHERE results.status in ('submitted','approved') ORDER BY terms.id DESC, courses.course_code''').fetchall()

    def result_rows_for_section(self, section_id: int):
        return self.db.execute('''SELECT results.*, users.name, students.student_id FROM results JOIN enrollments ON enrollments.id = results.enrollment_id JOIN users ON users.id = enrollments.student_user_id JOIN students ON students.user_id = users.id WHERE results.section_id=? ORDER BY students.student_id''', (section_id,)).fetchall()

    def approve_section_results(self, section_id: int):
        self.db.execute("UPDATE results SET status='approved', admin_approved_at=datetime('now'), published_at=datetime('now') WHERE section_id=? AND status='submitted'", (section_id,))
        self.db.commit()

    def password_reset_requests(self):
        return self.db.execute('SELECT * FROM password_reset_requests ORDER BY id DESC').fetchall()

    def mark_password_request_done(self, request_id: int):
        self.db.execute("UPDATE password_reset_requests SET status='done' WHERE id=?", (request_id,))
        self.db.commit()

    def all_users(self):
        return self.db.execute('SELECT id, name, email, role, department FROM users ORDER BY role, name').fetchall()


    def pending_result_sections(self):
        return self.db.execute('''
        SELECT DISTINCT
            sections.id,
            courses.course_code,
            courses.title,
            sections.section_no,
            terms.name AS term_name,
            results.status,
            users.name AS teacher_name
        FROM results
        JOIN sections ON sections.id = results.section_id
        JOIN courses ON courses.id = sections.course_id
        JOIN terms ON terms.id = sections.term_id
        JOIN users ON users.id = sections.teacher_user_id
        WHERE results.status IN ('submitted', 'approved')
        ORDER BY terms.year DESC, terms.id DESC, courses.course_code
    ''').fetchall()