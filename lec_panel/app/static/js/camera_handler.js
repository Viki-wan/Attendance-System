/**
 * Camera Handler for Web-based Face Recognition
 * Manages WebRTC camera access and frame capture
 */

class CameraHandler {
    constructor(canvasId, options = {}) {
        // CRITICAL FIX: Better canvas element detection
        if (typeof canvasId === 'string') {
            this.canvas = document.getElementById(canvasId);
            if (!this.canvas) {
                // Try querySelector as fallback
                this.canvas = document.querySelector(`#${canvasId}`);
            }
        } else if (canvasId instanceof HTMLCanvasElement) {
            this.canvas = canvasId;
        } else {
            this.canvas = null;
        }
        
        if (!this.canvas) {
            console.error(`Canvas element "${canvasId}" not found in DOM`);
            throw new Error(`Canvas element not found: ${canvasId}`);
        }
        
        // Verify it's actually a canvas
        if (!(this.canvas instanceof HTMLCanvasElement)) {
            throw new Error('Provided element is not a canvas');
        }
        
        this.ctx = this.canvas.getContext('2d');
        if (!this.ctx) {
            throw new Error('Failed to get 2D context from canvas');
        }
        
        console.log('✅ Canvas element found and validated:', this.canvas.id);
        
        // Create hidden video element
        this.video = document.createElement('video');
        this.video.setAttribute('autoplay', '');
        this.video.setAttribute('playsinline', '');
        this.video.style.display = 'none';
        document.body.appendChild(this.video);
        
        this.stream = null;
        this.isActive = false;  // FIX: Changed from this.active
        this.captureInterval = null;
        this.drawingLoop = null;
        
        // Settings
        this.width = options.width || 640;
        this.height = options.height || 480;
        this.fps = options.fps || 10;
        this.frameQuality = 0.85;
        
        // Set canvas size
        this.canvas.width = this.width;
        this.canvas.height = this.height;
        
        // State
        this.frameCount = 0;
        this.devices = [];
        this.currentDeviceIndex = 0;
        
        // Callbacks
        this.onFrame = null;
        this.onError = null;
        
        console.log('✅ CameraHandler initialized successfully');
    }
    
    /**
     * Start camera stream
     */
    async start(deviceId = null) {
        try {
            console.log('Starting camera...');
            
            // Stop existing stream if any
            if (this.stream) {
                this.stop();
            }
            
            // Request camera access
            const constraints = {
                video: {
                    width: { ideal: this.width },
                    height: { ideal: this.height },
                    facingMode: 'user'
                },
                audio: false
            };
            
            if (deviceId) {
                constraints.video.deviceId = { exact: deviceId };
            }
            
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Attach to video element
            this.video.srcObject = this.stream;
            
            // Wait for video to be ready
            await new Promise((resolve, reject) => {
                this.video.onloadedmetadata = () => {
                    this.video.play()
                        .then(resolve)
                        .catch(reject);
                };
                
                // Timeout after 10 seconds
                setTimeout(() => reject(new Error('Video load timeout')), 10000);
            });
            
            this.isActive = true;
            
            // Start drawing to canvas
            this.startDrawing();
            
            console.log('✅ Camera started successfully');
            return true;
            
        } catch (error) {
            console.error('❌ Failed to start camera:', error);
            
            if (this.onError) {
                this.onError(error);
            }
            
            throw error;
        }
    }
    
    /**
     * Stop camera stream
     */
    stop() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        if (this.captureInterval) {
            clearInterval(this.captureInterval);
            this.captureInterval = null;
        }
        
        if (this.drawingLoop) {
            cancelAnimationFrame(this.drawingLoop);
            this.drawingLoop = null;
        }
        
        this.isActive = false;
        
        // Clear canvas
        if (this.ctx && this.canvas) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
        
        console.log('📷 Camera stopped');
    }
    
    /**
     * Start drawing video to canvas
     */
    startDrawing() {
        const draw = () => {
            if (!this.isActive) return;
            
            try {
                // Draw video frame to canvas
                if (this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
                    this.ctx.drawImage(
                        this.video,
                        0, 0,
                        this.canvas.width,
                        this.canvas.height
                    );
                    
                    this.frameCount++;
                    
                    // Call frame callback
                    if (this.onFrame) {
                        this.onFrame();
                    }
                }
            } catch (error) {
                console.error('Frame drawing error:', error);
            }
            
            // Continue loop
            this.drawingLoop = requestAnimationFrame(draw);
        };
        
        draw();
    }
    
    /**
     * Capture current frame as base64
     */
    captureFrame() {
        if (!this.isActive) {
            return null;
        }
        
        try {
            return this.canvas.toDataURL('image/jpeg', this.frameQuality);
        } catch (error) {
            console.error('Frame capture error:', error);
            return null;
        }
    }
    
    /**
     * Switch to next available camera
     */
    async switchCamera() {
        if (this.devices.length === 0) {
            this.devices = await CameraHandler.getAvailableCameras();
        }
        
        if (this.devices.length <= 1) {
            console.log('Only one camera available');
            return;
        }
        
        this.currentDeviceIndex = (this.currentDeviceIndex + 1) % this.devices.length;
        const nextDevice = this.devices[this.currentDeviceIndex];
        
        this.stop();
        await this.start(nextDevice.deviceId);
    }
    
    /**
     * Get available cameras
     */
    static async getAvailableCameras() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            return devices.filter(device => device.kind === 'videoinput');
        } catch (error) {
            console.error('❌ Failed to enumerate cameras:', error);
            return [];
        }
    }
    
    /**
     * Check browser compatibility
     */
    static isSupported() {
        return !!(
            navigator.mediaDevices &&
            navigator.mediaDevices.getUserMedia &&
            HTMLCanvasElement.prototype.toDataURL
        );
    }
    
    /**
     * Cleanup
     */
    destroy() {
        this.stop();
        if (this.video && this.video.parentNode) {
            this.video.parentNode.removeChild(this.video);
        }
    }
}

// Make available globally
window.CameraHandler = CameraHandler;
console.log('✅ CameraHandler class loaded and exposed globally');