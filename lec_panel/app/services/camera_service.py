"""
Camera Service for Web-based Face Recognition
Handles frame processing from browser MediaStream API
"""

import cv2
import numpy as np
from typing import Optional, Dict
from datetime import datetime
import base64


class CameraService:
    """
    Manages camera operations for web-based attendance system
    """
    
    def __init__(self):
        """Initialize camera service"""
        self.active_sessions = {}  # session_id -> camera_info
        self.frame_buffer = {}  # session_id -> latest_frame
        
        # Camera settings
        self.target_fps = 30
        self.processing_fps = 2  # Process 2 frames per second
        self.max_resolution = (1280, 720)
        self.min_resolution = (640, 480)
    
    def decode_frame(self, base64_data: str) -> Optional[np.ndarray]:
        """
        Decode base64 image data to OpenCV frame
        
        Args:
            base64_data: Base64 encoded image (from browser)
            
        Returns:
            OpenCV frame (numpy array) or None if decode fails
        """
        try:
            # Remove data URL prefix if present
            if ',' in base64_data:
                base64_data = base64_data.split(',')[1]
            
            # Decode base64
            img_data = base64.b64decode(base64_data)
            
            # Convert to numpy array
            nparr = np.frombuffer(img_data, np.uint8)
            
            # Decode to image
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is None:
                print("❌ Failed to decode frame")
                return None
            
            return frame
            
        except Exception as e:
            print(f"❌ Error decoding frame: {e}")
            return None
    
    def encode_frame(self, frame: np.ndarray, quality: int = 85) -> Optional[str]:
        """
        Encode OpenCV frame to base64 for web display
        
        Args:
            frame: OpenCV frame
            quality: JPEG quality (0-100)
            
        Returns:
            Base64 encoded image string or None
        """
        try:
            # Encode as JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, buffer = cv2.imencode('.jpg', frame, encode_param)
            
            # Convert to base64
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            
            return f"data:image/jpeg;base64,{jpg_as_text}"
            
        except Exception as e:
            print(f"❌ Error encoding frame: {e}")
            return None
    
    def validate_frame(self, frame: np.ndarray) -> Dict:
        """
        Validate frame quality and resolution
        
        Args:
            frame: OpenCV frame
            
        Returns:
            Dictionary with validation results
        """
        if frame is None:
            return {
                'valid': False,
                'error': 'null_frame'
            }
        
        height, width = frame.shape[:2]
        
        # Check resolution
        resolution_ok = (
            self.min_resolution[0] <= width <= self.max_resolution[0] and
            self.min_resolution[1] <= height <= self.max_resolution[1]
        )
        
        # Check if frame is too dark or too bright
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = gray.mean()
        brightness_ok = 20 < brightness < 240
        
        # Check if frame is blurry
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_ok = blur_score > 100
        
        return {
            'valid': resolution_ok and brightness_ok and blur_ok,
            'resolution': (width, height),
            'resolution_ok': resolution_ok,
            'brightness': brightness,
            'brightness_ok': brightness_ok,
            'blur_score': blur_score,
            'blur_ok': blur_ok,
            'warnings': []
        }
    
    def resize_frame(
        self, 
        frame: np.ndarray, 
        target_width: int = 640
    ) -> np.ndarray:
        """
        Resize frame maintaining aspect ratio
        
        Args:
            frame: Input frame
            target_width: Desired width
            
        Returns:
            Resized frame
        """
        height, width = frame.shape[:2]
        
        if width <= target_width:
            return frame
        
        # Calculate new dimensions
        ratio = target_width / width
        new_height = int(height * ratio)
        
        # Resize
        resized = cv2.resize(
            frame, 
            (target_width, new_height),
            interpolation=cv2.INTER_AREA
        )
        
        return resized
    
    def draw_face_box(
        self,
        frame: np.ndarray,
        face_location: tuple,
        label: str,
        color: tuple = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw bounding box and label on face
        
        Args:
            frame: Input frame
            face_location: (top, right, bottom, left)
            label: Text label to display
            color: BGR color tuple
            thickness: Line thickness
            
        Returns:
            Frame with annotations
        """
        top, right, bottom, left = face_location
        
        # Draw rectangle
        cv2.rectangle(frame, (left, top), (right, bottom), color, thickness)
        
        # Draw label background
        label_height = 30
        cv2.rectangle(
            frame,
            (left, top - label_height),
            (right, top),
            color,
            -1  # Filled
        )
        
        # Draw label text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        text_thickness = 1
        
        # Calculate text size for centering
        (text_width, text_height), _ = cv2.getTextSize(
            label, font, font_scale, text_thickness
        )
        
        text_x = left + (right - left - text_width) // 2
        text_y = top - (label_height - text_height) // 2
        
        cv2.putText(
            frame,
            label,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            text_thickness
        )
        
        return frame
    
    def add_overlay_info(
        self,
        frame: np.ndarray,
        info: Dict
    ) -> np.ndarray:
        """
        Add overlay information to frame (status, timestamp, etc.)
        
        Args:
            frame: Input frame
            info: Dictionary with overlay information
            
        Returns:
            Frame with overlay
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        color = (255, 255, 255)
        bg_color = (0, 0, 0)
        
        y_offset = 20
        
        for key, value in info.items():
            text = f"{key}: {value}"
            
            # Get text size
            (text_width, text_height), _ = cv2.getTextSize(
                text, font, font_scale, thickness
            )
            
            # Draw background
            cv2.rectangle(
                frame,
                (5, y_offset - text_height - 5),
                (text_width + 15, y_offset + 5),
                bg_color,
                -1
            )
            
            # Draw text
            cv2.putText(
                frame,
                text,
                (10, y_offset),
                font,
                font_scale,
                color,
                thickness
            )
            
            y_offset += text_height + 15
        
        return frame
    
    def register_session(self, session_id: int, user_id: int) -> bool:
        """
        Register an active camera session
        
        Args:
            session_id: Attendance session ID
            user_id: Instructor user ID
            
        Returns:
            True if registered successfully
        """
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'started_at': datetime.now(),
            'frame_count': 0,
            'faces_detected': 0,
            'faces_recognized': 0
        }
        
        print(f"📷 Camera session registered: {session_id}")
        return True
    
    def unregister_session(self, session_id: int):
        """Remove camera session"""
        if session_id in self.active_sessions:
            stats = self.active_sessions[session_id]
            duration = (datetime.now() - stats['started_at']).total_seconds()
            
            print(f"📷 Camera session ended: {session_id}")
            print(f"   Duration: {duration:.1f}s")
            print(f"   Frames: {stats['frame_count']}")
            print(f"   Faces detected: {stats['faces_detected']}")
            print(f"   Faces recognized: {stats['faces_recognized']}")
            
            del self.active_sessions[session_id]
            
            if session_id in self.frame_buffer:
                del self.frame_buffer[session_id]
    
    def update_session_stats(
        self,
        session_id: int,
        faces_detected: int = 0,
        faces_recognized: int = 0
    ):
        """Update session statistics"""
        if session_id in self.active_sessions:
            stats = self.active_sessions[session_id]
            stats['frame_count'] += 1
            stats['faces_detected'] += faces_detected
            stats['faces_recognized'] += faces_recognized
    
    def get_session_stats(self, session_id: int) -> Optional[Dict]:
        """Get statistics for a camera session"""
        return self.active_sessions.get(session_id)
    
    def buffer_frame(self, session_id: int, frame: np.ndarray):
        """Store latest frame for a session"""
        self.frame_buffer[session_id] = {
            'frame': frame,
            'timestamp': datetime.now()
        }
    
    def get_buffered_frame(self, session_id: int) -> Optional[np.ndarray]:
        """Retrieve latest buffered frame"""
        buffer = self.frame_buffer.get(session_id)
        if buffer:
            return buffer['frame']
        return None
    
    def apply_preprocessing(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply preprocessing to improve face detection
        
        Args:
            frame: Input frame
            
        Returns:
            Preprocessed frame
        """
        # Convert to RGB (face_recognition uses RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Histogram equalization for better contrast
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        equalized = cv2.equalizeHist(gray)
        
        # Convert back to BGR for display
        preprocessed = cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)
        
        return preprocessed
    
    def get_active_sessions(self) -> Dict:
        """Get all active camera sessions"""
        return {
            session_id: {
                'user_id': info['user_id'],
                'duration': (datetime.now() - info['started_at']).total_seconds(),
                'frame_count': info['frame_count'],
                'faces_detected': info['faces_detected'],
                'faces_recognized': info['faces_recognized']
            }
            for session_id, info in self.active_sessions.items()
        }