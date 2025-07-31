from flask import Blueprint, render_template, request, session, jsonify, Response
from lecturer_panel.utils.decorators import login_required
from lecturer_panel.utils.helpers import get_current_user
from lecturer_panel.services.diagnostics_service import DiagnosticsService

diagnostics_bp = Blueprint('diagnostics', __name__)
diagnostics_service = DiagnosticsService()

@diagnostics_bp.route('/')
@login_required
def index():
    """Main diagnostics dashboard"""
    system_metrics = diagnostics_service.get_system_diagnostics()
    db_health = diagnostics_service._get_database_diagnostics()
    camera_status = diagnostics_service.get_camera_diagnostics()
    recent_errors = diagnostics_service.get_recent_errors(limit=50) if hasattr(diagnostics_service, 'get_recent_errors') else []
    performance_metrics = diagnostics_service._get_performance_metrics()
    return render_template('diagnostics/index.html',
                         system_metrics=system_metrics,
                         db_health=db_health,
                         camera_status=camera_status,
                         recent_errors=recent_errors,
                         performance_metrics=performance_metrics)

@diagnostics_bp.route('/camera-test')
@login_required
def camera_test():
    """Camera diagnostics page"""
    return render_template('diagnostics/camera_test.html')

@diagnostics_bp.route('/api/camera-info')
@login_required
def camera_info():
    """Get camera information and capabilities"""
    try:
        diagnostics = diagnostics_service.get_camera_diagnostics()
        return jsonify({'cameras': diagnostics.get('cameras', [])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/camera-quality/<int:camera_index>')
@login_required
def camera_quality(camera_index):
    """Test camera quality and detect issues"""
    try:
        result = diagnostics_service._test_camera(camera_index)
        if not result:
            return jsonify({'error': 'Camera not available'}), 400
        quality_score = result.get('quality_score', 0)
        recommendations = diagnostics_service.get_camera_recommendations(quality_score) if hasattr(diagnostics_service, 'get_camera_recommendations') else []
        return jsonify({
            'quality_score': quality_score,
            'camera_info': result,
            'recommendations': recommendations
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/system-health')
@login_required
def system_health():
    """Get current system health metrics"""
    try:
        metrics = diagnostics_service.get_system_diagnostics()
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/database-health')
@login_required
def database_health():
    """Get database health information"""
    try:
        health = diagnostics_service._get_database_diagnostics()
        return jsonify(health)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/performance-test')
@login_required
def performance_test():
    """Run performance tests"""
    try:
        results = diagnostics_service._get_performance_metrics()
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/face-recognition-test', methods=['POST'])
@login_required
def face_recognition_test():
    """Test face recognition performance"""
    try:
        test_results = diagnostics_service._get_face_recognition_diagnostics()
        return jsonify(test_results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/cleanup-logs', methods=['POST'])
@login_required
def cleanup_logs():
    """Clean up old logs and temporary files"""
    try:
        deleted_count = diagnostics_service.cleanup_old_diagnostics(days=90)
        temp_files_cleaned = diagnostics_service.cleanup_temp_files() if hasattr(diagnostics_service, 'cleanup_temp_files') else 0
        return jsonify({
            'logs_deleted': deleted_count,
            'temp_files_cleaned': temp_files_cleaned,
            'success': True
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/api/export-diagnostics')
@login_required
def export_diagnostics():
    """Export diagnostic data"""
    try:
        diagnostics_data = diagnostics_service.get_system_diagnostics()
        return jsonify(diagnostics_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@diagnostics_bp.route('/logs')
@login_required
def view_logs():
    logs = diagnostics_service.get_recent_activity_logs(limit=100) if hasattr(diagnostics_service, 'get_recent_activity_logs') else []
    return render_template('diagnostics/logs.html', logs=logs)

@diagnostics_bp.route('/api/logs')
@login_required
def api_logs():
    limit = request.args.get('limit', 50, type=int)
    log_type = request.args.get('type', 'all')
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    logs = diagnostics_service.get_filtered_logs(limit=limit, log_type=log_type, date_from=date_from, date_to=date_to) if hasattr(diagnostics_service, 'get_filtered_logs') else []
    return jsonify({'logs': logs})

@diagnostics_bp.route('/api/realtime-metrics')
@login_required
def realtime_metrics():
    def generate():
        while True:
            metrics = diagnostics_service.get_realtime_metrics() if hasattr(diagnostics_service, 'get_realtime_metrics') else {}
            yield f"data: {json.dumps(metrics)}\n\n"
            import time
            time.sleep(5)
    return Response(generate(), mimetype='text/plain')