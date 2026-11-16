# Debugging Face Encoding Loading

## Where to Look for Logs

### 1. Flask Console (Main Application)
When you run `python run.py`, you should see logs here for:
- Socket.IO events (frame received)
- Flask application logs

### 2. Celery Worker Console
If Celery is running asynchronously, you need a **separate terminal** running:
```bash
celery -A celery_worker.celery worker --loglevel=info --pool=solo
```

The encoding loading logs will appear in **this console**, not the Flask console.

### 3. Test Script (Easiest Way)
Run this to test encoding loading directly:
```bash
cd lec_panel
python test_encoding_loading.py
```

This will show you:
- Which directories are being checked
- How many encoding files were found
- Whether encodings can be loaded

## Quick Diagnostic Steps

### Step 1: Test Encoding Loading
```bash
cd lec_panel
python test_encoding_loading.py
```

This will tell you if encodings can be loaded at all.

### Step 2: Check Flask Console
When frames are received, you should see:
```
📸 Frame #10 received for session X, class Y
✅ Frame #10 queued as task abc123
```

### Step 3: Check Celery Worker (if running async)
If you have a Celery worker running, you should see:
```
🔄 Loading face encodings for class: {class_id}
📁 Encoding directories being checked:
   1. Old format: C:\Users\HP\.vscode\attendance system\face_encodings
...
✅ Loaded X face encodings
```

### Step 4: Check Browser Console
Open browser DevTools (F12) and look for:
- `Processing frame #X...`
- `Frame queued for processing`
- Any error messages

## Common Issues

### No logs appearing?
1. **Check if Celery is in eager mode**: If `CELERY_TASK_ALWAYS_EAGER=True`, tasks run synchronously in Flask console
2. **Check if Celery worker is running**: If `CELERY_TASK_ALWAYS_EAGER=False`, you need a separate Celery worker
3. **Check browser console**: Some errors only show in browser DevTools

### Encoding directory not found?
1. Run `test_encoding_loading.py` to see exact paths being checked
2. Verify the path exists: `C:\Users\HP\.vscode\attendance system\face_encodings`
3. Check file format matches: `student_S11_10067_25_encodings.pkl`

### No encodings loaded?
1. Check that files exist in the directory
2. Check file naming matches student IDs in database
3. Check database for student records

## Expected File Format

- Directory: `C:\Users\HP\.vscode\attendance system\face_encodings`
- Format: `student_{STUDENT_ID}_encodings.pkl`
- Example: `student_S11_10067_25_encodings.pkl`
- Student ID format: `S11/10067/25` (with slashes in DB, underscores in filename)

## Testing in Browser

1. Open browser DevTools (F12) → Console tab
2. Start attendance session
3. Look for messages:
   - `Processing frame #X...`
   - `Frame queued for processing`
   - Any error messages

4. Check Network tab for Socket.IO messages
5. Check if `frame_processing` events are being received


