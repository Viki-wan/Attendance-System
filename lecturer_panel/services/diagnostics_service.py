"""
Diagnostics Service for Face Recognition Attendance System
Handles camera diagnostics, system health monitoring, and performance metrics
"""
import cv2
import psutil
import platform
import time
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sqlite3
import logging
from lecturer_panel.utils.helpers import get_database_connection, log_error

class DiagnosticsService:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def get_camera_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive camera diagnostics"""
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'cameras': [],
            'overall_status': 'unknown',
            'errors': []
        }
        
        try:
            # Test multiple camera indices
            for camera_index in range(5):  # Test cameras 0-4
                camera_info = self._test_camera(camera_index)
                if camera_info:
                    diagnostics['cameras'].append(camera_info)
            
            # Determine overall status
            if diagnostics['cameras']:
                working_cameras = [c for c in diagnostics['cameras'] if c['status'] == 'working']
                if working_cameras:
                    diagnostics['overall_status'] = 'healthy'
                else:
                    diagnostics['overall_status'] = 'degraded'
            else:
                diagnostics['overall_status'] = 'critical'
                diagnostics['errors'].append('No cameras detected')
            
            # Store diagnostics in database
            self._store_camera_diagnostics(diagnostics)
            
        except Exception as e:
            self.logger.error(f"Error in camera diagnostics: {str(e)}")
            diagnostics['overall_status'] = 'error'
            diagnostics['errors'].append(f"Diagnostics error: {str(e)}")
        
        return diagnostics
    
    def _test_camera(self, camera_index: int) -> Optional[Dict[str, Any]]:
        """Test individual camera and return diagnostics"""
        camera_info = {
            'index': camera_index,
            'status': 'not_found',
            'resolution': None,
            'fps': None,
            'quality_score': None,
            'latency_ms': None,
            'error': None
        }
        
        cap = None
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return None
            
            # Test camera initialization time
            start_time = time.time()
            
            # Get camera properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            camera_info['resolution'] = f"{width}x{height}"
            camera_info['fps'] = fps
            
            # Test frame capture
            ret, frame = cap.read()
            if ret and frame is not None:
                camera_info['status'] = 'working'
                camera_info['latency_ms'] = int((time.time() - start_time) * 1000)
                camera_info['quality_score'] = self._calculate_quality_score(frame)
            else:
                camera_info['status'] = 'error'
                camera_info['error'] = 'Failed to capture frame'
            
        except Exception as e:
            camera_info['status'] = 'error'
            camera_info['error'] = str(e)
        finally:
            if cap:
                cap.release()
        
        return camera_info
    
    def _calculate_quality_score(self, frame: np.ndarray) -> float:
        """Calculate image quality score (0-100)"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Calculate sharpness using Laplacian variance
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Calculate brightness
            brightness = np.mean(gray)
            
            # Calculate contrast
            contrast = gray.std()
            
            # Normalize and combine metrics
            sharpness_score = min(laplacian_var / 1000, 1.0) * 40  # 40% weight
            brightness_score = (1 - abs(brightness - 127) / 127) * 30  # 30% weight
            contrast_score = min(contrast / 64, 1.0) * 30  # 30% weight
            
            quality_score = sharpness_score + brightness_score + contrast_score
            return round(quality_score, 2)
            
        except Exception as e:
            self.logger.error(f"Error calculating quality score: {str(e)}")
            return 0.0
    
    def get_system_diagnostics(self) -> Dict[str, Any]:
        """Get comprehensive system diagnostics"""
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {},
            'performance': {},
            'database': {},
            'face_recognition': {},
            'overall_status': 'healthy',
            'warnings': [],
            'errors': []
        }
        
        try:
            # System information
            diagnostics['system_info'] = {
                'platform': platform.system(),
                'platform_release': platform.release(),
                'architecture': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version(),
                'hostname': platform.node()
            }
            
            # Performance metrics
            diagnostics['performance'] = self._get_performance_metrics()
            
            # Database diagnostics
            diagnostics['database'] = self._get_database_diagnostics()
            
            # Face recognition diagnostics
            diagnostics['face_recognition'] = self._get_face_recognition_diagnostics()
            
            # Determine overall status
            diagnostics['overall_status'] = self._determine_system_status(diagnostics)
            
            # Store system diagnostics
            self._store_system_diagnostics(diagnostics)
            
        except Exception as e:
            self.logger.error(f"Error in system diagnostics: {str(e)}")
            diagnostics['overall_status'] = 'error'
            diagnostics['errors'].append(f"System diagnostics error: {str(e)}")
        
        return diagnostics
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available / (1024**3)  # GB
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free = disk.free / (1024**3)  # GB
            
            return {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_percent': memory_percent,
                'memory_available_gb': round(memory_available, 2),
                'disk_percent': disk_percent,
                'disk_free_gb': round(disk_free, 2),
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except Exception as e:
            self.logger.error(f"Error getting performance metrics: {str(e)}")
            return {}
    
    def _get_database_diagnostics(self) -> Dict[str, Any]:
        """Get database diagnostics"""
        diagnostics = {
            'status': 'unknown',
            'connection_time_ms': None,
            'table_counts': {},
            'database_size_mb': None,
            'errors': []
        }
        
        try:
            start_time = time.time()
            conn = get_database_connection()
            diagnostics['connection_time_ms'] = int((time.time() - start_time) * 1000)
            
            cursor = conn.cursor()
            
            # Get table counts
            tables = ['students', 'instructors', 'classes', 'class_sessions', 'attendance', 'courses']
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    diagnostics['table_counts'][table] = count
                except Exception as e:
                    diagnostics['errors'].append(f"Error counting {table}: {str(e)}")
            
            # Get database size
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            size_bytes = cursor.fetchone()[0]
            diagnostics['database_size_mb'] = round(size_bytes / (1024**2), 2)
            
            diagnostics['status'] = 'healthy'
            conn.close()
            
        except Exception as e:
            diagnostics['status'] = 'error'
            diagnostics['errors'].append(f"Database error: {str(e)}")
        
        return diagnostics
    
    def _get_face_recognition_diagnostics(self) -> Dict[str, Any]:
        """Get face recognition system diagnostics"""
        diagnostics = {
            'status': 'unknown',
            'face_recognition_available': False,
            'opencv_version': None,
            'face_encodings_count': 0,
            'last_recognition_time': None,
            'errors': []
        }
        
        try:
            # Check OpenCV
            diagnostics['opencv_version'] = cv2.__version__
            
            # Check face_recognition library
            try:
                import face_recognition
                diagnostics['face_recognition_available'] = True
            except ImportError:
                diagnostics['errors'].append("face_recognition library not available")
            
            # Get face encodings count
            conn = get_database_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students WHERE face_encoding IS NOT NULL")
            diagnostics['face_encodings_count'] = cursor.fetchone()[0]
            
            # Get last recognition activity
            cursor.execute("""
                SELECT MAX(timestamp) FROM attendance 
                WHERE method = 'face_recognition'
            """)
            last_recognition = cursor.fetchone()[0]
            if last_recognition:
                diagnostics['last_recognition_time'] = last_recognition
            
            conn.close()
            
            diagnostics['status'] = 'healthy' if diagnostics['face_recognition_available'] else 'degraded'
            
        except Exception as e:
            diagnostics['status'] = 'error'
            diagnostics['errors'].append(f"Face recognition error: {str(e)}")
        
        return diagnostics
    
    def _determine_system_status(self, diagnostics: Dict[str, Any]) -> str:
        """Determine overall system status based on diagnostics"""
        try:
            # Check for critical errors
            if diagnostics['database']['status'] == 'error':
                return 'critical'
            
            # Check performance thresholds
            perf = diagnostics['performance']
            if perf.get('cpu_percent', 0) > 90:
                diagnostics['warnings'].append('High CPU usage detected')
            if perf.get('memory_percent', 0) > 85:
                diagnostics['warnings'].append('High memory usage detected')
            if perf.get('disk_percent', 0) > 90:
                diagnostics['warnings'].append('Low disk space detected')
            
            # Check face recognition
            if diagnostics['face_recognition']['status'] == 'error':
                diagnostics['warnings'].append('Face recognition system issues detected')
            
            # Determine status
            if diagnostics['errors']:
                return 'error'
            elif diagnostics['warnings']:
                return 'warning'
            else:
                return 'healthy'
                
        except Exception as e:
            self.logger.error(f"Error determining system status: {str(e)}")
            return 'error'
    
    def _store_camera_diagnostics(self, diagnostics: Dict[str, Any]):
        """Store camera diagnostics in database"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            # Store overall camera status
            cursor.execute("""
                INSERT INTO system_metrics 
                (metric_name, metric_value, metric_unit, additional_data)
                VALUES (?, ?, ?, ?)
            """, (
                'camera_diagnostics',
                len(diagnostics['cameras']),
                'count',
                str(diagnostics)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error storing camera diagnostics: {str(e)}")
    
    def _store_system_diagnostics(self, diagnostics: Dict[str, Any]):
        """Store system diagnostics in database"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            # Store key metrics
            metrics = [
                ('system_status', diagnostics['overall_status'], 'status'),
                ('cpu_usage', diagnostics['performance'].get('cpu_percent', 0), 'percent'),
                ('memory_usage', diagnostics['performance'].get('memory_percent', 0), 'percent'),
                ('disk_usage', diagnostics['performance'].get('disk_percent', 0), 'percent'),
                ('database_size', diagnostics['database'].get('database_size_mb', 0), 'MB')
            ]
            
            for metric_name, metric_value, metric_unit in metrics:
                cursor.execute("""
                    INSERT INTO system_metrics 
                    (metric_name, metric_value, metric_unit, additional_data)
                    VALUES (?, ?, ?, ?)
                """, (metric_name, metric_value, metric_unit, str(diagnostics)))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Error storing system diagnostics: {str(e)}")
    
    def get_diagnostic_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get diagnostic history for a specific metric"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            since_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT metric_value, metric_unit, recorded_at, additional_data
                FROM system_metrics
                WHERE metric_name = ? AND recorded_at > ?
                ORDER BY recorded_at DESC
            """, (metric_name, since_time))
            
            results = cursor.fetchall()
            conn.close()
            
            history = []
            for row in results:
                history.append({
                    'value': row[0],
                    'unit': row[1],
                    'timestamp': row[2],
                    'additional_data': row[3]
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting diagnostic history: {str(e)}")
            return []
    
    def cleanup_old_diagnostics(self, days: int = 30):
        """Clean up old diagnostic data"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cursor.execute("""
                DELETE FROM system_metrics 
                WHERE recorded_at < ?
            """, (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted_count} old diagnostic records")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up diagnostics: {str(e)}")
            return 0