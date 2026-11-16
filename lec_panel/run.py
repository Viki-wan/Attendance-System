"""
Flask Attendance System - Application Entry Point
Run with: python run.py

Fixed for Windows + WSL2 port reservation issues
Uses port 8080 by default to avoid Hyper-V reserved ports
"""

import os
import sys
from app import create_app, socketio

# Get configuration from environment
config_name = os.environ.get('FLASK_CONFIG') or 'development'

# Create app instance
app = create_app(config_name)

def get_port():
    """Get port from environment or use safe default"""
    try:
        port = int(os.environ.get('PORT', 8080))
        # Validate port range
        if not (1024 <= port <= 65535):
            print(f"Warning: Invalid port {port}, using 8080")
            return 8080
        return port
    except ValueError:
        print("Warning: Invalid PORT value, using 8080")
        return 8080

def get_host():
    """Get host from environment or use safe default"""
    # Use 127.0.0.1 for development (more secure and avoids some Windows issues)
    # Use 0.0.0.0 if you need to access from other devices on network
    return os.environ.get('HOST', '127.0.0.1')

if __name__ == '__main__':
    port = get_port()
    host = get_host()
    
    print("=" * 60)
    print("Flask Attendance System")
    print("=" * 60)
    print(f"Environment: {config_name}")
    print(f"Debug Mode: {app.config['DEBUG']}")
    print(f"Server: http://{host}:{port}")
    print(f"Redis: {app.config.get('REDIS_URL', 'Not configured')}")
    print("=" * 60)
    print("\nPress CTRL+C to stop the server\n")
    
    try:
        # Run with SocketIO support
        socketio.run(
            app,
            host=host,
            port=port,
            debug=app.config['DEBUG'],
            use_reloader=app.config['DEBUG'],
            log_output=True,
            allow_unsafe_werkzeug=True  # For development only
        )
    except OSError as e:
        if "access" in str(e).lower() or "permission" in str(e).lower():
            print("\n" + "=" * 60)
            print("ERROR: Port Access Denied")
            print("=" * 60)
            print(f"Cannot bind to {host}:{port}")
            print("\nThis is likely due to Windows/Hyper-V port reservation.")
            print("\nSolutions:")
            print("1. Try a different port:")
            print(f"   set PORT=10000 && python run.py")
            print("\n2. Or fix Windows port reservation (run PowerShell as Admin):")
            print("   net stop winnat")
            print(f"   netsh int ipv4 add excludedportrange protocol=tcp startport={port} numberofports=10 store=persistent")
            print("   net start winnat")
            print("=" * 60)
            sys.exit(1)
        else:
            raise
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        sys.exit(0)