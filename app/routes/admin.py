import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.core.security import role_required
from app.db import get_db
from app.managers import AdminManager, AuthManager
from app.models import Admin, Course, Section, Student, Teacher
from app.services.id_generators import DEPARTMENT_CODES, SEMESTER_CODES
from app.services.importers import import_courses, import_students, import_teachers

bp = Blueprint('admin', __name__)


def _manager() -> AdminManager:
    return AdminManager(get_db())


@bp.route('/dashboard')
@role_required('admin')
def dashboard():
    return render_template('admin/dashboard.html', stats=_manager().dashboard_stats())


@bp.route('/terms')
@role_required('admin')
def terms():
    manager = _manager()
    return render_template('admin/terms.html', terms=manager.get_terms(), running_term=manager.current_running_term())


@bp.route('/term/create', methods=['GET', 'POST'])
@role_required('admin')
def create_term():
    if request.method == 'POST':
        _manager().create_term(Admin(), request.form['year'], request.form['semester'], request.form['start_date'], request.form['end_date'], request.form.get('status', 'running'))
        flash('Term created', 'success')
        return redirect(url_for('admin.terms'))
    return render_template('admin/create_term.html', semesters=list(SEMESTER_CODES.keys()))


@bp.route('/term/<int:term_id>/status', methods=['POST'])
@role_required('admin')
def update_term_status(term_id):
    _manager().update_term_status(term_id, request.form['status'])
    flash('Term status updated', 'success')
    return redirect(url_for('admin.terms'))


@bp.route('/student/create', methods=['GET', 'POST'])
@role_required('admin')
def create_student():
    if request.method == 'POST':
        student = Student(name=request.form['name'], email=request.form['email'], department=request.form['department'])
        created = _manager().create_student(student, request.form.get('password'), year=request.form['admission_year'], semester=request.form['admission_semester'])
        flash(f'Student created. Auto Student ID: {created.student_id}', 'success')
        return redirect(url_for('admin.create_student'))
    return render_template('admin/create_student.html', departments=DEPARTMENT_CODES, semesters=list(SEMESTER_CODES.keys()))


@bp.route('/teacher/create', methods=['GET', 'POST'])
@role_required('admin')
def create_teacher():
    if request.method == 'POST':
        teacher = Teacher(name=request.form['name'], email=request.form['email'], department=request.form['department'])
        created = _manager().create_teacher(teacher, request.form.get('password'))
        flash(f'Teacher created. Auto Teacher ID: {created.teacher_id}', 'success')
        return redirect(url_for('admin.create_teacher'))
    return render_template('admin/create_teacher.html', departments=DEPARTMENT_CODES)


@bp.route('/student/upload', methods=['GET', 'POST'])
@role_required('admin')
def upload_students():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            count = import_students(get_db(), path)
            flash(f'{count} students imported', 'success')
            return redirect(url_for('admin.dashboard'))
    return render_template('admin/upload_students.html')


@bp.route('/teacher/upload', methods=['GET', 'POST'])
@role_required('admin')
def upload_teachers():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            count = import_teachers(get_db(), path)
            flash(f'{count} teachers imported', 'success')
            return redirect(url_for('admin.dashboard'))
    return render_template('admin/upload_teachers.html')


@bp.route('/course/create', methods=['GET', 'POST'])
@role_required('admin')
def create_course():
    if request.method == 'POST':
        course = Course(course_code=request.form['course_code'], title=request.form['title'], credit=int(request.form['credit']))
        _manager().create_course(course)
        flash('Course created', 'success')
        return redirect(url_for('admin.create_course'))
    return render_template('admin/create_course.html')


@bp.route('/course/upload', methods=['GET', 'POST'])
@role_required('admin')
def upload_courses():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename:
            path = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            count = import_courses(get_db(), path)
            flash(f'{count} courses imported', 'success')
            return redirect(url_for('admin.dashboard'))
    return render_template('admin/upload_courses.html')


@bp.route('/section/create', methods=['GET', 'POST'])
@role_required('admin')
def create_section():
    manager = _manager()
    if request.method == 'POST':
        section = Section(section_no=request.form['section_no'], room_no=request.form['room_no'], schedule=request.form['schedule'], term_id=int(request.form['term_id']), course_id=int(request.form['course_id']), teacher_user_id=int(request.form['teacher_user_id']))
        try:
            manager.create_section(section)
            flash('Section created', 'success')
        except ValueError as exc:
            flash(str(exc), 'error')
        return redirect(url_for('admin.create_section'))
    return render_template('admin/create_section.html', terms=manager.get_active_terms(), courses=manager.get_courses(), teachers=manager.get_teachers())


@bp.route('/students')
@role_required('admin')
def students():
    return render_template('admin/list_students.html', rows=_manager().list_students())


@bp.route('/teachers')
@role_required('admin')
def teachers():
    return render_template('admin/list_teachers.html', rows=_manager().list_teachers())


@bp.route('/sections')
@role_required('admin')
def sections():
    return render_template('admin/list_sections.html', rows=_manager().list_sections())


@bp.route('/users/<int:user_id>/reset-password', methods=['GET', 'POST'])
@role_required('admin')
def reset_user_password(user_id):
    profile = AuthManager(get_db()).user_profile(user_id)
    if request.method == 'POST':
        AuthManager(get_db()).admin_reset_password(user_id, request.form['new_password'])
        flash('Password reset completed', 'success')
        return redirect(url_for('admin.reset_user_password', user_id=user_id))
    return render_template('admin/reset_password.html', profile=profile)


@bp.route('/password-requests', methods=['GET', 'POST'])
@role_required('admin')
def password_requests():
    manager = _manager()
    if request.method == 'POST':
        manager.mark_password_request_done(int(request.form['request_id']))
        flash('Password reset request marked done', 'success')
        return redirect(url_for('admin.password_requests'))
    return render_template('admin/password_requests.html', rows=manager.password_reset_requests())


@bp.route('/results')
@role_required('admin')
def results():
    return render_template('admin/results.html', rows=_manager().pending_result_sections())


@bp.route('/results/<int:section_id>', methods=['GET', 'POST'])
@role_required('admin')
def result_detail(section_id):
    manager = _manager()
    if request.method == 'POST':
        manager.approve_section_results(section_id)
        flash('Result approved and published', 'success')
        return redirect(url_for('admin.result_detail', section_id=section_id))
    rows = manager.result_rows_for_section(section_id)
    return render_template('admin/result_detail.html', rows=rows, section_id=section_id)
