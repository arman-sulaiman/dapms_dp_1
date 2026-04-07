from __future__ import annotations

import os
from werkzeug.utils import secure_filename

from app.models import Assessment
from app.services.results import ensure_component_scores, recalculate_section_results


THEORY_DEFAULTS = [
    ('Quiz', 10, 10, 'manual'),
    ('Attendance', 5, 5, 'attendance'),
    ('Mid', 25, 25, 'manual'),
    ('Final', 40, 40, 'manual'),
    ('Presentation', 5, 5, 'manual'),
    ('Assignment', 5, 5, 'manual'),
]

LAB_DEFAULTS = [
    ('Lab Test', 20, 20, 'manual'),
    ('Lab Performance', 20, 20, 'manual'),
    ('Final', 30, 30, 'manual'),
    ('Project/Open-Ended', 30, 30, 'manual'),
]


class TeacherManager:
    def __init__(self, db):
        self.db = db

    def dashboard_sections(self, teacher_user_id: int):
        return self.db.execute(
            '''
            SELECT sections.*, courses.course_code, courses.title, courses.credit,
                   terms.name as term_name, terms.status as term_status
            FROM sections
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = sections.term_id
            WHERE sections.teacher_user_id=? AND terms.status='running'
            ORDER BY terms.year DESC, terms.id DESC, sections.id DESC
            ''',
            (teacher_user_id,)
        ).fetchall()

    def archived_sections(self, teacher_user_id: int):
        return self.db.execute(
            '''
            SELECT sections.*, courses.course_code, courses.title, courses.credit,
                   terms.name as term_name, terms.status as term_status
            FROM sections
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = sections.term_id
            WHERE sections.teacher_user_id=? AND terms.status<>'running'
            ORDER BY terms.year DESC, terms.id DESC, sections.id DESC
            ''',
            (teacher_user_id,)
        ).fetchall()

    def _section_detail(self, section_id: int, teacher_user_id: int):
        return self.db.execute(
            '''
            SELECT sections.*, courses.course_code, courses.title, courses.credit, terms.name as term_name
            FROM sections
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = sections.term_id
            WHERE sections.id=? AND sections.teacher_user_id=?
            ''',
            (section_id, teacher_user_id)
        ).fetchone()

    def get_section_page_data(self, section_id: int, teacher_user_id: int, student_q: str = '') -> dict:
        section = self._section_detail(section_id, teacher_user_id)

        sql = '''
            SELECT users.name, users.email, students.student_id, enrollments.id as enrollment_id
            FROM enrollments
            JOIN users ON users.id = enrollments.student_user_id
            JOIN students ON students.user_id = users.id
            WHERE enrollments.section_id=?
        '''
        params = [section_id]

        if student_q:
            sql += ' AND (users.name LIKE ? OR students.student_id LIKE ? OR users.email LIKE ?)'
            term = f'%{student_q}%'
            params.extend([term, term, term])

        sql += ' ORDER BY users.name'
        students = self.db.execute(sql, tuple(params)).fetchall()

        assessments = self.db.execute(
            '''
            SELECT assessments.*,
                   (SELECT COUNT(*) FROM submissions WHERE submissions.assessment_id = assessments.id) AS submitted_count,
                   (SELECT COUNT(*) FROM enrollments WHERE enrollments.section_id = assessments.section_id) AS total_students
            FROM assessments
            WHERE section_id=?
            ORDER BY id DESC
            ''',
            (section_id,)
        ).fetchall()

        posts = self.db.execute(
            'SELECT * FROM announcements WHERE section_id=? ORDER BY id DESC',
            (section_id,)
        ).fetchall()

        sessions = self.db.execute(
            'SELECT * FROM attendance_sessions WHERE section_id=? ORDER BY class_no DESC',
            (section_id,)
        ).fetchall()

        materials = self.db.execute(
            'SELECT * FROM materials WHERE section_id=? ORDER BY id DESC',
            (section_id,)
        ).fetchall()

        components = self.list_components(section_id)
        marks_summary = self.section_marks_summary(section_id)
        result_state = self.section_result_state(section_id)

        return {
            'section': section,
            'students': students,
            'assessments': assessments,
            'posts': posts,
            'sessions': sessions,
            'materials': materials,
            'components': components,
            'marks_summary': marks_summary,
            'result_state': result_state,
            'student_q': student_q,
        }

    def enroll_student_by_student_id(self, section_id: int, student_id: str) -> bool:
        row = self.db.execute(
            '''
            SELECT users.id as user_id, sections.term_id
            FROM users
            JOIN students ON students.user_id = users.id
            JOIN sections ON sections.id = ?
            WHERE students.student_id = ?
            ''',
            (section_id, student_id)
        ).fetchone()

        if not row:
            return False

        self.db.execute(
            'INSERT INTO enrollments(section_id,student_user_id,term_id) VALUES(?,?,?)',
            (section_id, row['user_id'], row['term_id'])
        )
        self.db.commit()
        ensure_component_scores(self.db, section_id)
        return True

    def create_assignment(self, section_id: int, form, uploaded_file, upload_folder: str):
        filename = ''
        if uploaded_file and uploaded_file.filename:
            safe = secure_filename(uploaded_file.filename)
            filename = f'assignment_{section_id}_{safe}'
            uploaded_file.save(os.path.join(upload_folder, filename))

        self.db.execute(
            '''
            INSERT INTO assessments(
                section_id, type, title, percentage, total_marks, due_date,
                allow_submission, require_file, description, teacher_file_name,
                topic, posted_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,datetime("now"))
            ''',
            (
                section_id,
                'Assignment',
                form['title'],
                0,
                float(form.get('total_marks', 100) or 100),
                form.get('due_date', ''),
                1,
                1 if form.get('require_file') == 'on' else 0,
                form.get('description', ''),
                filename,
                form.get('topic', '')
            )
        )
        self.db.commit()

    def update_assignment(self, assessment_id: int, form, uploaded_file, upload_folder: str):
        current = self.get_assessment(assessment_id)
        filename = current.teacher_file_name if current else ''

        if uploaded_file and uploaded_file.filename:
            safe = secure_filename(uploaded_file.filename)
            filename = f'assignment_{current.section_id}_{assessment_id}_{safe}'
            uploaded_file.save(os.path.join(upload_folder, filename))

        self.db.execute(
            '''
            UPDATE assessments
            SET title=?, total_marks=?, due_date=?, require_file=?, description=?, teacher_file_name=?, topic=?
            WHERE id=?
            ''',
            (
                form['title'],
                float(form.get('total_marks', 100) or 100),
                form.get('due_date', ''),
                1 if form.get('require_file') == 'on' else 0,
                form.get('description', ''),
                filename,
                form.get('topic', ''),
                assessment_id
            )
        )
        self.db.commit()

    def delete_assignment(self, assessment_id: int):
        self.db.execute('DELETE FROM assessments WHERE id=?', (assessment_id,))
        self.db.commit()

    def get_assessment(self, assessment_id: int):
        row = self.db.execute('SELECT * FROM assessments WHERE id=?', (assessment_id,)).fetchone()
        return Assessment.from_row(row)

    def assessment_score_rows(self, assessment: Assessment):
        return self.db.execute(
            '''
            SELECT enrollments.id as enrollment_id, users.name, students.student_id,
                   COALESCE(assessment_scores.marks, 0) as marks,
                   assessment_scores.remarks,
                   submissions.file_name,
                   submissions.student_note,
                   submissions.submitted_at
            FROM enrollments
            JOIN users ON users.id = enrollments.student_user_id
            JOIN students ON students.user_id = users.id
            LEFT JOIN assessment_scores
                ON assessment_scores.enrollment_id = enrollments.id
               AND assessment_scores.assessment_id = ?
            LEFT JOIN submissions
                ON submissions.enrollment_id = enrollments.id
               AND submissions.assessment_id = ?
            WHERE enrollments.section_id = ?
            ORDER BY users.name
            ''',
            (assessment.id, assessment.id, assessment.section_id)
        ).fetchall()

    def save_assessment_score(self, assessment_id: int, enrollment_id: int, marks: float, remarks: str = '') -> None:
        self.db.execute(
            '''
            INSERT INTO assessment_scores(assessment_id,enrollment_id,marks,remarks)
            VALUES(?,?,?,?)
            ON CONFLICT(assessment_id, enrollment_id)
            DO UPDATE SET marks=excluded.marks, remarks=excluded.remarks
            ''',
            (assessment_id, enrollment_id, marks, remarks)
        )
        self.db.commit()

    def create_attendance(self, section_id: int, class_no: int, class_date: str, statuses: dict[int, str]) -> None:
        self.db.execute(
            'INSERT INTO attendance_sessions(section_id,class_no,class_date) VALUES(?,?,?)',
            (section_id, class_no, class_date)
        )
        session_id = self.db.execute('SELECT last_insert_rowid() id').fetchone()['id']

        enrollments = self.db.execute(
            'SELECT id FROM enrollments WHERE section_id=?',
            (section_id,)
        ).fetchall()

        for enrollment in enrollments:
            self.db.execute(
                'INSERT INTO attendance_entries(session_id,enrollment_id,status) VALUES(?,?,?)',
                (session_id, enrollment['id'], statuses.get(enrollment['id'], 'Absent'))
            )

        self.db.commit()
        ensure_component_scores(self.db, section_id)
        recalculate_section_results(self.db, section_id)

    def get_students_by_section(self, section_id: int):
        return self.db.execute(
            '''
            SELECT enrollments.id as enrollment_id, users.name, students.student_id
            FROM enrollments
            JOIN users ON users.id = enrollments.student_user_id
            JOIN students ON students.user_id = users.id
            WHERE enrollments.section_id=?
            ORDER BY students.student_id
            ''',
            (section_id,)
        ).fetchall()

    def create_announcement(self, section_id: int, title: str, body: str) -> None:
        self.db.execute(
            'INSERT INTO announcements(section_id,title,body,created_at) VALUES(?,?,?,datetime("now"))',
            (section_id, title, body)
        )
        self.db.commit()

    def create_material(self, section_id: int, heading: str, body: str, uploaded_file, upload_folder: str):
        filename = ''
        if uploaded_file and uploaded_file.filename:
            safe = secure_filename(uploaded_file.filename)
            filename = f'material_{section_id}_{safe}'
            uploaded_file.save(os.path.join(upload_folder, filename))

        self.db.execute(
            'INSERT INTO materials(section_id,heading,body,file_name,created_at) VALUES(?,?,?,?,datetime("now"))',
            (section_id, heading, body, filename)
        )
        self.db.commit()

    def ensure_default_components(self, section_id: int):
        section = self.db.execute(
            '''
            SELECT courses.credit
            FROM sections
            JOIN courses ON courses.id=sections.course_id
            WHERE sections.id=?
            ''',
            (section_id,)
        ).fetchone()

        defaults = THEORY_DEFAULTS if section and int(section['credit']) == 3 else LAB_DEFAULTS

        existing = self.db.execute(
            'SELECT COUNT(*) c FROM grading_components WHERE section_id=?',
            (section_id,)
        ).fetchone()['c']

        if existing:
            return

        for idx, (name, weight, max_marks, category) in enumerate(defaults, start=1):
            self.db.execute(
                '''
                INSERT INTO grading_components(
                    section_id,name,weight,max_marks,category,auto_generated,sort_order
                ) VALUES(?,?,?,?,?,?,?)
                ''',
                (
                    section_id,
                    name,
                    weight,
                    max_marks,
                    category,
                    1 if category == 'attendance' else 0,
                    idx
                )
            )

        self.db.commit()
        ensure_component_scores(self.db, section_id)
        recalculate_section_results(self.db, section_id)

    def list_components(self, section_id: int):
        ensure_component_scores(self.db, section_id)
        return self.db.execute(
            'SELECT * FROM grading_components WHERE section_id=? ORDER BY sort_order, id',
            (section_id,)
        ).fetchall()

    def add_component(self, section_id: int, name: str, weight: float, max_marks: float):
        sort_order = self.db.execute(
            'SELECT COALESCE(MAX(sort_order),0)+1 as n FROM grading_components WHERE section_id=?',
            (section_id,)
        ).fetchone()['n']

        self.db.execute(
            '''
            INSERT INTO grading_components(
                section_id,name,weight,max_marks,category,auto_generated,sort_order
            ) VALUES(?,?,?,?,?,?,?)
            ''',
            (section_id, name, weight, max_marks, 'manual', 0, sort_order)
        )
        self.db.commit()
        ensure_component_scores(self.db, section_id)

    def save_component_scores(self, component_id: int, marks_map: dict[int, float]):
        section_id = self.db.execute(
            'SELECT section_id FROM grading_components WHERE id=?',
            (component_id,)
        ).fetchone()['section_id']

        for enrollment_id, marks in marks_map.items():
            self.db.execute(
                '''
                INSERT INTO component_scores(component_id,enrollment_id,marks)
                VALUES(?,?,?)
                ON CONFLICT(component_id, enrollment_id)
                DO UPDATE SET marks=excluded.marks
                ''',
                (component_id, enrollment_id, marks)
            )

        self.db.commit()
        recalculate_section_results(self.db, section_id)

    def component_score_rows(self, component_id: int):
        return self.db.execute(
            '''
            SELECT c.*, e.id as enrollment_id, u.name, s.student_id, COALESCE(cs.marks, 0) as marks
            FROM grading_components c
            JOIN sections sec ON sec.id = c.section_id
            JOIN enrollments e ON e.section_id = sec.id
            JOIN users u ON u.id = e.student_user_id
            JOIN students s ON s.user_id = u.id
            LEFT JOIN component_scores cs ON cs.component_id = c.id AND cs.enrollment_id = e.id
            WHERE c.id=?
            ORDER BY s.student_id
            ''',
            (component_id,)
        ).fetchall()

    def section_marks_summary(self, section_id: int):
        recalculate_section_results(self.db, section_id)
        return self.db.execute(
            '''
            SELECT results.*, users.name, students.student_id
            FROM results
            JOIN enrollments ON enrollments.id = results.enrollment_id
            JOIN users ON users.id = enrollments.student_user_id
            JOIN students ON students.user_id = users.id
            WHERE results.section_id=?
            ORDER BY students.student_id
            ''',
            (section_id,)
        ).fetchall()

    def section_result_state(self, section_id: int):
        components = self.db.execute(
            'SELECT COALESCE(SUM(weight),0) as total_weight FROM grading_components WHERE section_id=?',
            (section_id,)
        ).fetchone()

        state = self.db.execute(
            'SELECT status, COUNT(*) c FROM results WHERE section_id=? GROUP BY status ORDER BY c DESC LIMIT 1',
            (section_id,)
        ).fetchone()

        return {
            'total_weight': components['total_weight'] if components else 0,
            'status': state['status'] if state else 'draft'
        }

    def submit_results_for_approval(self, section_id: int):
        recalculate_section_results(self.db, section_id)
        self.db.execute(
            "UPDATE results SET status='submitted', teacher_submitted_at=datetime('now') WHERE section_id=?",
            (section_id,)
        )
        self.db.commit()

    def get_attendance_report_data(self, section_id: int, teacher_user_id: int):
        recalculate_section_results(self.db, section_id)

        section = self.db.execute(
            '''
            SELECT sections.*, courses.course_code, courses.title,
                   terms.name as term_name, users.name as teacher_name
            FROM sections
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = sections.term_id
            JOIN users ON users.id = sections.teacher_user_id
            WHERE sections.id=? AND sections.teacher_user_id=?
            ''',
            (section_id, teacher_user_id)
        ).fetchone()

        students = self.db.execute(
            '''
            SELECT enrollments.id as enrollment_id, users.name, students.student_id
            FROM enrollments
            JOIN users ON users.id = enrollments.student_user_id
            JOIN students ON students.user_id = users.id
            WHERE enrollments.section_id=?
            ORDER BY students.student_id
            ''',
            (section_id,)
        ).fetchall()

        class_dates = self.db.execute(
            '''
            SELECT id as session_id, class_date, class_no
            FROM attendance_sessions
            WHERE section_id=?
            ORDER BY class_no, class_date
            ''',
            (section_id,)
        ).fetchall()

        entries = self.db.execute(
            '''
            SELECT attendance_entries.enrollment_id,
                   attendance_entries.session_id,
                   attendance_entries.status
            FROM attendance_entries
            JOIN attendance_sessions
                ON attendance_sessions.id = attendance_entries.session_id
            WHERE attendance_sessions.section_id=?
            ''',
            (section_id,)
        ).fetchall()

        attendance_map = {}
        for e in entries:
            attendance_map[(e['enrollment_id'], e['session_id'])] = 'P' if e['status'] == 'Present' else 'A'

        summary_map = {}
        total_classes = len(class_dates)

        for s in students:
            present = 0
            absent = 0

            for d in class_dates:
                st = attendance_map.get((s['enrollment_id'], d['session_id']))
                if st == 'P':
                    present += 1
                elif st == 'A':
                    absent += 1

            percentage = round((present * 100 / total_classes), 2) if total_classes > 0 else 0

            summary_map[s['enrollment_id']] = {
                'present': present,
                'absent': absent,
                'percentage': percentage
            }

        return {
            'section': section,
            'students': students,
            'class_dates': class_dates,
            'attendance_map': attendance_map,
            'summary_map': summary_map
        }