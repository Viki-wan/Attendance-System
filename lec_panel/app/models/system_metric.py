"""
SystemMetric Model
Tracks system performance, face recognition metrics, and operational analytics
for the Flask Attendance System
"""

from datetime import datetime, timedelta
from app import db
from sqlalchemy import Index, func
import json


class SystemMetric(db.Model):
    """
    SystemMetric Model
    Captures performance metrics, face recognition statistics, and system health data
    
    Use Cases:
    - Face recognition performance tracking
    - API response time monitoring
    - Session quality metrics
    - System resource utilization
    - Error rate tracking
    - Capacity planning data
    """
    __tablename__ = 'system_metrics'
    
    # Metric Type Constants
    METRIC_TYPES = {
        # Face Recognition Metrics
        'face_detection_time': 'Time taken to detect faces in frame (ms)',
        'face_recognition_time': 'Time taken to recognize a face (ms)',
        'face_encoding_time': 'Time taken to generate face encoding (ms)',
        'recognition_confidence': 'Average confidence score for recognition',
        'faces_detected_count': 'Number of faces detected in frame',
        'successful_matches': 'Number of successful face matches',
        'failed_matches': 'Number of failed recognition attempts',
        'unknown_faces': 'Number of unknown faces detected',
        
        # Session Metrics
        'session_duration': 'Actual session duration (minutes)',
        'attendance_completion_time': 'Time to complete attendance (minutes)',
        'attendance_rate': 'Percentage of students marked present',
        'late_arrivals': 'Number of students marked late',
        'manual_corrections': 'Number of manual attendance corrections',
        
        # API Performance Metrics
        'api_response_time': 'API endpoint response time (ms)',
        'websocket_latency': 'WebSocket message latency (ms)',
        'frame_processing_rate': 'Frames processed per second',
        'camera_frame_rate': 'Camera capture frame rate (fps)',
        
        # System Resource Metrics
        'cpu_usage': 'CPU utilization percentage',
        'memory_usage': 'Memory usage (MB)',
        'gpu_usage': 'GPU utilization percentage (if available)',
        'database_query_time': 'Database query execution time (ms)',
        'cache_hit_rate': 'Redis cache hit rate percentage',
        
        # Error Tracking
        'error_count': 'Number of errors encountered',
        'timeout_count': 'Number of timeout occurrences',
        'retry_count': 'Number of retry attempts',
        
        # User Experience Metrics
        'page_load_time': 'Frontend page load time (ms)',
        'websocket_reconnections': 'Number of WebSocket reconnections',
        'user_wait_time': 'Average user wait time (seconds)'
    }
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Metric Information
    metric_name = db.Column(db.String(100), nullable=False, index=True)
    metric_value = db.Column(db.Float, nullable=False)
    metric_unit = db.Column(db.String(20))  # ms, seconds, %, count, MB, etc.
    
    # Context Information
    session_id = db.Column(
        db.Integer, 
        db.ForeignKey('class_sessions.session_id'),
        nullable=True,
        index=True
    )
    instructor_id = db.Column(
        db.String(20),
        db.ForeignKey('instructors.instructor_id'),
        nullable=True,
        index=True
    )
    
    # Additional Data (JSON format for flexibility)
    additional_data = db.Column(db.Text)  # Stored as JSON string
    
    # Metadata
    recorded_at = db.Column(
        db.DateTime, 
        default=datetime.utcnow, 
        nullable=False,
        index=True
    )
    
    # Relationships
    session = db.relationship('ClassSession', back_populates='metrics')
    instructor = db.relationship('Instructor', back_populates='metrics')
    
    # Composite Indexes for common queries
    __table_args__ = (
        Index('idx_metric_name_time', 'metric_name', 'recorded_at'),
        Index('idx_session_metrics', 'session_id', 'metric_name'),
        Index('idx_instructor_metrics', 'instructor_id', 'recorded_at'),
    )
    
    def __repr__(self):
        return f'<SystemMetric {self.metric_name}: {self.metric_value} {self.metric_unit}>'
    
    # ======================
    # Property Methods
    # ======================
    
    @property
    def additional_data_dict(self):
        """Parse additional_data JSON string to dictionary"""
        if self.additional_data:
            try:
                return json.loads(self.additional_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    @additional_data_dict.setter
    def additional_data_dict(self, data):
        """Set additional_data from dictionary"""
        if data:
            self.additional_data = json.dumps(data)
        else:
            self.additional_data = None
    
    @property
    def metric_description(self):
        """Get human-readable description of metric"""
        return self.METRIC_TYPES.get(self.metric_name, 'Custom metric')
    
    @property
    def is_performance_metric(self):
        """Check if this is a performance-related metric"""
        performance_metrics = [
            'face_detection_time', 'face_recognition_time', 'api_response_time',
            'websocket_latency', 'database_query_time', 'page_load_time'
        ]
        return self.metric_name in performance_metrics
    
    @property
    def is_error_metric(self):
        """Check if this is an error-related metric"""
        error_metrics = ['error_count', 'timeout_count', 'retry_count', 'failed_matches']
        return self.metric_name in error_metrics
    
    # ======================
    # Instance Methods
    # ======================
    
    def to_dict(self, include_relationships=False):
        """Convert metric to dictionary"""
        data = {
            'id': self.id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'metric_unit': self.metric_unit,
            'metric_description': self.metric_description,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'session_id': self.session_id,
            'instructor_id': self.instructor_id,
            'additional_data': self.additional_data_dict
        }
        
        if include_relationships:
            if self.session:
                data['session'] = {
                    'session_id': self.session.session_id,
                    'class_id': self.session.class_id,
                    'date': self.session.date.isoformat() if self.session.date else None
                }
            if self.instructor:
                data['instructor'] = {
                    'instructor_id': self.instructor.instructor_id,
                    'name': self.instructor.instructor_name
                }
        
        return data
    
    # ======================
    # Static Factory Methods
    # ======================
    
    @staticmethod
    def record_metric(metric_name, metric_value, metric_unit=None, 
                     session_id=None, instructor_id=None, additional_data=None):
        """
        Factory method to record a new metric
        
        Args:
            metric_name: Name of the metric
            metric_value: Numeric value
            metric_unit: Unit of measurement
            session_id: Optional session context
            instructor_id: Optional instructor context
            additional_data: Optional dict with extra information
            
        Returns:
            SystemMetric instance
        """
        metric = SystemMetric(
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            session_id=session_id,
            instructor_id=instructor_id
        )
        
        if additional_data:
            metric.additional_data_dict = additional_data
        
        db.session.add(metric)
        db.session.commit()
        
        return metric
    
    @staticmethod
    def record_face_recognition_metrics(session_id, detection_time, recognition_time, 
                                       confidence, faces_detected, matches_found):
        """
        Batch record face recognition metrics for a session
        
        Args:
            session_id: Session ID
            detection_time: Face detection time in ms
            recognition_time: Recognition time in ms
            confidence: Average confidence score
            faces_detected: Number of faces detected
            matches_found: Number of successful matches
        """
        metrics = [
            SystemMetric(
                metric_name='face_detection_time',
                metric_value=detection_time,
                metric_unit='ms',
                session_id=session_id
            ),
            SystemMetric(
                metric_name='face_recognition_time',
                metric_value=recognition_time,
                metric_unit='ms',
                session_id=session_id
            ),
            SystemMetric(
                metric_name='recognition_confidence',
                metric_value=confidence,
                metric_unit='score',
                session_id=session_id
            ),
            SystemMetric(
                metric_name='faces_detected_count',
                metric_value=faces_detected,
                metric_unit='count',
                session_id=session_id
            ),
            SystemMetric(
                metric_name='successful_matches',
                metric_value=matches_found,
                metric_unit='count',
                session_id=session_id
            )
        ]
        
        db.session.bulk_save_objects(metrics)
        db.session.commit()
    
    # ======================
    # Query Methods
    # ======================
    
    @staticmethod
    def get_by_metric_name(metric_name, start_date=None, end_date=None, limit=None):
        """
        Get metrics by name with optional date filtering
        
        Args:
            metric_name: Name of metric to retrieve
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Optional result limit
            
        Returns:
            List of SystemMetric objects
        """
        query = SystemMetric.query.filter_by(metric_name=metric_name)
        
        if start_date:
            query = query.filter(SystemMetric.recorded_at >= start_date)
        
        if end_date:
            query = query.filter(SystemMetric.recorded_at <= end_date)
        
        query = query.order_by(SystemMetric.recorded_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_session_metrics(session_id):
        """Get all metrics for a specific session"""
        return SystemMetric.query.filter_by(
            session_id=session_id
        ).order_by(SystemMetric.recorded_at).all()
    
    @staticmethod
    def get_instructor_metrics(instructor_id, start_date=None, end_date=None):
        """Get all metrics for a specific instructor"""
        query = SystemMetric.query.filter_by(instructor_id=instructor_id)
        
        if start_date:
            query = query.filter(SystemMetric.recorded_at >= start_date)
        
        if end_date:
            query = query.filter(SystemMetric.recorded_at <= end_date)
        
        return query.order_by(SystemMetric.recorded_at.desc()).all()
    
    # ======================
    # Analytics Methods
    # ======================
    
    @staticmethod
    def get_average_metric(metric_name, start_date=None, end_date=None, 
                          session_id=None, instructor_id=None):
        """
        Calculate average value for a metric
        
        Args:
            metric_name: Name of metric
            start_date: Optional start date
            end_date: Optional end date
            session_id: Optional session filter
            instructor_id: Optional instructor filter
            
        Returns:
            float: Average value or None
        """
        query = db.session.query(func.avg(SystemMetric.metric_value)).filter(
            SystemMetric.metric_name == metric_name
        )
        
        if start_date:
            query = query.filter(SystemMetric.recorded_at >= start_date)
        
        if end_date:
            query = query.filter(SystemMetric.recorded_at <= end_date)
        
        if session_id:
            query = query.filter(SystemMetric.session_id == session_id)
        
        if instructor_id:
            query = query.filter(SystemMetric.instructor_id == instructor_id)
        
        result = query.scalar()
        return float(result) if result else None
    
    @staticmethod
    def get_metric_statistics(metric_name, start_date=None, end_date=None):
        """
        Get comprehensive statistics for a metric
        
        Args:
            metric_name: Name of metric
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            dict: Statistics including avg, min, max, count
        """
        query = db.session.query(
            func.avg(SystemMetric.metric_value).label('average'),
            func.min(SystemMetric.metric_value).label('minimum'),
            func.max(SystemMetric.metric_value).label('maximum'),
            func.count(SystemMetric.id).label('count'),
            func.sum(SystemMetric.metric_value).label('total')
        ).filter(SystemMetric.metric_name == metric_name)
        
        if start_date:
            query = query.filter(SystemMetric.recorded_at >= start_date)
        
        if end_date:
            query = query.filter(SystemMetric.recorded_at <= end_date)
        
        result = query.first()
        
        return {
            'metric_name': metric_name,
            'average': float(result.average) if result.average else 0,
            'minimum': float(result.minimum) if result.minimum else 0,
            'maximum': float(result.maximum) if result.maximum else 0,
            'count': result.count or 0,
            'total': float(result.total) if result.total else 0
        }
    
    @staticmethod
    def get_performance_summary(session_id):
        """
        Get comprehensive performance summary for a session
        
        Args:
            session_id: Session ID
            
        Returns:
            dict: Performance metrics summary
        """
        metrics = SystemMetric.query.filter_by(session_id=session_id).all()
        
        summary = {
            'total_metrics_recorded': len(metrics),
            'face_recognition': {},
            'performance': {},
            'errors': {}
        }
        
        # Group metrics by category
        for metric in metrics:
            if 'face' in metric.metric_name or 'recognition' in metric.metric_name:
                summary['face_recognition'][metric.metric_name] = metric.metric_value
            elif metric.is_performance_metric:
                summary['performance'][metric.metric_name] = metric.metric_value
            elif metric.is_error_metric:
                summary['errors'][metric.metric_name] = metric.metric_value
        
        return summary
    
    @staticmethod
    def get_system_health_score(time_window_hours=24):
        """
        Calculate overall system health score based on recent metrics
        
        Args:
            time_window_hours: Hours to look back
            
        Returns:
            dict: Health score and breakdown
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)
        
        # Get error rate
        error_metrics = SystemMetric.query.filter(
            SystemMetric.metric_name.in_(['error_count', 'timeout_count', 'failed_matches']),
            SystemMetric.recorded_at >= cutoff_time
        ).all()
        
        total_errors = sum(m.metric_value for m in error_metrics)
        
        # Get average performance metrics
        avg_response_time = SystemMetric.get_average_metric(
            'api_response_time',
            start_date=cutoff_time
        ) or 0
        
        avg_recognition_time = SystemMetric.get_average_metric(
            'face_recognition_time',
            start_date=cutoff_time
        ) or 0
        
        # Calculate health score (0-100)
        # Lower errors and faster response times = higher score
        error_penalty = min(total_errors * 2, 50)  # Max 50 point penalty
        performance_penalty = 0
        
        if avg_response_time > 1000:  # >1 second
            performance_penalty += 20
        elif avg_response_time > 500:  # >500ms
            performance_penalty += 10
        
        if avg_recognition_time > 500:  # >500ms
            performance_penalty += 20
        elif avg_recognition_time > 200:  # >200ms
            performance_penalty += 10
        
        health_score = max(0, 100 - error_penalty - performance_penalty)
        
        return {
            'health_score': health_score,
            'status': 'healthy' if health_score >= 80 else 'degraded' if health_score >= 60 else 'unhealthy',
            'metrics': {
                'total_errors': total_errors,
                'avg_response_time_ms': avg_response_time,
                'avg_recognition_time_ms': avg_recognition_time
            },
            'time_window_hours': time_window_hours,
            'calculated_at': datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def get_trending_metrics(metric_name, days=7, interval='daily'):
        """
        Get trending data for a metric over time
        
        Args:
            metric_name: Name of metric
            days: Number of days to look back
            interval: 'hourly' or 'daily'
            
        Returns:
            list: Time-series data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        if interval == 'daily':
            # Group by day
            query = db.session.query(
                func.date(SystemMetric.recorded_at).label('date'),
                func.avg(SystemMetric.metric_value).label('average'),
                func.count(SystemMetric.id).label('count')
            ).filter(
                SystemMetric.metric_name == metric_name,
                SystemMetric.recorded_at >= cutoff_date
            ).group_by(
                func.date(SystemMetric.recorded_at)
            ).order_by('date')
        else:
            # Group by hour
            query = db.session.query(
                func.strftime('%Y-%m-%d %H:00:00', SystemMetric.recorded_at).label('hour'),
                func.avg(SystemMetric.metric_value).label('average'),
                func.count(SystemMetric.id).label('count')
            ).filter(
                SystemMetric.metric_name == metric_name,
                SystemMetric.recorded_at >= cutoff_date
            ).group_by('hour').order_by('hour')
        
        results = query.all()
        
        return [
            {
                'timestamp': str(r[0]),
                'average': float(r[1]) if r[1] else 0,
                'count': r[2]
            }
            for r in results
        ]
    
    # ======================
    # Maintenance Methods
    # ======================
    
    @staticmethod
    def cleanup_old_metrics(days_to_keep=90):
        """
        Delete metrics older than specified days
        
        Args:
            days_to_keep: Number of days to retain
            
        Returns:
            int: Number of records deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        deleted_count = SystemMetric.query.filter(
            SystemMetric.recorded_at < cutoff_date
        ).delete()
        
        db.session.commit()
        
        return deleted_count
    
    @staticmethod
    def get_storage_size_estimate():
        """
        Estimate storage size of metrics table
        
        Returns:
            dict: Storage statistics
        """
        total_count = SystemMetric.query.count()
        oldest_metric = SystemMetric.query.order_by(
            SystemMetric.recorded_at.asc()
        ).first()
        newest_metric = SystemMetric.query.order_by(
            SystemMetric.recorded_at.desc()
        ).first()
        
        # Rough estimate: ~200 bytes per metric record
        estimated_size_mb = (total_count * 200) / (1024 * 1024)
        
        return {
            'total_records': total_count,
            'estimated_size_mb': round(estimated_size_mb, 2),
            'oldest_record': oldest_metric.recorded_at.isoformat() if oldest_metric else None,
            'newest_record': newest_metric.recorded_at.isoformat() if newest_metric else None
        }