/**
 * Face Detection Overlay Handler
 * Draws bounding boxes and labels on detected faces in real-time
 */

class FaceOverlayHandler {
    constructor(canvasId, overlayId) {
        this.canvas = document.getElementById(canvasId);
        this.overlay = document.getElementById(overlayId);
        
        if (!this.canvas || !this.overlay) {
            throw new Error('Canvas or overlay element not found');
        }
        
        // Create overlay canvas
        this.overlayCanvas = document.createElement('canvas');
        this.overlayCanvas.className = 'position-absolute top-0 start-0';
        this.overlayCanvas.style.pointerEvents = 'none';
        this.overlayCanvas.style.zIndex = '10';
        this.overlayCanvas.style.width = '100%';
        this.overlayCanvas.style.height = '100%';
        
        this.overlay.appendChild(this.overlayCanvas);
        this.ctx = this.overlayCanvas.getContext('2d');
        
        // Match overlay canvas size to camera canvas
        this.updateCanvasSize();
        
        // Settings
        this.showBoundingBoxes = true;
        this.showLabels = true;
        this.showConfidence = true;
        this.animationEnabled = true;
        
        // State
        this.detectedFaces = [];
        this.animationFrame = null;
        
        // Colors
        this.colors = {
            recognized: '#28a745',      // Green
            unknown: '#ffc107',         // Yellow
            processing: '#17a2b8',      // Cyan
            error: '#dc3545'            // Red
        };
        
        // Animation
        this.pulsePhase = 0;
        
        // Resize observer
        this.resizeObserver = new ResizeObserver(() => {
            this.updateCanvasSize();
            this.redraw();
        });
        this.resizeObserver.observe(this.canvas);
        
        console.log('✅ FaceOverlayHandler initialized');
    }
    
    updateCanvasSize() {
        const rect = this.canvas.getBoundingClientRect();
        // Use actual canvas dimensions, not CSS size, for accurate drawing
        const canvasWidth = this.canvas.width || rect.width;
        const canvasHeight = this.canvas.height || rect.height;
        
        // Set overlay canvas to match camera canvas dimensions
        this.overlayCanvas.width = canvasWidth;
        this.overlayCanvas.height = canvasHeight;
        this.width = canvasWidth;
        this.height = canvasHeight;
    }
    
    /**
     * Update detected faces from socket event
     */
    updateFaces(faces, frameWidth, frameHeight) {
        // Filter out faces without bbox data
        this.detectedFaces = faces
            .filter(face => face.bbox && face.bbox.x !== undefined)
            .map(face => ({
                ...face,
                timestamp: Date.now(),
                frameWidth: frameWidth,
                frameHeight: frameHeight
            }));
        
        this.redraw();
    }
    
    /**
     * Clear all overlays
     */
    clear() {
        this.detectedFaces = [];
        this.ctx.clearRect(0, 0, this.width, this.height);
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
    }
    
    /**
     * Redraw all face overlays
     */
    redraw() {
        if (!this.showBoundingBoxes && !this.showLabels) {
            this.clear();
            return;
        }
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        // Remove stale faces (older than 2 seconds)
        const now = Date.now();
        this.detectedFaces = this.detectedFaces.filter(face => 
            now - face.timestamp < 2000
        );
        
        // Draw each face
        this.detectedFaces.forEach(face => {
            this.drawFace(face);
        });
        
        // Continue animation if enabled
        if (this.animationEnabled && this.detectedFaces.length > 0) {
            this.pulsePhase += 0.05;
            this.animationFrame = requestAnimationFrame(() => this.redraw());
        }
    }
    
    /**
     * Draw a single face overlay
     */
    drawFace(face) {
        if (!face.bbox) return;
        
        // Scale normalized coordinates to canvas size
        const x = face.bbox.x * this.width;
        const y = face.bbox.y * this.height;
        const w = face.bbox.width * this.width;
        const h = face.bbox.height * this.height;
        
        // Determine color based on recognition status
        const color = face.recognized ? this.colors.recognized : 
                     face.confidence > 0 ? this.colors.processing : 
                     this.colors.unknown;
        
        // Calculate fade based on age
        const age = Date.now() - face.timestamp;
        const opacity = Math.max(0.3, 1 - (age / 2000));
        
        // Draw bounding box
        if (this.showBoundingBoxes) {
            this.drawBoundingBox(x, y, w, h, color, opacity);
        }
        
        // Draw label
        if (this.showLabels) {
            this.drawLabel(x, y, w, face, color, opacity);
        }
        
        // Draw corner markers
        this.drawCorners(x, y, w, h, color, opacity);
    }
    
    /**
     * Draw bounding box rectangle
     */
    drawBoundingBox(x, y, w, h, color, opacity) {
        this.ctx.save();
        
        // Add pulse animation for recognized faces
        if (this.animationEnabled) {
            const pulse = Math.sin(this.pulsePhase) * 0.1 + 1;
            this.ctx.lineWidth = 3 * pulse;
        } else {
            this.ctx.lineWidth = 3;
        }
        
        this.ctx.strokeStyle = this.hexToRgba(color, opacity);
        this.ctx.strokeRect(x, y, w, h);
        
        // Add inner glow
        this.ctx.strokeStyle = this.hexToRgba(color, opacity * 0.3);
        this.ctx.lineWidth = 1;
        this.ctx.strokeRect(x + 2, y + 2, w - 4, h - 4);
        
        this.ctx.restore();
    }
    
    /**
     * Draw corner markers
     */
    drawCorners(x, y, w, h, color, opacity) {
        this.ctx.save();
        this.ctx.strokeStyle = this.hexToRgba(color, opacity);
        this.ctx.lineWidth = 4;
        this.ctx.lineCap = 'round';
        
        const cornerLength = Math.min(w, h) * 0.15;
        
        // Top-left
        this.ctx.beginPath();
        this.ctx.moveTo(x, y + cornerLength);
        this.ctx.lineTo(x, y);
        this.ctx.lineTo(x + cornerLength, y);
        this.ctx.stroke();
        
        // Top-right
        this.ctx.beginPath();
        this.ctx.moveTo(x + w - cornerLength, y);
        this.ctx.lineTo(x + w, y);
        this.ctx.lineTo(x + w, y + cornerLength);
        this.ctx.stroke();
        
        // Bottom-left
        this.ctx.beginPath();
        this.ctx.moveTo(x, y + h - cornerLength);
        this.ctx.lineTo(x, y + h);
        this.ctx.lineTo(x + cornerLength, y + h);
        this.ctx.stroke();
        
        // Bottom-right
        this.ctx.beginPath();
        this.ctx.moveTo(x + w - cornerLength, y + h);
        this.ctx.lineTo(x + w, y + h);
        this.ctx.lineTo(x + w, y + h - cornerLength);
        this.ctx.stroke();
        
        this.ctx.restore();
    }
    
    /**
     * Draw label with name and confidence
     */
    drawLabel(x, y, w, face, color, opacity) {
        const name = face.name || 'Unknown';
        const confidence = face.confidence ? 
            `${(face.confidence * 100).toFixed(0)}%` : '';
        
        // Prepare label text
        const labelText = this.showConfidence && confidence ? 
            `${name} (${confidence})` : name;
        
        // Measure text
        this.ctx.save();
        this.ctx.font = 'bold 14px Arial, sans-serif';
        const textWidth = this.ctx.measureText(labelText).width;
        const padding = 8;
        const labelWidth = textWidth + padding * 2;
        const labelHeight = 28;
        
        // Position label (above box, or below if near top)
        let labelX = x;
        let labelY = y - labelHeight - 5;
        
        // If near top of canvas, place below
        if (labelY < 0) {
            labelY = y + w + 5;
        }
        
        // Keep within canvas bounds
        labelX = Math.max(0, Math.min(labelX, this.width - labelWidth));
        labelY = Math.max(0, Math.min(labelY, this.height - labelHeight));
        
        // Draw label background with gradient
        const gradient = this.ctx.createLinearGradient(
            labelX, labelY, 
            labelX, labelY + labelHeight
        );
        gradient.addColorStop(0, this.hexToRgba(color, opacity * 0.95));
        gradient.addColorStop(1, this.hexToRgba(color, opacity * 0.85));
        
        this.ctx.fillStyle = gradient;
        this.roundRect(labelX, labelY, labelWidth, labelHeight, 5);
        this.ctx.fill();
        
        // Draw label border
        this.ctx.strokeStyle = this.hexToRgba('#ffffff', opacity * 0.3);
        this.ctx.lineWidth = 1;
        this.ctx.stroke();
        
        // Draw text
        this.ctx.fillStyle = this.hexToRgba('#ffffff', opacity);
        this.ctx.textAlign = 'left';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(labelText, labelX + padding, labelY + labelHeight / 2);
        
        this.ctx.restore();
    }
    
    /**
     * Draw rounded rectangle
     */
    roundRect(x, y, w, h, radius) {
        this.ctx.beginPath();
        this.ctx.moveTo(x + radius, y);
        this.ctx.lineTo(x + w - radius, y);
        this.ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
        this.ctx.lineTo(x + w, y + h - radius);
        this.ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
        this.ctx.lineTo(x + radius, y + h);
        this.ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
        this.ctx.lineTo(x, y + radius);
        this.ctx.quadraticCurveTo(x, y, x + radius, y);
        this.ctx.closePath();
    }
    
    /**
     * Convert hex color to rgba
     */
    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    
    /**
     * Toggle bounding boxes
     */
    toggleBoundingBoxes(show) {
        this.showBoundingBoxes = show;
        this.redraw();
    }
    
    /**
     * Toggle labels
     */
    toggleLabels(show) {
        this.showLabels = show;
        this.redraw();
    }
    
    /**
     * Toggle confidence display
     */
    toggleConfidence(show) {
        this.showConfidence = show;
        this.redraw();
    }
    
    /**
     * Toggle animation
     */
    toggleAnimation(enabled) {
        this.animationEnabled = enabled;
        if (!enabled && this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
        this.redraw();
    }
    
    /**
     * Set custom colors
     */
    setColors(colors) {
        this.colors = { ...this.colors, ...colors };
        this.redraw();
    }
    
    /**
     * Cleanup
     */
    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        this.clear();
        if (this.overlayCanvas.parentNode) {
            this.overlayCanvas.parentNode.removeChild(this.overlayCanvas);
        }
    }
}

// Make available globally
window.FaceOverlayHandler = FaceOverlayHandler;
console.log('✅ FaceOverlayHandler class loaded and exposed globally');