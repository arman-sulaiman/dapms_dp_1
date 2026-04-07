import sqlite3
from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _add_column_if_missing(db, table_name: str, column_name: str, column_sql: str):
    columns = [row['name'] for row in db.execute(f'PRAGMA table_info({table_name})').fetchall()]
    if column_name in columns:
        return
    try:
        db.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_sql}')
    except sqlite3.OperationalError as exc:
       
        message = str(exc).lower()
        if 'non-constant default' not in message:
            raise
        safe_sql = column_sql
        if 'DEFAULT CURRENT_TIMESTAMP' in safe_sql:
            safe_sql = safe_sql.replace(' DEFAULT CURRENT_TIMESTAMP', '')
        elif 'default current_timestamp' in safe_sql.lower():
            import re
            safe_sql = re.sub(r'\s+default\s+current_timestamp', '', safe_sql, flags=re.I)
        db.execute(f'ALTER TABLE {table_name} ADD COLUMN {safe_sql}')
        if column_name == 'posted_at':
            db.execute(f"UPDATE {table_name} SET {column_name}=datetime('now') WHERE {column_name} IS NULL OR {column_name}='' ")


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = get_db()
        db.executescript(
            '''
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                department TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admins(
                user_id INTEGER PRIMARY KEY,
                admin_id TEXT NOT NULL UNIQUE,
                role_name TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS teachers(
                user_id INTEGER PRIMARY KEY,
                teacher_id TEXT NOT NULL UNIQUE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS students(
                user_id INTEGER PRIMARY KEY,
                student_id TEXT NOT NULL UNIQUE,
                admission_term TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS terms(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                semester TEXT,
                year INTEGER
            );
            CREATE TABLE IF NOT EXISTS courses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                credit INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sections(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_no TEXT NOT NULL,
                room_no TEXT NOT NULL,
                schedule TEXT NOT NULL,
                term_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                teacher_user_id INTEGER NOT NULL,
                UNIQUE(term_id, course_id, section_no),
                FOREIGN KEY(term_id) REFERENCES terms(id) ON DELETE CASCADE,
                FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
                FOREIGN KEY(teacher_user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS enrollments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                student_user_id INTEGER NOT NULL,
                term_id INTEGER NOT NULL,
                UNIQUE(section_id, student_user_id),
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE,
                FOREIGN KEY(student_user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(term_id) REFERENCES terms(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS assessments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                type TEXT NOT NULL DEFAULT 'Assignment',
                title TEXT NOT NULL,
                percentage REAL NOT NULL DEFAULT 0,
                total_marks REAL NOT NULL DEFAULT 100,
                due_date TEXT,
                allow_submission INTEGER NOT NULL DEFAULT 1,
                require_file INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                teacher_file_name TEXT DEFAULT '',
                topic TEXT DEFAULT '',
                posted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS assessment_scores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER NOT NULL,
                enrollment_id INTEGER NOT NULL,
                marks REAL NOT NULL DEFAULT 0,
                remarks TEXT DEFAULT '',
                UNIQUE(assessment_id, enrollment_id),
                FOREIGN KEY(assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY(enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS submissions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_id INTEGER NOT NULL,
                enrollment_id INTEGER NOT NULL,
                file_name TEXT NOT NULL DEFAULT '',
                student_note TEXT DEFAULT '',
                submitted_at TEXT NOT NULL,
                UNIQUE(assessment_id, enrollment_id),
                FOREIGN KEY(assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
                FOREIGN KEY(enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS attendance_sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                class_no INTEGER NOT NULL,
                class_date TEXT NOT NULL,
                UNIQUE(section_id, class_no),
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS attendance_entries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                enrollment_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(session_id, enrollment_id),
                FOREIGN KEY(session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY(enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS announcements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS materials(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                heading TEXT NOT NULL,
                body TEXT DEFAULT '',
                file_name TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS grading_components(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                weight REAL NOT NULL,
                max_marks REAL NOT NULL DEFAULT 100,
                category TEXT NOT NULL DEFAULT 'manual',
                auto_generated INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE(section_id, name),
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS component_scores(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_id INTEGER NOT NULL,
                enrollment_id INTEGER NOT NULL,
                marks REAL NOT NULL DEFAULT 0,
                remarks TEXT DEFAULT '',
                UNIQUE(component_id, enrollment_id),
                FOREIGN KEY(component_id) REFERENCES grading_components(id) ON DELETE CASCADE,
                FOREIGN KEY(enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS results(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_id INTEGER NOT NULL,
                enrollment_id INTEGER NOT NULL,
                total REAL NOT NULL DEFAULT 0,
                letter_grade TEXT NOT NULL DEFAULT 'F',
                grade_point REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'draft',
                teacher_submitted_at TEXT,
                admin_approved_at TEXT,
                published_at TEXT,
                UNIQUE(section_id, enrollment_id),
                FOREIGN KEY(section_id) REFERENCES sections(id) ON DELETE CASCADE,
                FOREIGN KEY(enrollment_id) REFERENCES enrollments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS password_reset_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                note TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            '''
        )
        for table, col, sql in [
            ('terms', 'semester', 'semester TEXT'),
            ('terms', 'year', 'year INTEGER'),
            ('assessments', 'require_file', 'require_file INTEGER NOT NULL DEFAULT 0'),
            ('assessments', 'description', "description TEXT DEFAULT ''"),
            ('assessments', 'teacher_file_name', "teacher_file_name TEXT DEFAULT ''"),
            ('assessments', 'topic', "topic TEXT DEFAULT ''"),
            ('assessments', 'posted_at', 'posted_at TEXT DEFAULT CURRENT_TIMESTAMP'),
            ('assessment_scores', 'remarks', "remarks TEXT DEFAULT ''"),
            ('submissions', 'student_note', "student_note TEXT DEFAULT ''"),
        ]:
            _add_column_if_missing(db, table, col, sql)
        seed(db)
        db.commit()


def seed(db):
    if db.execute('SELECT COUNT(*) c FROM users').fetchone()['c']:
        return
    db.execute('INSERT INTO users(role,name,email,password_hash,department) VALUES(?,?,?,?,?)', ('admin', 'System Admin', 'admin@dapms.local', generate_password_hash('admin123'), 'CSE'))
    admin_user_id = db.execute("SELECT id FROM users WHERE email='admin@dapms.local'").fetchone()['id']
    
    db.execute('INSERT INTO admins(user_id,admin_id,role_name) VALUES(?,?,?)', (admin_user_id, 'A001', 'Admin'))
    db.execute('INSERT INTO users(role,name,email,password_hash,department) VALUES(?,?,?,?,?)', ('teacher', 'Demo Teacher', 'teacher@dapms.local', generate_password_hash('teacher123'), 'CSE'))
    teacher_user_id = db.execute("SELECT id FROM users WHERE email='teacher@dapms.local'").fetchone()['id']
    db.execute('INSERT INTO teachers(user_id,teacher_id) VALUES(?,?)', (teacher_user_id, 'T014001'))
    db.execute('INSERT INTO users(role,name,email,password_hash,department) VALUES(?,?,?,?,?)', ('student', 'Demo Student', 'student@dapms.local', generate_password_hash('student123'), 'CSE'))
    student_user_id = db.execute("SELECT id FROM users WHERE email='student@dapms.local'").fetchone()['id']
    db.execute('INSERT INTO students(user_id,student_id,admission_term) VALUES(?,?,?)', (student_user_id, '243014001', '243'))
    db.execute('INSERT INTO terms(name,start_date,end_date,status,semester,year) VALUES(?,?,?,?,?,?)', ('Spring 2026', '2026-01-01', '2026-04-30', 'running', 'Spring', 2026))
    term_id = db.execute('SELECT id FROM terms LIMIT 1').fetchone()['id']
    db.execute('INSERT INTO courses(course_code,title,credit) VALUES(?,?,?)', ('CSE1101', 'Structured Programming', 3))
    course_id = db.execute('SELECT id FROM courses LIMIT 1').fetchone()['id']
    db.execute('INSERT INTO sections(section_no,room_no,schedule,term_id,course_id,teacher_user_id) VALUES(?,?,?,?,?,?)', ('1', 'AB-403', 'Sun Tue 10:00', term_id, course_id, teacher_user_id))
    section_id = db.execute('SELECT id FROM sections LIMIT 1').fetchone()['id']
    db.execute('INSERT INTO enrollments(section_id,student_user_id,term_id) VALUES(?,?,?)', (section_id, student_user_id, term_id))
    enrollment_id = db.execute('SELECT id FROM enrollments LIMIT 1').fetchone()['id']
    db.execute('INSERT INTO assessments(section_id,type,title,percentage,total_marks,due_date,allow_submission,require_file,description,topic) VALUES(?,?,?,?,?,?,?,?,?,?)', (section_id, 'Assignment', 'Assignment 1', 10, 10, '2026-03-15', 1, 1, 'Submit your first assignment.', 'Week 1'))
    assess_id = db.execute('SELECT id FROM assessments LIMIT 1').fetchone()['id']
    db.execute('INSERT INTO assessment_scores(assessment_id,enrollment_id,marks) VALUES(?,?,?)', (assess_id, enrollment_id, 8))
    db.execute('INSERT INTO announcements(section_id,title,body,created_at) VALUES(?,?,?,datetime("now"))', (section_id, 'Welcome', 'Welcome to the course.'))
    db.execute('INSERT INTO attendance_sessions(section_id,class_no,class_date) VALUES(?,?,?)', (section_id, 1, '2026-03-01'))
    session_id = db.execute('SELECT id FROM attendance_sessions LIMIT 1').fetchone()['id']
    db.execute('INSERT INTO attendance_entries(session_id,enrollment_id,status) VALUES(?,?,?)', (session_id, enrollment_id, 'Present'))
    defaults = [
        ('Quiz', 10, 10, 'manual', 0, 1),
        ('Attendance', 10, 10, 'attendance', 1, 2),
        ('Mid', 25, 25, 'manual', 0, 3),
        ('Final', 45, 45, 'manual', 0, 4),
        ('Assignment', 10, 10, 'manual', 0, 5),
    ]
    for row in defaults:
        db.execute('INSERT INTO grading_components(section_id,name,weight,max_marks,category,auto_generated,sort_order) VALUES(?,?,?,?,?,?,?)', (section_id, *row))
