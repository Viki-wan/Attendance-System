"""
Fixed Implementation Checker for Face Recognition System
Run this script to verify which components are implemented
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import re

class ImplementationChecker:
    def __init__(self, project_root: str = None):
        # Auto-detect project root
        if project_root:
            self.project_root = Path(project_root)
        else:
            # Try to find project root
            current = Path.cwd()
            
            # PRIORITY 1: Check if we're in lec_panel (the actual project folder)
            if current.name == 'lec_panel' and (current / 'app').exists():
                self.project_root = current
            # PRIORITY 2: Check if script is in lec_panel (current directory has app)
            elif (current / 'app').exists() and (current / 'run.py').exists():
                self.project_root = current
            # PRIORITY 3: Check if we're inside lec_panel
            elif 'lec_panel' in current.parts:
                # Navigate up to find lec_panel folder
                for parent in [current] + list(current.parents):
                    if parent.name == 'lec_panel' and (parent / 'app').exists():
                        self.project_root = parent
                        break
                else:
                    self.project_root = current
            # PRIORITY 4: Check if lec_panel is a subdirectory
            elif (current / 'lec_panel' / 'app').exists():
                self.project_root = current / 'lec_panel'
            # PRIORITY 5: Check parent for lec_panel
            elif (current.parent / 'lec_panel' / 'app').exists():
                self.project_root = current.parent / 'lec_panel'
            else:
                # Default to current directory
                self.project_root = current
        
        self.app_dir = self.project_root / 'app'
        self.results = {
            'files': {},
            'socketio_handlers': [],
            'celery_tasks': [],
            'service_methods': {},
            'missing': [],
            'project_root': str(self.project_root)
        }
    
    def check_file_exists(self, relative_path: str) -> Tuple[bool, Path]:
        """Check if a file exists"""
        full_path = self.project_root / relative_path
        exists = full_path.exists()
        
        # Debug output
        if not exists:
            print(f"      Looking for: {full_path}")
            # Try alternative paths
            alt_path = self.project_root / relative_path.replace('/', '\\')
            if alt_path.exists():
                print(f"      Found at: {alt_path}")
                return True, alt_path
        
        return exists, full_path
    
    def check_socketio_events(self, filepath: Path) -> List[str]:
        """Extract Socket.IO event handlers from file"""
        handlers = []
        if not filepath.exists():
            return handlers
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Search for @socketio.on decorators
            pattern = r"@socketio\.on\(['\"]([^'\"]+)['\"]\)"
            matches = re.findall(pattern, content)
            handlers = list(set(matches))
        except Exception as e:
            print(f"      Error reading {filepath}: {e}")
        
        return handlers
    
    def check_celery_tasks(self, filepath: Path) -> List[str]:
        """Extract Celery tasks from file"""
        tasks = []
        if not filepath.exists():
            return tasks
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Search for task decorators and function names
            pattern = r"@(?:shared_task|celery_app\.task|celery\.task).*?\ndef\s+(\w+)"
            matches = re.findall(pattern, content, re.DOTALL)
            tasks = list(set(matches))
        except Exception as e:
            print(f"      Error reading {filepath}: {e}")
        
        return tasks
    
    def check_class_methods(self, filepath: Path, class_name: str) -> List[str]:
        """Extract methods from a class"""
        methods = []
        if not filepath.exists():
            return methods
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the class definition
            class_pattern = rf"class\s+{class_name}[:\(]"
            class_match = re.search(class_pattern, content)
            
            if class_match:
                # Get content after class definition
                class_start = class_match.start()
                
                # Find next class or end of file
                next_class_pattern = r"\nclass\s+\w+"
                next_class_match = re.search(next_class_pattern, content[class_start + 10:])
                
                if next_class_match:
                    class_content = content[class_start:class_start + 10 + next_class_match.start()]
                else:
                    class_content = content[class_start:]
                
                # Extract methods
                method_pattern = r"def\s+(\w+)\s*\("
                all_methods = re.findall(method_pattern, class_content)
                # Filter out private methods and __init__
                methods = [m for m in all_methods if not m.startswith('_') or m == '__init__']
                
        except Exception as e:
            print(f"      Error reading {filepath}: {e}")
        
        return methods
    
    def run_checks(self) -> Dict:
        """Run all implementation checks"""
        print("=" * 80)
        print("FACE RECOGNITION SYSTEM - IMPLEMENTATION CHECKER")
        print("=" * 80)
        print(f"Script Location: {Path(__file__).absolute()}")
        print(f"Current Directory: {Path.cwd()}")
        print(f"Project Root: {self.project_root}")
        print(f"App Directory: {self.app_dir}")
        print(f"App Exists: {self.app_dir.exists()}")
        
        # Verify we found the right location
        if not self.app_dir.exists():
            print("\n⚠️  WARNING: 'app' directory not found!")
            print(f"   Expected: {self.app_dir}")
            print("\n   Please run this script from the lec_panel directory or")
            print("   provide the correct path: python verify_implementation.py /path/to/lec_panel")
        print()
        
        # Critical Files
        critical_files = {
            'socket_io_events.py': 'app/socket_io_events.py',
            'face_recognition_service.py': 'app/services/face_recognition_service.py',
            'camera_service.py': 'app/services/camera_service.py',
            'face_processing.py': 'app/tasks/face_processing.py',
        }
        
        print("1. CHECKING CRITICAL FILES")
        print("-" * 80)
        for name, path in critical_files.items():
            exists, full_path = self.check_file_exists(path)
            status = "✅ EXISTS" if exists else "❌ MISSING"
            print(f"{status:15} {name}")
            
            if exists:
                # Show file size
                size = full_path.stat().st_size
                print(f"                → {full_path}")
                print(f"                → Size: {size:,} bytes")
            
            self.results['files'][name] = {
                'exists': exists,
                'path': str(full_path),
                'size': full_path.stat().st_size if exists else 0
            }
            
            if not exists:
                self.results['missing'].append(path)
        print()
        
        # Socket.IO Handlers
        print("2. CHECKING SOCKET.IO EVENT HANDLERS")
        print("-" * 80)
        socketio_exists, socketio_file = self.check_file_exists('app/socket_io_events.py')
        
        if socketio_exists:
            handlers = self.check_socketio_events(socketio_file)
            
            required_handlers = [
                'join_session',
                'leave_session',
                'process_frame',
                'start_recognition',
                'stop_recognition',
                'mark_attendance_manual',
                'request_session_stats',
                'session_heartbeat'
            ]
            
            if handlers:
                print(f"Found {len(handlers)} handler(s):")
                for handler in sorted(handlers):
                    is_required = handler in required_handlers
                    marker = "✅" if is_required else "ℹ️"
                    print(f"  {marker} @socketio.on('{handler}')")
                
                # Check missing required handlers
                missing_handlers = set(required_handlers) - set(handlers)
                if missing_handlers:
                    print(f"\n⚠️  Missing required handlers:")
                    for handler in sorted(missing_handlers):
                        print(f"  ❌ @socketio.on('{handler}')")
            else:
                print("⚠️  No Socket.IO handlers found in file")
            
            self.results['socketio_handlers'] = handlers
        else:
            print("❌ socket_io_events.py file not found")
            self.results['socketio_handlers'] = []
        print()
        
        # Celery Tasks
        print("3. CHECKING CELERY BACKGROUND TASKS")
        print("-" * 80)
        tasks_exists, tasks_file = self.check_file_exists('app/tasks/face_processing.py')
        
        if tasks_exists:
            tasks = self.check_celery_tasks(tasks_file)
            
            required_tasks = [
                'process_frame_task',
                'recognize_face_task',
                'mark_attendance_task',
                'save_unknown_face_task',
                'preload_class_faces_task'
            ]
            
            if tasks:
                print(f"Found {len(tasks)} task(s):")
                for task in sorted(tasks):
                    is_required = task in required_tasks
                    marker = "✅" if is_required else "ℹ️"
                    print(f"  {marker} @shared_task {task}()")
                
                # Check missing required tasks
                missing_tasks = set(required_tasks) - set(tasks)
                if missing_tasks:
                    print(f"\n⚠️  Missing required tasks:")
                    for task in sorted(missing_tasks):
                        print(f"  ❌ {task}")
            else:
                print("⚠️  No Celery tasks found in file")
            
            self.results['celery_tasks'] = tasks
        else:
            print("❌ face_processing.py file not found")
            self.results['celery_tasks'] = []
        print()
        
        # Face Recognition Service
        print("4. CHECKING FACE RECOGNITION SERVICE")
        print("-" * 80)
        face_exists, face_service_file = self.check_file_exists('app/services/face_recognition_service.py')
        
        if face_exists:
            face_methods = self.check_class_methods(face_service_file, 'FaceRecognitionService')
            
            required_methods = [
                'recognize_faces_in_frame',
                'extract_face_encoding_from_array',
                'load_known_faces',
                'compare_faces',
                'mark_attendance',
                'get_cache_stats'
            ]
            
            if face_methods:
                print(f"Found {len(face_methods)} method(s) in FaceRecognitionService:")
                for method in sorted(face_methods):
                    is_required = method in required_methods
                    marker = "✅" if is_required else "ℹ️"
                    print(f"  {marker} {method}()")
                
                # Check missing required methods
                missing_methods = set(required_methods) - set(face_methods)
                if missing_methods:
                    print(f"\n⚠️  Missing required methods:")
                    for method in sorted(missing_methods):
                        print(f"  ❌ {method}()")
            else:
                print("⚠️  No methods found in FaceRecognitionService")
            
            self.results['service_methods']['FaceRecognitionService'] = face_methods
        else:
            print("❌ face_recognition_service.py file not found")
            self.results['service_methods']['FaceRecognitionService'] = []
        print()
        
        # Camera Service
        print("5. CHECKING CAMERA SERVICE")
        print("-" * 80)
        camera_exists, camera_service_file = self.check_file_exists('app/services/camera_service.py')
        
        if camera_exists:
            camera_methods = self.check_class_methods(camera_service_file, 'CameraService')
            
            required_methods = [
                'register_session',
                'unregister_session',
                'decode_frame',
                'validate_frame',
                'process_frame',
                'get_session_stats'
            ]
            
            if camera_methods:
                print(f"Found {len(camera_methods)} method(s) in CameraService:")
                for method in sorted(camera_methods):
                    is_required = method in required_methods
                    marker = "✅" if is_required else "ℹ️"
                    print(f"  {marker} {method}()")
                
                # Check missing required methods
                missing_methods = set(required_methods) - set(camera_methods)
                if missing_methods:
                    print(f"\n⚠️  Missing required methods:")
                    for method in sorted(missing_methods):
                        print(f"  ❌ {method}()")
            else:
                print("⚠️  No methods found in CameraService")
            
            self.results['service_methods']['CameraService'] = camera_methods
        else:
            print("❌ camera_service.py file not found")
            self.results['service_methods']['CameraService'] = []
        print()
        
        # JavaScript Files
        print("6. CHECKING FRONTEND JAVASCRIPT FILES")
        print("-" * 80)
        js_files = {
            'camera_handler.js': 'app/static/js/camera_handler.js',
            'attendance_realtime.js': 'app/static/js/attendance_realtime.js',
            'progress_tracker.js': 'app/static/js/progress_tracker.js',
            'diagnostics.js': 'app/static/js/diagnostics.js'
        }
        
        for name, path in js_files.items():
            exists, full_path = self.check_file_exists(path)
            status = "✅" if exists else "❌"
            print(f"  {status} {name}")
            if exists:
                size = full_path.stat().st_size
                print(f"      Size: {size:,} bytes")
        print()
        
        # Summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        total_files = len(critical_files)
        existing_files = sum(1 for f in self.results['files'].values() if f['exists'])
        
        socketio_count = len(self.results['socketio_handlers'])
        celery_count = len(self.results['celery_tasks'])
        face_methods_count = len(self.results['service_methods'].get('FaceRecognitionService', []))
        camera_methods_count = len(self.results['service_methods'].get('CameraService', []))
        
        print(f"Critical Files:    {existing_files}/{total_files} exist")
        print(f"Socket.IO:         {socketio_count} handlers found")
        print(f"Celery Tasks:      {celery_count} tasks found")
        print(f"Face Service:      {face_methods_count} methods found")
        print(f"Camera Service:    {camera_methods_count} methods found")
        
        if self.results['missing']:
            print(f"\n⚠️  MISSING FILES:")
            for missing in self.results['missing']:
                print(f"  ❌ {missing}")
        
        # Determine system status
        print()
        if existing_files == total_files and socketio_count >= 5 and celery_count >= 3:
            print("✅ SYSTEM STATUS: Fully Implemented")
            print("   All critical components are in place!")
        elif existing_files >= 3:
            print("⚠️  SYSTEM STATUS: Partially Implemented")
            print("   Some components are missing or incomplete")
        else:
            print("❌ SYSTEM STATUS: Missing Critical Components")
            print("   Major components need to be implemented")
        
        print("=" * 80)
        
        return self.results


def main():
    """Main entry point"""
    print("Starting Implementation Verification...\n")
    
    # Get project root
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
        print(f"Using provided project root: {project_root}\n")
    else:
        project_root = None
        print("Auto-detecting project root...\n")
    
    try:
        checker = ImplementationChecker(project_root)
        results = checker.run_checks()
        
        # Save results to JSON
        import json
        output_file = checker.project_root / 'implementation_check_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📄 Results saved to: {output_file}")
        
    except Exception as e:
        print(f"\n❌ Error running verification: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())