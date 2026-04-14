from __future__ import annotations

import os
from werkzeug.utils import secure_filename

from app.models import Assessment
from app.services.results import (
    build_student_results,
    ensure_component_scores,
    recalculate_section_results,
)


class StudentManager:
    def __init__(self, db):
        self.db = db

    def dashboard_courses(self, student_user_id: int):
        return self.db.execute('''
            SELECT
                sections.id as section_id,
                courses.course_code,
                courses.title,
                sections.section_no,
                terms.name as term_name,
                COALESCE(att.present_count, 0) as present_count,
                COALESCE(att.total_count, 0) as total_count,
                CASE
                    WHEN COALESCE(att.total_count, 0) = 0 THEN 0
                    ELSE ROUND((att.present_count * 100.0) / att.total_count, 2)
                END as attendance_percentage
            FROM enrollments
            JOIN sections ON sections.id = enrollments.section_id
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = enrollments.term_id
            LEFT JOIN (
                SELECT
                    e.id as enrollment_id,
                    SUM(CASE WHEN ae.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                    COUNT(ae.id) as total_count
                FROM enrollments e
                LEFT JOIN attendance_entries ae ON ae.enrollment_id = e.id
                GROUP BY e.id
            ) att ON att.enrollment_id = enrollments.id
            WHERE enrollments.student_user_id = ?
              AND terms.status = 'running'
            ORDER BY terms.year DESC, terms.id DESC, courses.course_code
        ''', (student_user_id,)).fetchall()

    def archived_courses(self, student_user_id: int):
        return self.db.execute('''
            SELECT
                sections.id as section_id,
                courses.course_code,
                courses.title,
                sections.section_no,
                terms.name as term_name,
                terms.status as term_status,
                COALESCE(att.present_count, 0) as present_count,
                COALESCE(att.total_count, 0) as total_count,
                CASE
                    WHEN COALESCE(att.total_count, 0) = 0 THEN 0
                    ELSE ROUND((att.present_count * 100.0) / att.total_count, 2)
                END as attendance_percentage
            FROM enrollments
            JOIN sections ON sections.id = enrollments.section_id
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = enrollments.term_id
            LEFT JOIN (
                SELECT
                    e.id as enrollment_id,
                    SUM(CASE WHEN ae.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                    COUNT(ae.id) as total_count
                FROM enrollments e
                LEFT JOIN attendance_entries ae ON ae.enrollment_id = e.id
                GROUP BY e.id
            ) att ON att.enrollment_id = enrollments.id
            WHERE enrollments.student_user_id = ?
              AND terms.status <> 'running'
            ORDER BY terms.year DESC, terms.id DESC, courses.course_code
        ''', (student_user_id,)).fetchall()

    def current_term_total_credit(self, student_user_id: int):
        row = self.db.execute('''
            SELECT COALESCE(SUM(courses.credit), 0) AS total_credit
            FROM enrollments
            JOIN sections ON sections.id = enrollments.section_id
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = enrollments.term_id
            WHERE enrollments.student_user_id = ?
              AND terms.status = 'running'
        ''', (student_user_id,)).fetchone()

        return row['total_credit'] if row else 0

    def get_course_page_data(self, section_id: int, student_user_id: int) -> dict:
        recalculate_section_results(self.db, section_id)

        section = self.db.execute('''
            SELECT
                sections.*,
                courses.course_code,
                courses.title,
                courses.credit,
                terms.name as term_name,
                users.name as teacher_name
            FROM sections
            JOIN courses ON courses.id = sections.course_id
            JOIN terms ON terms.id = sections.term_id
            JOIN users ON users.id = sections.teacher_user_id
            JOIN enrollments ON enrollments.section_id = sections.id
            WHERE sections.id = ?
              AND enrollments.student_user_id = ?
        ''', (section_id, student_user_id)).fetchone()

        assessments = self.db.execute('''
            SELECT
                assessments.*,
                submissions.id as submission_id,
                submissions.file_name,
                submissions.student_note,
                submissions.submitted_at,
                assessment_scores.marks,
                CASE
                    WHEN submissions.id IS NOT NULL THEN 'Submitted'
                    ELSE 'Pending'
                END AS submission_status
            FROM assessments
            LEFT JOIN enrollments
                ON enrollments.section_id = assessments.section_id
               AND enrollments.student_user_id = ?
            LEFT JOIN submissions
                ON submissions.assessment_id = assessments.id
               AND submissions.enrollment_id = enrollments.id
            LEFT JOIN assessment_scores
                ON assessment_scores.assessment_id = assessments.id
               AND assessment_scores.enrollment_id = enrollments.id
            WHERE assessments.section_id = ?
            ORDER BY assessments.id DESC
        ''', (student_user_id, section_id)).fetchall()

        posts = self.db.execute(
            'SELECT * FROM announcements WHERE section_id = ? ORDER BY id DESC',
            (section_id,)
        ).fetchall()

        attendance = self.db.execute('''
            SELECT
                attendance_sessions.class_no,
                attendance_sessions.class_date,
                attendance_entries.status
            FROM attendance_entries
            JOIN attendance_sessions ON attendance_sessions.id = attendance_entries.session_id
            JOIN enrollments ON enrollments.id = attendance_entries.enrollment_id
            WHERE enrollments.student_user_id = ?
              AND enrollments.section_id = ?
            ORDER BY attendance_sessions.class_no
        ''', (student_user_id, section_id)).fetchall()

        materials = self.db.execute(
            'SELECT * FROM materials WHERE section_id = ? ORDER BY id DESC',
            (section_id,)
        ).fetchall()

        enrollment = self.get_enrollment(section_id, student_user_id)
        components = []
        result = None

        if enrollment:
            ensure_component_scores(self.db, section_id)
            components = self.db.execute('''
                SELECT
                    gc.*,
                    COALESCE(cs.marks, 0) as marks
                FROM grading_components gc
                LEFT JOIN component_scores cs
                    ON cs.component_id = gc.id
                   AND cs.enrollment_id = ?
                WHERE gc.section_id = ?
                ORDER BY gc.sort_order, gc.id
            ''', (enrollment['id'], section_id)).fetchall()

            result = self.db.execute(
                'SELECT * FROM results WHERE section_id = ? AND enrollment_id = ?',
                (section_id, enrollment['id'])
            ).fetchone()

        return {
            'section': section,
            'assessments': assessments,
            'posts': posts,
            'attendance': attendance,
            'materials': materials,
            'components': components,
            'result': result
        }

    def get_assessment(self, assessment_id: int):
        row = self.db.execute('SELECT * FROM assessments WHERE id = ?', (assessment_id,)).fetchone()
        return Assessment.from_row(row)

    def get_enrollment(self, section_id: int, student_user_id: int):
        return self.db.execute(
            'SELECT id FROM enrollments WHERE section_id = ? AND student_user_id = ?',
            (section_id, student_user_id)
        ).fetchone()

    def submit_assignment(self, assessment: Assessment, enrollment_id: int, uploaded_file, upload_folder: str, student_note: str = '') -> tuple[bool, str]:
        if not assessment.can_submit:
            return False, 'Submission not allowed.'

        if assessment.is_overdue:
            return False, 'Submission deadline is over.'

        filename = ''
        existing = self.db.execute(
            'SELECT file_name FROM submissions WHERE assessment_id = ? AND enrollment_id = ?',
            (assessment.id, enrollment_id)
        ).fetchone()

        if existing:
            filename = existing['file_name']

        if uploaded_file and uploaded_file.filename:
            safe_name = secure_filename(uploaded_file.filename)
            filename = f"{enrollment_id}_{assessment.id}_{safe_name}"
            uploaded_file.save(os.path.join(upload_folder, filename))
        elif assessment.file_required and not filename:
            return False, 'File is required for this assignment.'

        self.db.execute(
            '''
            INSERT OR REPLACE INTO submissions
            (id, assessment_id, enrollment_id, file_name, student_note, submitted_at)
            VALUES (
                (SELECT id FROM submissions WHERE assessment_id = ? AND enrollment_id = ?),
                ?, ?, ?, ?, datetime("now")
            )
            ''',
            (assessment.id, enrollment_id, assessment.id, enrollment_id, filename, student_note)
        )
        self.db.commit()

        return True, 'Assignment submitted successfully.'

    def build_results(self, student_user_id: int):
        return build_student_results(self.db, student_user_id)

    def get_performance_data(self, section_id: int, student_user_id: int) -> dict:
        data = self.get_course_page_data(section_id, student_user_id)

        attendance = data.get('attendance', [])
        assessments = data.get('assessments', [])
        components = data.get('components', [])

        total_classes = len(attendance)
        present_classes = len([a for a in attendance if a['status'] == 'Present'])
        attendance_percentage = round((present_classes * 100 / total_classes), 2) if total_classes > 0 else 0

        total_assignments = len(assessments)
        submitted_assignments = len([a for a in assessments if a['submission_status'] == 'Submitted'])
        assignment_submission_percentage = round((submitted_assignments * 100 / total_assignments), 2) if total_assignments > 0 else 0

        assignment_marks_obtained = sum(float(a['marks']) for a in assessments if a['marks'] is not None)
        assignment_marks_total = sum(float(a['total_marks']) for a in assessments if a['marks'] is not None)
        assignment_marks_percentage = round((assignment_marks_obtained * 100 / assignment_marks_total), 2) if assignment_marks_total > 0 else 0

        component_marks_obtained = sum(float(c['marks']) for c in components if c['marks'] is not None)
        component_marks_total = sum(float(c['max_marks']) for c in components if c['marks'] is not None)
        component_marks_percentage = round((component_marks_obtained * 100 / component_marks_total), 2) if component_marks_total > 0 else 0

        scores_for_average = [attendance_percentage, assignment_submission_percentage]

        if assignment_marks_total > 0:
            scores_for_average.append(assignment_marks_percentage)

        if component_marks_total > 0:
            scores_for_average.append(component_marks_percentage)

        overall_score = round(sum(scores_for_average) / len(scores_for_average), 2) if scores_for_average else 0

        advice = []

        if attendance_percentage < 75:
            advice.append('Your attendance is below a safe level. Attend classes more regularly to improve both learning and attendance-based marks.')

        if assignment_submission_percentage < 80:
            advice.append('You have missing or late assignment submissions. Try to submit every assignment on time.')

        if assignment_marks_total > 0 and assignment_marks_percentage < 60:
            advice.append('Your assignment marks are low. Review feedback carefully and improve preparation before the next submission.')

        if component_marks_total > 0 and component_marks_percentage < 60:
            advice.append('Your assessments marks are below average. Focus more on quizzes, assignments, lab tasks/presentation, or other course assessments.')

        if not advice:
            advice.append('Your performance is in a good position. Stay consistent and maintain this progress.')

        return {
            **data,
            'performance': {
                'present_classes': present_classes,
                'total_classes': total_classes,
                'attendance_percentage': attendance_percentage,
                'submitted_assignments': submitted_assignments,
                'total_assignments': total_assignments,
                'assignment_submission_percentage': assignment_submission_percentage,
                'assignment_marks_obtained': round(assignment_marks_obtained, 2),
                'assignment_marks_total': round(assignment_marks_total, 2),
                'assignment_marks_percentage': assignment_marks_percentage,
                'component_marks_obtained': round(component_marks_obtained, 2),
                'component_marks_total': round(component_marks_total, 2),
                'component_marks_percentage': component_marks_percentage,
                'overall_score': overall_score,
                'advice': advice,
            }
        }