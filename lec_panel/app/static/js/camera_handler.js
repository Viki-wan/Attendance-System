/**
 * Camera Handler for Web-based Face Recognition
 * Manages WebRTC camera access and frame capture
 */

class CameraHandler {
    constructor(videoElement, canvasElement) {
        this.videoElement = videoElement;
        this.canvasElement = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.stream = null;
        this.isStreaming = false;
        this.captureInterval = null;
        
        // Settings
        this.targetFPS = 30;
        this.processingFPS = 2; // Send 2 frames per second for processing
        this.frameQuality = 0.85; // JPEG quality
        this.maxWidth = 640; // Max width for processing
        
        // State
        this.frameCount = 0;
        this.lastProcessTime = 0;
        this.recognitionResults = [];
        
        // Callbacks
        this.onFrameCapture = null;
        this.onError = null;
        this.onStreamStart = null;
        this.onStreamStop = null;
    }
    
    /**
     * Initialize and start camera stream
     */
    async startCamera(constraints = {}) {
        try {
            // Default constraints
            const defaultConstraints = {
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'user',
                    frameRate: { ideal: this.targetFPS }
                },
                audio: false
            };
            
            // Merge with provided constraints
            const finalConstraints = {
                ...defaultConstraints,
                ...constraints
            };
            
            // Request camera access
            this.stream = await navigator.mediaDevices.getUserMedia(finalConstraints);
            
            // Attach to video element
            this.videoElement.srcObject = this.stream;
            
            // Wait for video to load
            await new Promise((resolve) => {
                this.videoElement.onloadedmetadata = () => {
                    this.videoElement.play();
                    resolve();
                };
            });
            
            // Set canvas size to match video
            this.canvasElement.width = this.videoElement.videoWidth;
            this.canvasElement.height = this.videoElement.videoHeight;
            
            this.isStreaming = true;
            
            // Start frame capture
            this.startFrameCapture();
            
            if (this.onStreamStart) {
                this.onStreamStart();
            }
            
            console.log('📷 Camera started successfully');
            return true;
            
        } catch (error) {
            console.error('❌ Failed to start camera:', error);
            
            if (this.onError) {
                this.onError({
                    type: 'camera_access',
                    message: 'Failed to access camera',
                    error: error
                });
            }
            
            return false;
        }
    }
    
    /**
     * Stop camera stream
     */
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        if (this.captureInterval) {
            clearInterval(this.captureInterval);
            this.captureInterval = null;
        }
        
        this.isStreaming = false;
        
        if (this.onStreamStop) {
            this.onStreamStop();
        }
        
        console.log('📷 Camera stopped');
    }
    
    /**
     * Start periodic frame capture
     */
    startFrameCapture() {
        const captureIntervalMs = 1000 / this.processingFPS;
        
        this.captureInterval = setInterval(() => {
            if (this.isStreaming) {
                this.captureFrame();
            }
        }, captureIntervalMs);
    }
    
    /**
     * Capture and process a single frame
     */
    captureFrame() {
        if (!this.isStreaming || !this.videoElement.videoWidth) {
            return null;
        }
        
        // Draw video frame to canvas
        this.ctx.drawImage(
            this.videoElement,
            0, 0,
            this.canvasElement.width,
            this.canvasElement.height
        );
        
        // Get frame as base64
        const frameData = this.canvasElement.toDataURL('image/jpeg', this.frameQuality);
        
        this.frameCount++;
        
        // Callback with frame data
        if (this.onFrameCapture) {
            this.onFrameCapture({
                frame: frameData,
                timestamp: new Date().toISOString(),
                frameNumber: this.frameCount,
                width: this.canvasElement.width,
                height: this.canvasElement.height
            });
        }
        
        return frameData;
    }
    
    /**
     * Take a snapshot (higher quality)
     */
    takeSnapshot(quality = 0.95) {
        if (!this.isStreaming) {
            return null;
        }
        
        // Create temporary canvas for high-quality capture
        const snapshotCanvas = document.createElement('canvas');
        snapshotCanvas.width = this.videoElement.videoWidth;
        snapshotCanvas.height = this.videoElement.videoHeight;
        
        const snapshotCtx = snapshotCanvas.getContext('2d');
        snapshotCtx.drawImage(this.videoElement, 0, 0);
        
        return snapshotCanvas.toDataURL('image/jpeg', quality);
    }
    
    /**
     * Draw face boxes on canvas
     */
    drawFaceBox(location, label, color = 'green') {
        const { top, right, bottom, left } = location;
        
        // Draw rectangle
        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 3;
        this.ctx.strokeRect(left, top, right - left, bottom - top);
        
        // Draw label background
        const labelHeight = 30;
        this.ctx.fillStyle = color;
        this.ctx.fillRect(left, top - labelHeight, right - left, labelHeight);
        
        // Draw label text
        this.ctx.fillStyle = 'white';
        this.ctx.font = '16px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(
            label,
            left + (right - left) / 2,
            top - labelHeight / 2
        );
    }
    
    /**
     * Draw overlay information
     */
    drawOverlay(info) {
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        this.ctx.fillRect(10, 10, 250, Object.keys(info).length * 25 + 10);
        
        this.ctx.fillStyle = 'white';
        this.ctx.font = '14px Arial';
        this.ctx.textAlign = 'left';
        
        let y = 30;
        for (const [key, value] of Object.entries(info)) {
            this.ctx.fillText(`${key}: ${value}`, 20, y);
            y += 25;
        }
    }
    
    /**
     * Clear canvas overlays
     */
    clearOverlays() {
        // Redraw video frame
        this.ctx.drawImage(
            this.videoElement,
            0, 0,
            this.canvasElement.width,
            this.canvasElement.height
        );
    }
    
    /**
     * Get camera capabilities
     */
    getCameraCapabilities() {
        if (!this.stream) {
            return null;
        }
        
        const videoTrack = this.stream.getVideoTracks()[0];
        const capabilities = videoTrack.getCapabilities();
        const settings = videoTrack.getSettings();
        
        return {
            capabilities: capabilities,
            currentSettings: settings,
            isActive: videoTrack.enabled,
            label: videoTrack.label
        };
    }
    
    /**
     * Adjust camera settings
     */
    async adjustSettings(constraints) {
        if (!this.stream) {
            return false;
        }
        
        try {
            const videoTrack = this.stream.getVideoTracks()[0];
            await videoTrack.applyConstraints(constraints);
            return true;
        } catch (error) {
            console.error('❌ Failed to adjust camera settings:', error);
            return false;
        }
    }
    
    /**
     * Switch camera (front/back)
     */
    async switchCamera() {
        const currentFacingMode = this.stream.getVideoTracks()[0]
            .getSettings().facingMode;
        
        const newFacingMode = currentFacingMode === 'user' ? 'environment' : 'user';
        
        this.stopCamera();
        
        return await this.startCamera({
            video: { facingMode: newFacingMode }
        });
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
     * Get stream statistics
     */
    getStatistics() {
        return {
            isStreaming: this.isStreaming,
            frameCount: this.frameCount,
            processingFPS: this.processingFPS,
            videoWidth: this.videoElement.videoWidth,
            videoHeight: this.videoElement.videoHeight,
            recognitionResults: this.recognitionResults.length
        };
    }
    
    /**
     * Add recognition result for display
     */
    addRecognitionResult(result) {
        this.recognitionResults.push({
            ...result,
            timestamp: Date.now()
        });
        
        // Keep only last 10 results
        if (this.recognitionResults.length > 10) {
            this.recognitionResults.shift();
        }
    }
    
    /**
     * Clear recognition results
     */
    clearRecognitionResults() {
        this.recognitionResults = [];
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CameraHandler;
}