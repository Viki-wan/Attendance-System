# Face Recognition Setup Guide

This guide covers the installation, configuration, and optimization of the face recognition system.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Model Setup](#model-setup)
- [Configuration](#configuration)
- [Encoding Storage](#encoding-storage)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Components

- **Python 3.8+** (Python 3.12.7 recommended for Windows)
- **CMake** (for building dlib from source, if needed)
- **Visual C++ Build Tools** (Windows) or **gcc** (Linux/Mac)
- **Webcam** with minimum 640x480 resolution
- **Adequate lighting** (minimum 50 lux, recommended 200+ lux)

### System Requirements

- **CPU**: Multi-core processor recommended (face recognition is CPU-intensive)
- **RAM**: Minimum 4GB, 8GB+ recommended
- **Storage**: ~500MB for face recognition models and libraries

## Installation

### Step 1: Install Base Dependencies

```bash
pip install numpy opencv-python opencv-contrib-python
```

### Step 2: Install dlib

**Windows (Python 3.12.7 - Recommended Approach):**

1. Download prebuilt wheel from [unofficial Windows binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#dlib)
2. Install the wheel:
   ```bash
   pip install dlib-19.24.0-cp312-cp312-win_amd64.whl
   ```

**Alternative (Prebuilt wheel via pip):**
```bash
pip install --only-binary=:all: dlib
```

**Linux:**
```bash
sudo apt-get install cmake libopenblas-dev liblapack-dev
pip install dlib
```

**Mac:**
```bash
brew install cmake
pip install dlib
```

### Step 3: Install face_recognition

```bash
pip install face_recognition
```

**Important**: Ensure `setuptools` is up to date:
```bash
pip install --upgrade setuptools
```

### Step 4: Download Face Recognition Models

The `face_recognition` library will automatically download models on first import. Models are stored in:

- **Windows**: `C:\Users\<username>\.face_recognition_models\`
- **Linux/Mac**: `~/.face_recognition_models/`

Models are approximately 100MB total.

### Step 5: Verify Installation

```python
python -c "import face_recognition; import cv2; print('Installation successful!')"
```

If you see "Installation successful!", you're ready to go!

## Model Setup

### Model Types

The system supports two face detection models:

1. **HOG (Histogram of Oriented Gradients)** - Default
   - Faster processing (~100ms per frame)
   - Lower accuracy (~95%)
   - CPU-only, no GPU required
   - Recommended for: Real-time processing, low-end hardware

2. **CNN (Convolutional Neural Network)** - Optional
   - Slower processing (~500ms per frame)
   - Higher accuracy (~99%)
   - GPU acceleration possible
   - Recommended for: High accuracy requirements, batch processing

### Changing Models

**In Admin Panel:**
1. Open Settings → Face Recognition
2. Change "Recognition Model" from `hog` to `cnn`
3. Restart the application

**In Flask Config:**
```python
# lec_panel/config/config.py
FACE_RECOGNITION_MODEL = 'cnn'  # or 'hog'
```

**In Code:**
```python
# For face detection
face_locations = face_recognition.face_locations(rgb_image, model='cnn')

# For face encoding
encodings = face_recognition.face_encodings(rgb_image, known_face_locations, model='large')
```

## Configuration

### Recognition Sensitivity

Controls how strict face matching is:

- **Lower values (0.3-0.5)**: More strict, fewer false positives
- **Higher values (0.6-0.8)**: More lenient, may have false positives

**Default**: 0.6 (60% similarity required)

**Changing Sensitivity:**

Admin Panel:
1. Settings → Face Recognition → Sensitivity
2. Adjust slider (1-100, default 50 = 0.5 threshold)

Config File:
```python
FACE_RECOGNITION_TOLERANCE = 0.6  # 0.0 to 1.0
```

Database Settings:
```python
Setting.set('face_recognition_sensitivity', '60')  # 0-100 scale
```

### Minimum Face Size

Faces smaller than this threshold are ignored:

```python
MIN_FACE_SIZE = 100  # pixels (width or height)
```

**Recommendations:**
- **640x480 video**: 100 pixels
- **1280x720 video**: 150 pixels
- **1920x1080 video**: 200 pixels

### Camera Settings

```python
# lec_panel/config/config.py
CAMERA_RESOLUTION = (640, 480)  # Width, Height
CAMERA_FPS = 30
FRAME_PROCESS_INTERVAL = 500  # milliseconds (2 FPS processing)
```

**Processing FPS vs Video FPS:**
- Video captures at 30 FPS
- Face recognition processes at 2 FPS (every 500ms)
- This reduces CPU load while maintaining responsiveness

## Encoding Storage

### Storage Locations

The system checks multiple locations for face encodings:

1. **Old Format** (backward compatibility):
   ```
   face_encodings/student_S11_10067_25_encodings.pkl
   ```

2. **New Format** (recommended):
   ```
   lec_panel/uploads/encodings/S11_10067_25.pkl
   ```

3. **Database BLOB**:
   - Stored in `students.face_encoding` column
   - Automatically saved during registration

### Encoding Format

**Old Format** (list of encodings):
```python
# List of numpy arrays
encodings = [encoding1, encoding2, encoding3]
```

**New Format** (single encoding):
```python
# Single numpy array (128-dimensional)
encoding = np.array([...])
```

The system automatically converts between formats.

### Encoding Structure

Each face encoding is a 128-dimensional vector:
- Normalized to unit length
- Generated using `face_recognition` library
- Unique to each individual face

### Manual Encoding Management

**Export encodings:**
```python
import pickle
import numpy as np

# Load encoding
with open('encoding.pkl', 'rb') as f:
    encoding = pickle.load(f)

# Export as JSON (for external use)
encoding_list = encoding.tolist()
import json
json.dump(encoding_list, open('encoding.json', 'w'))
```

**Import encodings:**
```python
import pickle
import numpy as np

# From numpy array
encoding = np.array(encoding_data)

# Save
with open('encoding.pkl', 'wb') as f:
    pickle.dump(encoding, f)
```

## Performance Optimization

### Caching Face Encodings

The system uses in-memory caching to avoid reloading encodings:

```python
# Cache duration: 1 hour
_CACHE_TIMEOUT = 3600  # seconds

# Cache key: class_id or 'all'
_face_encoding_cache = {
    'class_123': (encodings, student_ids, timestamp),
    'all': (encodings, student_ids, timestamp)
}
```

**Benefits:**
- Reduces database/disk reads
- Faster frame processing
- Lower memory usage (single copy per class)

### Processing Optimization

1. **Limit faces per frame:**
   ```python
   MAX_FACES_PER_FRAME = 5  # Process only first 5 faces
   ```

2. **Skip frames with poor quality:**
   - Low brightness (< 20)
   - High blur (< 100 Laplacian variance)
   - Too dark or too bright

3. **Use Celery for async processing:**
   - Prevents blocking the web server
   - Allows parallel processing
   - Scales horizontally

### Hardware Recommendations

**Minimum:**
- Dual-core CPU
- 4GB RAM
- Integrated GPU (for CNN model)

**Recommended:**
- Quad-core CPU or better
- 8GB+ RAM
- Dedicated GPU (NVIDIA, for CNN model)
- SSD storage (faster encoding loading)

**Optimal:**
- 8+ core CPU
- 16GB+ RAM
- High-end GPU (NVIDIA RTX series)
- NVMe SSD

## Troubleshooting

### Issue: "dlib build failed - No CMAKE_C_COMPILER found"

**Solution:**
1. Install Visual C++ Build Tools (Windows)
2. Or use Python 3.12.7 with prebuilt wheels:
   ```bash
   pip install --only-binary=:all: dlib
   ```

### Issue: "ModuleNotFoundError: No module named 'face_recognition_models'"

**Solution:**
1. Upgrade setuptools:
   ```bash
   pip install --upgrade setuptools
   ```
2. Models download automatically on first import
3. Check internet connection (first-time download required)

### Issue: Face recognition not detecting faces

**Checklist:**
- [ ] Adequate lighting (minimum 50 lux)
- [ ] Face is clearly visible and centered
- [ ] Face size is above minimum threshold (100px)
- [ ] Camera is focused and not blurry
- [ ] No obstructions (masks, sunglasses, etc.)

**Debug:**
```python
# Test face detection
import face_recognition
from PIL import Image

image = face_recognition.load_image_file("test.jpg")
face_locations = face_recognition.face_locations(image)

print(f"Found {len(face_locations)} face(s)")
```

### Issue: Low recognition accuracy

**Solutions:**

1. **Improve image quality:**
   - Higher resolution (1920x1080 recommended)
   - Better lighting
   - Sharp focus

2. **Adjust sensitivity:**
   - Lower threshold for stricter matching
   - Higher threshold for lenient matching

3. **Use better model:**
   - Switch from HOG to CNN model
   - Use 'large' encoding model

4. **Re-register students:**
   - Capture multiple angles
   - Use consistent lighting
   - Update encodings periodically

### Issue: Slow processing

**Optimizations:**
1. Reduce processing FPS (increase `FRAME_PROCESS_INTERVAL`)
2. Lower camera resolution
3. Use HOG instead of CNN model
4. Limit number of faces processed per frame
5. Ensure Celery worker is running (async processing)

### Issue: Encoding files not loading

**Check:**
1. File paths in `config/config.py`:
   ```python
   FACE_ENCODINGS_FOLDER = BASE_DIR / 'face_encodings'
   ```

2. File naming convention:
   - Old: `student_S11_10067_25_encodings.pkl`
   - New: `S11_10067_25.pkl`

3. File permissions (read access)

4. Run diagnostic:
   ```bash
   cd lec_panel
   python test_encoding_loading.py
   ```

## Best Practices

1. **Image Quality:**
   - Use consistent lighting for registration and recognition
   - Capture face from front angle (0-15° deviation)
   - Ensure face occupies 20-40% of image
   - Use neutral expression during registration

2. **Registration:**
   - Capture 3-5 images per student (different angles/expressions)
   - Use high-resolution images (1920x1080 minimum)
   - Verify face is detected before saving

3. **Recognition:**
   - Maintain good lighting conditions
   - Position camera at eye level
   - Allow 2-3 seconds for recognition
   - Update encodings if student's appearance changes significantly

4. **Performance:**
   - Process frames at 2 FPS (sufficient for attendance)
   - Use caching for frequently accessed encodings
   - Monitor CPU usage and adjust settings accordingly
   - Use Celery for production workloads

5. **Maintenance:**
   - Periodically re-register students (yearly)
   - Update encodings if recognition accuracy drops
   - Monitor unknown face reports for quality issues
   - Backup encoding files regularly

## Additional Resources

- [face_recognition Library Documentation](https://github.com/ageitgey/face_recognition)
- [dlib Documentation](http://dlib.net/)
- [OpenCV Face Recognition Tutorial](https://docs.opencv.org/4.x/da/d60/tutorial_face_main.html)

---

**Need Help?** Check the main [Troubleshooting Guide](../docs/TROUBLESHOOTING.md) or open an issue on GitHub.

