# Troubleshooting Guide

Common issues and solutions for the Face Recognition Attendance System.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Face Recognition Issues](#face-recognition-issues)
- [Web Application Issues](#web-application-issues)
- [Database Issues](#database-issues)
- [Performance Issues](#performance-issues)
- [Network & Connectivity](#network--connectivity)
- [Camera Issues](#camera-issues)

## Installation Issues

### Issue: "No module named 'face_recognition'"

**Symptoms:**
```
ModuleNotFoundError: No module named 'face_recognition'
```

**Solutions:**
1. Ensure virtual environment is activated:
   ```bash
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

2. Install face_recognition:
   ```bash
   pip install face_recognition
   ```

3. Verify installation:
   ```bash
   python -c "import face_recognition; print('OK')"
   ```

### Issue: "dlib build failed - No CMAKE_C_COMPILER found"

**Symptoms:**
```
ERROR: Failed building wheel for dlib
CMake Error: No CMAKE_C_COMPILER could be found
```

**Solutions:**

**Windows:**
1. Install Visual C++ Build Tools
2. Or use Python 3.12.7 with prebuilt wheels:
   ```bash
   pip install --only-binary=:all: dlib face_recognition
   ```

**Linux:**
```bash
sudo apt-get install cmake libopenblas-dev liblapack-dev
pip install dlib
```

### Issue: "ModuleNotFoundError: No module named 'dotenv'"

**Symptoms:**
```
ModuleNotFoundError: No module named 'dotenv'
```

**Solution:**
```bash
pip install python-dotenv
```

### Issue: "ModuleNotFoundError: No module named 'pkg_resources'"

**Symptoms:**
```
ModuleNotFoundError: No module named 'pkg_resources'
```

**Solution:**
```bash
pip install --upgrade setuptools
```

### Issue: "Port already in use" or "Port access denied"

**Symptoms:**
```
OSError: [Errno 48] Address already in use
An attempt was made to access a socket in a way forbidden by its access permissions
```

**Solutions:**

1. **Use a different port:**
   ```powershell
   # Windows PowerShell
   $env:PORT = "10000"
   python run.py
   ```

   ```bash
   # Linux/Mac
   export PORT=10000
   python run.py
   ```

2. **Find and kill process using the port:**
   ```bash
   # Windows
   netstat -ano | findstr :8080
   taskkill /PID <PID> /F

   # Linux/Mac
   lsof -ti:8080 | xargs kill
   ```

3. **Fix Windows port reservation:**
   ```powershell
   # Run as Administrator
   net stop winnat
   netsh int ipv4 add excludedportrange protocol=tcp startport=8080 numberofports=10
   net start winnat
   ```

## Face Recognition Issues

### Issue: Face recognition not working / No faces detected

**Symptoms:**
- Camera feed shows but no recognition happens
- "No faces detected" message
- Students not being recognized

**Solutions:**

1. **Check camera permissions:**
   - Browser: Allow camera access when prompted
   - Check browser settings for blocked permissions

2. **Verify lighting:**
   - Ensure adequate lighting (minimum 50 lux)
   - Avoid backlighting
   - Use even, diffused lighting

3. **Check face encoding loading:**
   ```bash
   cd lec_panel
   python test_encoding_loading.py
   ```

4. **Verify students have face encodings:**
   - Check database: `SELECT student_id FROM students WHERE face_encoding IS NOT NULL;`
   - Check encoding files in `face_encodings/` directory
   - Re-register students if encodings are missing

5. **Check Celery worker:**
   - Ensure Celery worker is running:
     ```bash
     celery -A celery_worker.celery worker --loglevel=info --pool=solo
     ```
   - Check worker logs for errors

6. **Browser console errors:**
   - Open DevTools (F12)
   - Check Console tab for JavaScript errors
   - Check Network tab for failed requests

### Issue: Low recognition accuracy / False positives

**Symptoms:**
- Wrong students being recognized
- Students not recognized correctly
- High number of unknown faces

**Solutions:**

1. **Adjust sensitivity threshold:**
   - Admin Panel → Settings → Face Recognition → Sensitivity
   - Lower value = more strict (fewer false positives)
   - Higher value = more lenient (may increase false positives)

2. **Re-register students:**
   - Use high-quality images (1920x1080 recommended)
   - Capture from front angle (0-15°)
   - Ensure good lighting
   - Capture multiple images per student

3. **Check image quality:**
   - Ensure sharp focus
   - Avoid motion blur
   - Use consistent lighting

4. **Update face encodings:**
   - If student's appearance changed significantly
   - Periodically refresh encodings (yearly)

### Issue: "face_recognition_models" warning

**Symptoms:**
```
Could not find models file. Please check the installation...
```

**Note:** This is usually a harmless warning. Models are downloaded automatically.

**Solution:**
1. Verify models directory exists:
   - Windows: `C:\Users\<username>\.face_recognition_models\`
   - Linux/Mac: `~/.face_recognition_models/`

2. Models download automatically on first import
3. Check internet connection (required for first download)

### Issue: Encoding files not loading

**Symptoms:**
- "No face encodings found" error
- Students not in recognition database

**Solutions:**

1. **Check file paths:**
   ```python
   # Verify paths in config/config.py
   FACE_ENCODINGS_FOLDER = BASE_DIR / 'face_encodings'
   ```

2. **Verify file naming:**
   - Old format: `student_S11_10067_25_encodings.pkl`
   - New format: `S11_10067_25.pkl`

3. **Run diagnostic script:**
   ```bash
   cd lec_panel
   python test_encoding_loading.py
   ```

4. **Check file permissions:**
   ```bash
   # Linux/Mac
   ls -la face_encodings/
   chmod 644 face_encodings/*.pkl
   ```

5. **Verify encoding format:**
   - Ensure pickle files are valid
   - Check file size (should be ~1KB per encoding)

## Web Application Issues

### Issue: Flask app exits immediately without error

**Symptoms:**
- App starts but immediately returns to prompt
- No error messages displayed

**Solutions:**

1. **Check run.py configuration:**
   ```python
   socketio.run(
       app,
       debug=False,  # Set to False
       use_reloader=False,  # Set to False
       log_output=False
   )
   ```

2. **Add error handling:**
   ```python
   try:
       socketio.run(app, ...)
   except Exception as e:
       import traceback
       traceback.print_exc()
   ```

3. **Check logs:**
   - Check `logs/app.log` for errors
   - Check console output

### Issue: "Celery not recognized" error

**Symptoms:**
```
'celery' is not recognized as an internal or external command
```

**Solutions:**

1. **Activate virtual environment:**
   ```bash
   venv\Scripts\activate  # Windows
   ```

2. **Install Celery:**
   ```bash
   pip install celery
   ```

3. **Use Python module syntax:**
   ```bash
   python -m celery -A celery_worker.celery worker --loglevel=info --pool=solo
   ```

### Issue: WebSocket connection fails

**Symptoms:**
- "WebSocket connection failed"
- Real-time updates not working
- Socket.IO errors in browser console

**Solutions:**

1. **Check Socket.IO server:**
   - Ensure Flask-SocketIO is properly configured
   - Check `socketio.init_app()` in `app/__init__.py`

2. **Verify WebSocket support:**
   - Check browser console for errors
   - Try different browser
   - Check firewall/proxy settings

3. **Check Nginx configuration** (if using):
   - Ensure WebSocket proxying is configured:
     ```nginx
     location /socket.io {
         proxy_pass http://127.0.0.1:5000;
         proxy_http_version 1.1;
         proxy_set_header Upgrade $http_upgrade;
         proxy_set_header Connection "upgrade";
     }
     ```

### Issue: 404 errors for routes

**Symptoms:**
- Routes return 404 Not Found
- API endpoints not accessible

**Solutions:**

1. **Check blueprint registration:**
   - Verify blueprints are registered in `app/__init__.py`
   - Check URL prefixes

2. **Verify route patterns:**
   - Check route definitions match URLs being accessed
   - Ensure trailing slashes match

3. **Check URL construction:**
   - Use `url_for()` for generating URLs
   - Verify route names match

### Issue: "Binary slop" in Flask terminal

**Symptoms:**
- Raw WebSocket packet data printed to console
- Unreadable binary characters

**Solution:**
Disable Socket.IO logging in `app/__init__.py`:
```python
socketio.init_app(app, logger=False, engineio_logger=False)
```

## Database Issues

### Issue: "Database is locked"

**Symptoms:**
- SQLite database lock errors
- Cannot write to database

**Solutions:**

1. **Check for open connections:**
   - Ensure all database connections are closed
   - Use connection pooling properly

2. **Use WAL mode** (SQLite):
   ```python
   # In config
   SQLALCHEMY_DATABASE_URI = 'sqlite:///attendance.db?check_same_thread=False'
   ```

3. **Check file permissions:**
   ```bash
   chmod 664 attendance.db
   ```

4. **Consider PostgreSQL** for production (better concurrency)

### Issue: Migration errors

**Symptoms:**
- Flask-Migrate errors
- Database schema mismatches

**Solutions:**

1. **Initialize migrations:**
   ```bash
   flask db init
   ```

2. **Create migration:**
   ```bash
   flask db migrate -m "Description"
   ```

3. **Apply migrations:**
   ```bash
   flask db upgrade
   ```

4. **Reset migrations** (if needed):
   ```bash
   flask db downgrade base
   flask db upgrade
   ```

### Issue: Database file not found

**Symptoms:**
- Database file missing or not created

**Solution:**
```bash
# Create database tables
cd lec_panel
flask db upgrade

# Or manually:
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

## Performance Issues

### Issue: Slow face recognition processing

**Symptoms:**
- High latency in recognition
- System lagging during attendance

**Solutions:**

1. **Reduce processing FPS:**
   ```python
   FRAME_PROCESS_INTERVAL = 500  # Process every 500ms (2 FPS)
   ```

2. **Limit faces per frame:**
   ```python
   MAX_FACES_PER_FRAME = 5
   ```

3. **Use HOG model instead of CNN:**
   ```python
   FACE_RECOGNITION_MODEL = 'hog'  # Faster than 'cnn'
   ```

4. **Reduce camera resolution:**
   ```python
   CAMERA_RESOLUTION = (640, 480)  # Lower resolution
   ```

5. **Enable Celery for async processing:**
   - Ensure Celery worker is running
   - Use Redis for message queue

6. **Optimize encoding cache:**
   - Ensure encodings are cached in memory
   - Preload encodings for active sessions

### Issue: High memory usage

**Symptoms:**
- System running out of memory
- Application crashes

**Solutions:**

1. **Limit encoding cache size:**
   - Clear cache periodically
   - Load encodings per class, not all at once

2. **Reduce worker processes:**
   ```python
   # Gunicorn
   workers = 2  # Reduce from 4
   ```

3. **Monitor memory usage:**
   ```bash
   # Linux
   htop
   # Windows
   Task Manager
   ```

### Issue: Slow database queries

**Symptoms:**
- Long loading times
- Timeout errors

**Solutions:**

1. **Add database indexes:**
   ```bash
   flask db migrate -m "Add indexes"
   ```

2. **Use connection pooling:**
   - Already configured in SQLAlchemy settings
   - Adjust pool size if needed

3. **Enable query caching:**
   - Use Redis cache for frequent queries
   - Cache dashboard statistics

4. **Optimize queries:**
   - Use eager loading for relationships
   - Add appropriate filters

## Network & Connectivity

### Issue: Redis connection failed

**Symptoms:**
- "Connection refused" errors
- Cache not working

**Solutions:**

1. **Check Redis is running:**
   ```bash
   # Linux
   sudo systemctl status redis
   sudo systemctl start redis

   # Windows
   # Start Redis service manually
   ```

2. **Verify Redis configuration:**
   ```python
   REDIS_HOST = 'localhost'
   REDIS_PORT = 6379
   ```

3. **Test connection:**
   ```python
   import redis
   r = redis.Redis(host='localhost', port=6379)
   r.ping()  # Should return True
   ```

### Issue: Cannot access application from network

**Symptoms:**
- Application works on localhost but not from other devices

**Solutions:**

1. **Change host binding:**
   ```python
   HOST = '0.0.0.0'  # Instead of '127.0.0.1'
   ```

2. **Check firewall:**
   ```bash
   # Linux
   sudo ufw allow 8080/tcp

   # Windows
   # Add firewall rule in Windows Firewall
   ```

3. **Use proper domain/IP:**
   - Access via server IP address or domain name
   - Not via localhost from remote device

## Camera Issues

### Issue: Camera not accessible in browser

**Symptoms:**
- "Camera permission denied"
- No video feed

**Solutions:**

1. **Grant camera permissions:**
   - Browser will prompt for permission
   - Check browser settings if denied

2. **Use HTTPS:**
   - Modern browsers require HTTPS for camera access
   - Use SSL certificate in production

3. **Check camera availability:**
   ```javascript
   navigator.mediaDevices.getUserMedia({ video: true })
     .then(stream => console.log('Camera OK'))
     .catch(err => console.error('Camera error:', err));
   ```

4. **Try different browser:**
   - Chrome/Edge recommended
   - Firefox also works
   - Safari may have limitations

### Issue: Poor video quality

**Symptoms:**
- Blurry video feed
- Low resolution

**Solutions:**

1. **Increase camera resolution:**
   ```javascript
   const constraints = {
     video: {
       width: { ideal: 1280 },
       height: { ideal: 720 }
     }
   };
   ```

2. **Check camera settings:**
   - Adjust focus
   - Check lighting
   - Clean camera lens

3. **Adjust frame quality:**
   ```javascript
   canvas.toDataURL('image/jpeg', 0.85);  // Higher quality (0.85)
   ```

## Getting More Help

### Debug Mode

Enable debug mode for detailed error messages:
```python
DEBUG = True
FLASK_CONFIG = 'development'
```

### Log Files

Check log files for detailed error information:
- `logs/app.log` - Application logs
- `logs/error.log` - Error logs
- Browser console (F12) - Client-side errors

### Diagnostic Scripts

Run diagnostic scripts:
```bash
# Test encoding loading
python lec_panel/test_encoding_loading.py

# Test Redis connection
python lec_panel/test_redis.py
```

### Common Log Locations

- Application logs: `lec_panel/logs/app.log`
- Celery logs: Check supervisor/systemd logs
- Web server logs: Nginx/Apache logs
- System logs: `/var/log/` (Linux)

---

**Still having issues?** Open an issue on GitHub with:
- Error messages
- System information (OS, Python version)
- Steps to reproduce
- Relevant log excerpts

