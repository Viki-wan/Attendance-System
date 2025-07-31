from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_socketio import SocketIO
import os
import sys
from pathlib import Path
from datetime import datetime

# Add the parent directory to the Python path to allow imports
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from lecturer_panel.config import Config
from lecturer_panel.services.database_service import DatabaseService
from lecturer_panel.blueprints.auth import auth_bp
from lecturer_panel.blueprints.dashboard import dashboard_bp
from lecturer_panel.blueprints.attendance import attendance_bp
from lecturer_panel.blueprints.reports import reports_bp
from lecturer_panel.blueprints.settings import settings_bp
from lecturer_panel.blueprints.diagnostics import diagnostics_bp
from lecturer_panel.blueprints.api import api_bp
from lecturer_panel.utils.decorators import login_required
from lecturer_panel.utils.helpers import get_current_user

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize SocketIO for real-time updates
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Initialize database service
    db_service = DatabaseService()
   # db_service.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(diagnostics_bp, url_prefix='/diagnostics')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Root route - redirect to dashboard if authenticated, else login
    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))
    
    # Global template context
    @app.context_processor
    def inject_globals():
        return {
            'current_user': get_current_user(),
            'app_name': 'Lecturer Panel',
            'version': '1.0.0',
            'build_date': datetime.now().strftime('%Y.%m.%d')
        }
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403
    
    # SocketIO events for real-time updates
    @socketio.on('connect')
    def handle_connect():
        if 'user_id' not in session:
            return False
        print(f"User {session['user_id']} connected")
    
    @socketio.on('disconnect')
    def handle_disconnect():
        if 'user_id' in session:
            print(f"User {session['user_id']} disconnected")
    
    # Store socketio instance in app for use in other modules
    app.socketio = socketio
    
    return app, socketio

# Create the app and socketio instances
app, socketio = create_app()

if __name__ == '__main__':
    # Development server
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)