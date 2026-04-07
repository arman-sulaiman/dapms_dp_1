import os
from flask import Flask, g, send_from_directory, render_template

from .db import get_db, init_db
from .routes.auth import bp as auth_bp
from .routes.admin import bp as admin_bp
from .routes.teacher import bp as teacher_bp
from .routes.student import bp as student_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = '123'
    app.config['DATABASE'] = os.path.join(app.instance_path, 'dapms.sqlite3')
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db(app)

    @app.context_processor
    def inject_global_state():
        user = getattr(g, 'user', None)
        current_term = None
        if user is not None:
            try:
                current_term = get_db().execute("SELECT * FROM terms WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
            except Exception:
                current_term = None
        return {'current_term': current_term, 'current_user': user}

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    @app.route('/')
    def home():
        return render_template('home.html')

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')
    return app
