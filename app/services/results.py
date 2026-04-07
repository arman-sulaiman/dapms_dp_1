from collections import OrderedDict

from app.core.grading import get_grade


def calculate_attendance_marks(db, section_id: int, enrollment_id: int) -> float:
    total_classes = db.execute('SELECT COUNT(*) c FROM attendance_sessions WHERE section_id=?', (section_id,)).fetchone()['c']
    if not total_classes:
        return 0.0
    present = db.execute('''
        SELECT COUNT(*) c
        FROM attendance_entries
        JOIN attendance_sessions ON attendance_sessions.id = attendance_entries.session_id
        WHERE attendance_sessions.section_id=? AND attendance_entries.enrollment_id=? AND attendance_entries.status='Present'
    ''', (section_id, enrollment_id)).fetchone()['c']
    return round((present / total_classes) * 10, 2)


def ensure_component_scores(db, section_id: int):
    components = db.execute('SELECT * FROM grading_components WHERE section_id=? ORDER BY sort_order, id', (section_id,)).fetchall()
    enrollments = db.execute('SELECT id FROM enrollments WHERE section_id=?', (section_id,)).fetchall()
    for comp in components:
        for enroll in enrollments:
            marks = 0.0
            if comp['category'] == 'attendance':
                marks = calculate_attendance_marks(db, section_id, enroll['id'])
            db.execute(
                'INSERT OR IGNORE INTO component_scores(component_id,enrollment_id,marks,remarks) VALUES(?,?,?,?)',
                (comp['id'], enroll['id'], marks, '')
            )
            if comp['category'] == 'attendance':
                db.execute('UPDATE component_scores SET marks=? WHERE component_id=? AND enrollment_id=?', (marks, comp['id'], enroll['id']))
    db.commit()


def recalculate_section_results(db, section_id: int):
    ensure_component_scores(db, section_id)
    rows = db.execute('''
        SELECT enrollments.id as enrollment_id, components.id as component_id, components.weight, components.max_marks,
               COALESCE(scores.marks, 0) as marks
        FROM enrollments
        CROSS JOIN grading_components as components
        LEFT JOIN component_scores as scores ON scores.component_id = components.id AND scores.enrollment_id = enrollments.id
        WHERE enrollments.section_id=? AND components.section_id=?
        ORDER BY enrollments.id, components.sort_order, components.id
    ''', (section_id, section_id)).fetchall()
    by_enrollment = OrderedDict()
    for row in rows:
        bucket = by_enrollment.setdefault(row['enrollment_id'], 0.0)
        if row['max_marks'] > 0:
            bucket += (row['marks'] / row['max_marks']) * row['weight']
        by_enrollment[row['enrollment_id']] = bucket
    for enrollment_id, total in by_enrollment.items():
        total = round(total, 2)
        letter, gp = get_grade(total)
        db.execute(
            'INSERT INTO results(section_id,enrollment_id,total,letter_grade,grade_point) VALUES(?,?,?,?,?) '
            'ON CONFLICT(section_id, enrollment_id) DO UPDATE SET total=excluded.total, letter_grade=excluded.letter_grade, grade_point=excluded.grade_point',
            (section_id, enrollment_id, total, letter, gp)
        )
    db.commit()


def build_student_results(db, student_user_id):
    enrollments = db.execute(
        '''
        SELECT enrollments.id as enrollment_id, terms.id as term_id, terms.name as term_name,
               courses.course_code, courses.title, courses.credit, sections.id as section_id,
               COALESCE(results.total, 0) as total, results.letter_grade, COALESCE(results.grade_point, 0) as grade_point,
               COALESCE(results.status, 'draft') as result_status
        FROM enrollments
        JOIN sections ON sections.id = enrollments.section_id
        JOIN terms ON terms.id = enrollments.term_id
        JOIN courses ON courses.id = sections.course_id
        LEFT JOIN results ON results.enrollment_id = enrollments.id AND results.section_id = sections.id
        WHERE enrollments.student_user_id = ?
        ORDER BY terms.year, terms.id, courses.course_code
        ''',
        (student_user_id,)
    ).fetchall()
    course_rows = []
    term_map = OrderedDict()
    total_points = 0.0
    total_credits = 0.0
    for e in enrollments:
        visible = e['result_status'] in ('approved', 'published')
        gp = e['grade_point'] if visible else None
        total = e['total'] if visible else None
        letter = e['letter_grade'] if visible else 'Pending'
        course_rows.append({
            'term_name': e['term_name'], 'course_code': e['course_code'], 'title': e['title'], 'credit': e['credit'],
            'total': total, 'grade': letter, 'gp': gp, 'status': e['result_status']
        })
        if visible and gp is not None:
            term = term_map.setdefault(e['term_name'], {'credits': 0.0, 'points': 0.0})
            term['credits'] += e['credit']
            term['points'] += e['credit'] * gp
            total_credits += e['credit']
            total_points += e['credit'] * gp
    term_rows = []
    for term_name, info in term_map.items():
        term_rows.append({'term_name': term_name, 'credits': info['credits'], 'gpa': round(info['points'] / info['credits'], 2) if info['credits'] else 0})
    cgpa = round(total_points / total_credits, 2) if total_credits else 0
    return course_rows, term_rows, cgpa, total_credits
