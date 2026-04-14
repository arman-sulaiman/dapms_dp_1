from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.core.security import role_required
from app.db import get_db
from app.managers import StudentManager

bp = Blueprint('student', __name__)


def _manager() -> StudentManager:
    return StudentManager(get_db())


@bp.route('/dashboard')
@role_required('student')
def dashboard():
    manager = _manager()
    return render_template(
        'student/dashboard.html',
        courses=manager.dashboard_courses(session.get('user_id')),
        archived_courses=manager.archived_courses(session.get('user_id')),
        current_term_total_credit=manager.current_term_total_credit(session.get('user_id'))
    )


@bp.route('/course/<int:section_id>')
@role_required('student')
def course_page(section_id):
    return render_template(
        'student/course_page.html',
        **_manager().get_course_page_data(section_id, session.get('user_id'))
    )


@bp.route('/assignment/<int:assessment_id>/submit', methods=['POST'])
@role_required('student')
def submit_assignment(assessment_id):
    manager = _manager()
    assessment = manager.get_assessment(assessment_id)

    if not assessment or not assessment.can_submit:
        flash('Submission not allowed', 'error')
        return redirect(request.referrer or url_for('student.dashboard'))

    enrollment = manager.get_enrollment(assessment.section_id, session.get('user_id'))
    if not enrollment:
        flash('Enrollment not found.', 'error')
        return redirect(url_for('student.dashboard'))

    submitted, message = manager.submit_assignment(
        assessment,
        enrollment['id'],
        request.files.get('file'),
        current_app.config['UPLOAD_FOLDER'],
        request.form.get('student_note', '')
    )

    flash(message, 'success' if submitted else 'error')
    return redirect(url_for('student.course_page', section_id=assessment.section_id))


@bp.route('/results')
@role_required('student')
def results():
    course_rows, term_rows, cgpa, total_credits = _manager().build_results(session.get('user_id'))
    return render_template(
        'student/results.html',
        course_rows=course_rows,
        term_rows=term_rows,
        cgpa=cgpa,
        total_credits=total_credits
    )
    
@bp.route('/course/<int:section_id>/performance')
@role_required('student')
def performance(section_id):
    return render_template(
        'student/performance.html',
        **_manager().get_performance_data(section_id, session.get('user_id'))
    )