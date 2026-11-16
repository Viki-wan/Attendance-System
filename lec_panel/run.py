"""
Flask Attendance System - Application Entry Point
Run with: python run.py

Fixed for Windows + WSL2 port reservation issues
Uses port 10000 by default (8080 is often reserved by Hyper-V/WinNAT)
"""

import os
import socket
import sys
from app import create_app, socketio

# Get configuration from environment
config_name = os.environ.get('FLASK_CONFIG') or 'development'

# Create app instance
app = create_app(config_name)

def get_port():
    """Get port from environment or use safe default"""
    try:
        port = int(os.environ.get('PORT', 10000))
        if not (1024 <= port <= 65535):
            print(f"Warning: Invalid port {port}, using 10000")
            return 10000
        return port
    except ValueError:
        print("Warning: Invalid PORT value, using 10000")
        return 10000


def port_is_bindable(host, port):
    """Return True if we can bind TCP on host:port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def resolve_port(host, preferred):
    """Use preferred port, otherwise first fallback that Windows will allow."""
    candidates = [preferred, 10000, 3000, 8888, 5001]
    seen = set()
    for port in candidates:
        if port in seen:
            continue
        seen.add(port)
        if port_is_bindable(host, port):
            if port != preferred:
                print(f"Port {preferred} is blocked; using {port} instead")
            return port
    return preferred

def get_host():
    """Get host from environment or use safe default"""
    # Use 127.0.0.1 for development (more secure and avoids some Windows issues)
    # Use 0.0.0.0 if you need to access from other devices on network
    return os.environ.get('HOST', '127.0.0.1')

if __name__ == '__main__':
    host = get_host()
    port = resolve_port(host, get_port())
    
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
        # Keep this simple while we debug: no reloader, no debug spam, no raw packet logs
        socketio.run(
            app,
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
            log_output=False,
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