from __future__ import annotations

DEPARTMENT_CODES = {
    'CSE': '014',
    'BBA': '011',
    'EEE': '012',
}

SEMESTER_CODES = {
    'Spring': '1',
    'Summer': '2',
    'Fall': '3',
}


def normalize_department(department: str) -> str:
    return (department or '').strip().upper()


def department_code(department: str) -> str:
    department = normalize_department(department)
    return DEPARTMENT_CODES.get(department, '999')


def term_code(year: int | str, semester: str) -> str:
    year_str = str(year).strip()
    if len(year_str) != 4 or not year_str.isdigit():
        raise ValueError('Year must be 4 digits.')
    sem_code = SEMESTER_CODES.get((semester or '').strip().title())
    if not sem_code:
        raise ValueError('Invalid semester.')
    return f"{year_str[-2:]}{sem_code}"


def build_term_name(year: int | str, semester: str) -> str:
    semester = (semester or '').strip().title()
    return f'{semester} {year}'


def next_student_id(db, department: str, year: int | str, semester: str) -> tuple[str, str]:
    term = term_code(year, semester)
    dept_code = department_code(department)
    prefix = f'{term}{dept_code}'
    row = db.execute(
        'SELECT student_id FROM students WHERE student_id LIKE ? ORDER BY student_id DESC LIMIT 1',
        (f'{prefix}%',)
    ).fetchone()
    serial = 1
    if row and row['student_id']:
        serial = int(str(row['student_id'])[-3:]) + 1
    return f'{prefix}{serial:03d}', term


def next_teacher_id(db, department: str) -> str:
    dept_code = department_code(department)
    prefix = f'T{dept_code}'
    row = db.execute(
        'SELECT teacher_id FROM teachers WHERE teacher_id LIKE ? ORDER BY teacher_id DESC LIMIT 1',
        (f'{prefix}%',)
    ).fetchone()
    serial = 1
    if row and row['teacher_id']:
        serial = int(str(row['teacher_id'])[-3:]) + 1
    return f'{prefix}{serial:03d}'
