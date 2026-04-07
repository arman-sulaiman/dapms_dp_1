from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.core.security import role_required
from app.db import get_db
from app.managers import TeacherManager

bp = Blueprint('teacher', __name__)


def _manager() -> TeacherManager:
    return TeacherManager(get_db())


@bp.route('/dashboard')
@role_required('teacher')
def dashboard():
    return render_template('teacher/dashboard.html', sections=_manager().dashboard_sections(session.get('user_id')), archived_sections=_manager().archived_sections(session.get('user_id')))


@bp.route('/section/<int:section_id>')
@role_required('teacher')
def section_page(section_id):
    data = _manager().get_section_page_data(section_id, session.get('user_id'), request.args.get('q', '').strip())
    return render_template('teacher/section_page.html', **data)


@bp.route('/section/<int:section_id>/enroll', methods=['POST'])
@role_required('teacher')
def enroll_student(section_id):
    try:
        enrolled = _manager().enroll_student_by_student_id(section_id, request.form['student_id'])
        flash('Student enrolled' if enrolled else 'Student not found', 'success' if enrolled else 'error')
    except Exception as exc:
        flash(str(exc) or 'Student already enrolled', 'error')
    return redirect(url_for('teacher.section_page', section_id=section_id))


@bp.route('/section/<int:section_id>/assignment/create', methods=['GET', 'POST'])
@role_required('teacher')
def create_assignment(section_id):
    if request.method == 'POST':
        _manager().create_assignment(section_id, request.form, request.files.get('file'), current_app.config['UPLOAD_FOLDER'])
        flash('Assignment posted', 'success')
        return redirect(url_for('teacher.section_page', section_id=section_id))
    return render_template('teacher/create_assignment.html', section_id=section_id)


@bp.route('/assignment/<int:assessment_id>/edit', methods=['GET', 'POST'])
@role_required('teacher')
def edit_assignment(assessment_id):
    manager = _manager()
    assignment = manager.get_assessment(assessment_id)
    if request.method == 'POST':
        manager.update_assignment(assessment_id, request.form, request.files.get('file'), current_app.config['UPLOAD_FOLDER'])
        flash('Assignment updated', 'success')
        return redirect(url_for('teacher.section_page', section_id=assignment.section_id))
    return render_template('teacher/edit_assignment.html', assignment=assignment)


@bp.route('/assignment/<int:assessment_id>/delete', methods=['POST'])
@role_required('teacher')
def delete_assignment(assessment_id):
    manager = _manager()
    assignment = manager.get_assessment(assessment_id)
    manager.delete_assignment(assessment_id)
    flash('Assignment deleted', 'success')
    return redirect(url_for('teacher.section_page', section_id=assignment.section_id))


@bp.route('/assignment/<int:assessment_id>/scores', methods=['GET', 'POST'])
@role_required('teacher')
def assignment_scores(assessment_id):
    manager = _manager()
    assessment = manager.get_assessment(assessment_id)
    if request.method == 'POST':
        manager.save_assessment_score(assessment_id, int(request.form['enrollment_id']), float(request.form['marks'] or 0), request.form.get('remarks', ''))
        flash('Marks saved', 'success')
        return redirect(url_for('teacher.assignment_scores', assessment_id=assessment_id))
    rows = manager.assessment_score_rows(assessment)
    return render_template('teacher/assignment_scores.html', assessment=assessment.to_dict(), rows=rows)


@bp.route('/section/<int:section_id>/attendance/create', methods=['GET', 'POST'])
@role_required('teacher')
def create_attendance(section_id):
    manager = _manager()
    if request.method == 'POST':
        statuses = {int(key.split('_')[1]): value for key, value in request.form.items() if key.startswith('status_')}
        manager.create_attendance(section_id, int(request.form['class_no']), request.form['class_date'], statuses)
        flash('Attendance saved', 'success')
        return redirect(url_for('teacher.section_page', section_id=section_id))
    return render_template('teacher/create_attendance.html', students=manager.get_students_by_section(section_id), section_id=section_id)


@bp.route('/section/<int:section_id>/announcement/create', methods=['POST'])
@role_required('teacher')
def create_announcement(section_id):
    _manager().create_announcement(section_id, request.form['title'], request.form['body'])
    flash('Announcement posted', 'success')
    return redirect(url_for('teacher.section_page', section_id=section_id))


@bp.route('/section/<int:section_id>/material/create', methods=['POST'])
@role_required('teacher')
def create_material(section_id):
    _manager().create_material(section_id, request.form['heading'], request.form.get('body', ''), request.files.get('file'), current_app.config['UPLOAD_FOLDER'])
    flash('Material uploaded', 'success')
    return redirect(url_for('teacher.section_page', section_id=section_id))


@bp.route('/section/<int:section_id>/components/defaults', methods=['POST'])
@role_required('teacher')
def seed_components(section_id):
    _manager().ensure_default_components(section_id)
    flash('Default marking components created', 'success')
    return redirect(url_for('teacher.section_page', section_id=section_id))


@bp.route('/section/<int:section_id>/components/add', methods=['POST'])
@role_required('teacher')
def add_component(section_id):
    _manager().add_component(section_id, request.form['name'], float(request.form['weight']), float(request.form['max_marks']))
    flash('Marking component added', 'success')
    return redirect(url_for('teacher.section_page', section_id=section_id))


@bp.route('/component/<int:component_id>/scores', methods=['GET', 'POST'])
@role_required('teacher')
def component_scores(component_id):
    manager = _manager()
    rows = manager.component_score_rows(component_id)
    if request.method == 'POST':
        marks_map = {int(k.split('_')[1]): float(v or 0) for k, v in request.form.items() if k.startswith('marks_')}
        manager.save_component_scores(component_id, marks_map)
        flash('Component marks updated', 'success')
        return redirect(url_for('teacher.component_scores', component_id=component_id))
    component = rows[0] if rows else None
    return render_template('teacher/component_scores.html', rows=rows, component=component)


@bp.route('/section/<int:section_id>/results/submit', methods=['POST'])
@role_required('teacher')
def submit_results(section_id):
    _manager().submit_results_for_approval(section_id)
    flash('Results submitted to admin for approval', 'success')
    return redirect(url_for('teacher.section_page', section_id=section_id))

@bp.route('/section/<int:section_id>/attendance-report')
@role_required('teacher')
def attendance_report(section_id):
    data = _manager().get_attendance_report_data(section_id, session.get('user_id'))
    return render_template('teacher/attendance_report.html', **data)