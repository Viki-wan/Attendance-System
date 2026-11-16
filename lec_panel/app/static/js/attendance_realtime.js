class AttendanceRealtimeHandler {
    constructor(sessionId, userId) {
        this.sessionId = sessionId;
        this.userId = userId;
        this.socket = io({
            transports: ['websocket'],
            upgrade: false,
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 5
        });
        
        this.recognizedStudents = new Set();
        this.lastHeartbeat = Date.now();
        this.isRecognizing = false;
        this.recognitionInterval = null;
        this.recognitionFPS = 2; // Process 2 frames per second
        this.frameNumber = 0; // Track frame numbers for debugging
        
        this.initializeSocketHandlers();
        this.initializeUIHandlers();
        this.joinSession();
        this.startHeartbeat();
    }

    // ========== Socket Event Handlers ==========
    
    initializeSocketHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('✅ Connected to server');
            this.showNotification('Connected', 'success');
            this.joinSession();
        });

        this.socket.on('disconnect', () => {
            console.log('❌ Disconnected from server');
            this.showNotification('Disconnected - Reconnecting...', 'warning');
        });

        this.socket.on('error', (data) => {
            console.error('Socket error:', data);
            this.showNotification(data.message || 'An error occurred', 'error');
        });

        // Recognition error events
        this.socket.on('recognition_error', (data) => {
            console.error('Recognition error:', data);
            this.showNotification(data.message || 'Face recognition error', 'error');
        });

        // Frame processing events
        this.socket.on('frame_processing', (data) => {
            console.log('Frame queued for processing:', data.task_id);
        });

        this.socket.on('frame_error', (data) => {
            console.error('Frame processing error:', data);
            if (data.frame_number) {
                console.error(`Error on frame ${data.frame_number}:`, data.message || data.error);
            }
        });

        this.socket.on('frame_warning', (data) => {
            console.warn('Frame quality warning:', data);
        });

        // Recognition events
        this.socket.on('student_recognized', (data) => {
            this.handleStudentRecognized(data);
        });

        this.socket.on('attendance_marked', (data) => {
            this.handleAttendanceMarked(data);
        });

        // NEW: Face detection overlay event
        this.socket.on('face_detection_overlay', (data) => {
            this.handleFaceDetectionOverlay(data);
        });

        this.socket.on('unknown_face_detected', (data) => {
            this.handleUnknownFace(data);
        });

        // Statistics events
        this.socket.on('session_progress', (data) => {
            this.updateStatistics(data);
            this.updateProgressBar(data);
        });

        this.socket.on('session_stats', (data) => {
            this.updateStatistics(data);
        });

        // Bulk attendance events
        this.socket.on('bulk_attendance_marked', (data) => {
            this.showNotification(
                `Marked ${data.count} students as ${data.status}`, 
                'success'
            );
            this.requestStats();
        });

        this.socket.on('attendance_updated', (data) => {
            this.updateStudentStatus(
                data.student_id, 
                data.new_status
            );
        });

        this.socket.on('note_added', (data) => {
            this.showNotification('Note added successfully', 'success');
        });

        // Session events
        this.socket.on('recognition_started', (data) => {
            this.isRecognizing = true;
            this.updateRecognitionStatus(true);
            this.showNotification('Face recognition started', 'info');
        });

        this.socket.on('recognition_stopped', (data) => {
            this.isRecognizing = false;
            this.updateRecognitionStatus(false);
            this.showNotification('Face recognition stopped', 'info');
            
            // Clear overlay when stopped
            if (this.overlayHandler) {
                this.overlayHandler.clear();
            }
        });

        this.socket.on('session_ended', (data) => {
            this.handleSessionEnded(data);
        });

        // Data response events
        this.socket.on('student_list', (data) => {
            this.updateStudentList(data.students);
        });

        this.socket.on('recent_recognitions', (data) => {
            this.updateRecentRecognitions(data.recognitions);
        });

        this.socket.on('sync_response', (data) => {
            this.handleSyncResponse(data);
        });

        // Notification events
        this.socket.on('new_notification', (data) => {
            this.showSystemNotification(data);
        });
    }

    // ========== Session Management ==========
    
    joinSession() {
        this.socket.emit('join_session', {
            session_id: this.sessionId,
            user_id: this.userId
        });

        this.socket.on('joined_session', (data) => {
            console.log('Joined session:', data.session_id);
            this.requestInitialData();
        });
    }

    leaveSession() {
        this.socket.emit('leave_session', {
            session_id: this.sessionId
        });
    }

    requestInitialData() {
        this.socket.emit('request_session_stats', {
            session_id: this.sessionId
        });

        this.socket.emit('request_student_list', {
            session_id: this.sessionId
        });

        this.socket.emit('request_recent_recognitions', {
            session_id: this.sessionId
        });
    }

    startHeartbeat() {
        setInterval(() => {
            if (this.socket.connected) {
                this.socket.emit('session_heartbeat', {
                    session_id: this.sessionId
                });
            }
        }, 30000);
    }

    // ========== Recognition Control Methods ==========
    
    startRecognition() {
        if (this.isRecognizing) {
            console.log('Recognition already active');
            return;
        }
        
        console.log('Starting face recognition...');
        this.isRecognizing = true;
        
        // Initialize overlay handler if not already created
        if (!this.overlayHandler) {
            try {
                this.overlayHandler = new FaceOverlayHandler(
                    'camera-canvas',
                    'recognition-overlay'
                );
                console.log('✅ Face overlay handler initialized');
            } catch (error) {
                console.error('Failed to initialize overlay handler:', error);
            }
        }
        
        this.socket.emit('start_recognition', {
            session_id: this.sessionId,
            user_id: this.userId
        });
        
        this.startFrameProcessing();
        this.updateRecognitionStatus(true);
        
        console.log('✅ Face recognition started');
    }
    
    stopRecognition() {
        if (!this.isRecognizing) {
            console.log('Recognition already stopped');
            return;
        }
        
        console.log('Stopping face recognition...');
        this.isRecognizing = false;
        
        if (this.recognitionInterval) {
            clearInterval(this.recognitionInterval);
            this.recognitionInterval = null;
        }
        
        // Clear overlay
        if (this.overlayHandler) {
            this.overlayHandler.clear();
        }
        
        this.socket.emit('stop_recognition', {
            session_id: this.sessionId,
            user_id: this.userId
        });
        
        this.updateRecognitionStatus(false);
        
        console.log('🛑 Face recognition stopped');
    }
    
    startFrameProcessing() {
        if (this.recognitionInterval) {
            clearInterval(this.recognitionInterval);
        }
        
        const intervalMs = 1000 / this.recognitionFPS;
        
        this.recognitionInterval = setInterval(async () => {
            if (!this.isRecognizing) return;
            
            try {
                await this.processFrame();
            } catch (error) {
                console.error('Frame processing error:', error);
            }
        }, intervalMs);
        
        console.log(`Frame processing started at ${this.recognitionFPS} FPS`);
    }
    
    async processFrame() {
        if (!window.cameraHandler || !window.cameraHandler.isActive) {
            console.warn('Camera handler not active, skipping frame');
            return;
        }
        
        const frameData = window.cameraHandler.captureFrame();
        
        if (!frameData) {
            console.warn('Failed to capture frame');
            return;
        }
        
        this.frameNumber++;
        if (this.frameNumber % 10 === 0) {
            console.log(`Processing frame #${this.frameNumber}...`);
        }
        
        this.socket.emit('process_frame', {
            session_id: this.sessionId,
            user_id: this.userId,
            frame_data: frameData,
            timestamp: new Date().toISOString(),
            frame_number: this.frameNumber
        });
    }

    // ========== NEW: Face Detection Overlay Handler ==========
    
    handleFaceDetectionOverlay(data) {
        if (!this.overlayHandler) return;
        
        console.log(`Face overlay update: ${data.faces.length} faces detected`);
        
        // Update overlay with detected faces
        this.overlayHandler.updateFaces(
            data.faces,
            data.frame_width,
            data.frame_height
        );
        
        // Update detection counter
        const detectedCount = document.getElementById('detected-count');
        if (detectedCount) {
            detectedCount.textContent = data.faces.length;
        }
    }

    // ========== Recognition Handlers ==========
    
    handleStudentRecognized(data) {
        const {student_id, student_name, confidence, status} = data;
        
        this.recognizedStudents.add(student_id);
        
        this.showNotification(
            `Recognized: ${student_name} (${(confidence * 100).toFixed(1)}%)`,
            'success'
        );
        
        this.updateStudentStatus(student_id, status);
        
        this.addToRecentFeed({
            student_name,
            confidence,
            timestamp: new Date().toLocaleTimeString()
        });
        
        this.playRecognitionSound();
    }

    handleAttendanceMarked(data) {
        const {student_id, student_name, status, method} = data;
        
        this.updateStudentStatus(student_id, status);
        
        const methodText = method === 'manual' ? '(Manual)' : '(Auto)';
        this.showNotification(
            `${student_name} marked as ${status} ${methodText}`,
            'info'
        );
        
        this.requestStats();
    }

    handleUnknownFace(data) {
        this.showNotification(
            'Unknown person detected in camera',
            'warning'
        );
        
        if (data.image_url) {
            this.displayUnknownFaceAlert(data.image_url);
        }
    }

    // ========== UI Updates ==========
    
    updateStudentStatus(studentId, status) {
        const studentCard = document.querySelector(
            `[data-student-id="${studentId}"]`
        );
        
        if (studentCard) {
            studentCard.classList.remove(
                'status-present', 
                'status-absent', 
                'status-late'
            );
            
            studentCard.classList.add(`status-${status.toLowerCase()}`);
            
            const badge = studentCard.querySelector('.status-badge');
            if (badge) {
                badge.textContent = status;
                badge.className = `status-badge badge bg-${
                    status === 'Present' ? 'success' : 
                    status === 'Late' ? 'warning' : 
                    'secondary'
                }`;
            }
            
            const timestamp = studentCard.querySelector('.timestamp');
            if (timestamp) {
                timestamp.textContent = new Date().toLocaleTimeString();
            }
        }
    }

    updateStatistics(stats) {
        const presentCount = document.getElementById('present-count');
        const lateCount = document.getElementById('late-count');
        const absentCount = document.getElementById('absent-count');
        const totalCount = document.getElementById('total-count');
        
        if (presentCount) presentCount.textContent = stats.present || 0;
        if (lateCount) lateCount.textContent = stats.late || 0;
        if (absentCount) absentCount.textContent = stats.absent || 0;
        if (totalCount) totalCount.textContent = stats.total_expected || 0;
        
        const rate = stats.attendance_rate || 0;
        const rateElement = document.getElementById('attendance-rate') || 
                           document.getElementById('attendance-percentage');
        if (rateElement) {
            rateElement.textContent = `${rate.toFixed(1)}%`;
        }
    }

    updateProgressBar(stats) {
        const progressBar = document.getElementById('attendance-progress') ||
                           document.getElementById('attendance-progress-bar');
        
        if (!progressBar) return;
        
        const rate = stats.attendance_rate || 0;
        
        progressBar.style.width = `${rate}%`;
        progressBar.setAttribute('aria-valuenow', rate);
        
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
        if (rate >= 80) {
            progressBar.classList.add('bg-success');
        } else if (rate >= 60) {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-danger');
        }
    }

    addToRecentFeed(data) {
        const feed = document.getElementById('recent-recognitions-feed');
        if (!feed) return;
        
        const item = document.createElement('div');
        item.className = 'recognition-item new';
        item.innerHTML = `
            <div class="recognition-time">${data.timestamp}</div>
            <div class="recognition-name">${data.student_name}</div>
            <div class="recognition-confidence">
                ${(data.confidence * 100).toFixed(1)}%
            </div>
        `;
        
        feed.insertBefore(item, feed.firstChild);
        
        if (feed.children.length > 10) {
            feed.removeChild(feed.lastChild);
        }
        
        setTimeout(() => {
            item.classList.remove('new');
        }, 2000);
    }


    updateStudentList(students) {
        const container = document.getElementById('student-list');
        if (!container) return;
        
        container.innerHTML = '';
        
        students.forEach(student => {
            const card = this.createStudentCard(student);
            container.appendChild(card);
        });
    }

    createStudentCard(student) {
        const card = document.createElement('div');
        card.className = 'student-card';
        card.setAttribute('data-student-id', student.student_id);
        
        card.innerHTML = `
            <div class="student-info">
                <img src="${student.image_path || '/static/images/default-avatar.png'}" 
                     alt="${student.fname} ${student.lname}"
                     class="student-avatar">
                <div class="student-details">
                    <h5>${student.fname} ${student.lname}</h5>
                    <p class="text-muted">${student.student_id}</p>
                </div>
            </div>
            <div class="student-status">
                <span class="status-badge badge bg-secondary">
                    ${student.status || 'Absent'}
                </span>
                <span class="timestamp text-muted small">
                    ${student.timestamp || '--:--'}
                </span>
            </div>
            <div class="student-actions">
                <button class="btn btn-sm btn-success mark-present" 
                        data-student-id="${student.student_id}">
                    <i class="bi bi-check-circle"></i>
                </button>
                <button class="btn btn-sm btn-warning mark-late" 
                        data-student-id="${student.student_id}">
                    <i class="bi bi-clock"></i>
                </button>
                <button class="btn btn-sm btn-info add-note" 
                        data-student-id="${student.student_id}">
                    <i class="bi bi-sticky"></i>
                </button>
            </div>
        `;
        
        return card;
    }

    updateRecentRecognitions(recognitions) {
        const feed = document.getElementById('recent-recognitions-feed');
        if (!feed) return;
        
        feed.innerHTML = '';
        
        recognitions.forEach(rec => {
            const item = document.createElement('div');
            item.className = 'recognition-item';
            item.innerHTML = `
                <div class="recognition-time">${rec.timestamp}</div>
                <div class="recognition-name">${rec.student_name}</div>
                <div class="recognition-confidence">
                    ${(rec.confidence_score * 100).toFixed(1)}%
                </div>
            `;
            feed.appendChild(item);
        });
    }

    addToRecentFeed(data) {
        const feed = document.getElementById('recent-recognitions-feed');
        if (!feed) return;
        
        const item = document.createElement('div');
        item.className = 'recognition-item new';
        item.innerHTML = `
            <div class="recognition-time">${data.timestamp}</div>
            <div class="recognition-name">${data.student_name}</div>
            <div class="recognition-confidence">
                ${(data.confidence * 100).toFixed(1)}%
            </div>
        `;
        
        feed.insertBefore(item, feed.firstChild);
        
        // Remove oldest if more than 10
        if (feed.children.length > 10) {
            feed.removeChild(feed.lastChild);
        }
        
        // Remove 'new' class after animation
        setTimeout(() => {
            item.classList.remove('new');
        }, 2000);
    }

    // ========== Manual Operations ==========
    
    markAttendance(studentId, status) {
        this.socket.emit('mark_attendance_manual', {
            session_id: this.sessionId,
            student_id: studentId,
            status: status,
            method: 'manual'
        });
    }

    bulkMarkAttendance(studentIds, status) {
        this.socket.emit('bulk_mark_attendance', {
            session_id: this.sessionId,
            student_ids: studentIds,
            status: status
        });
    }


    addNote(studentId, note) {
        // Find attendance record
        const attendanceId = this.getAttendanceId(studentId);
        
        this.socket.emit('add_attendance_note', {
            attendance_id: attendanceId,
            note: note
        });
    }

    updateAttendanceStatus(attendanceId, newStatus, reason) {
        this.socket.emit('update_attendance_status', {
            attendance_id: attendanceId,
            status: newStatus,
            reason: reason
        });
    }

    // ========== Helper Methods ==========
    
    requestStats() {
        this.socket.emit('request_session_stats', {
            session_id: this.sessionId
        });
    }

    updateRecognitionStatus(isActive) {
        const indicator = document.getElementById('recognition-status');
        if (indicator) {
            indicator.className = `recognition-status ${
                isActive ? 'active' : 'inactive'
            }`;
            indicator.innerHTML = isActive ? 
                '<i class="bi bi-circle-fill"></i> Recognition Active' : 
                '<i class="bi bi-circle-fill"></i> Recognition Stopped';
        }
    }

    showNotification(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${
            type === 'success' ? 'success' :
            type === 'error' ? 'danger' :
            type === 'warning' ? 'warning' :
            'info'
        } border-0`;
        
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast"></button>
            </div>
        `;
        
        const container = document.getElementById('toast-container');
        if (container) {
            container.appendChild(toast);
            
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
            
            toast.addEventListener('hidden.bs.toast', () => {
                toast.remove();
            });
        }
    }

    playRecognitionSound() {
        const audio = new Audio('/static/sounds/recognition.mp3');
        audio.volume = 0.3;
        audio.play().catch(() => {});
    }

    handleSessionEnded(data) {
        this.showNotification('Session has ended', 'info');
        
        if (data.statistics) {
            this.showFinalStatistics(data.statistics);
        }
        
        this.disableControls();
    }

    disableControls() {
        document.querySelectorAll('.session-control-btn').forEach(btn => {
            btn.disabled = true;
        });
    }

    handleSyncResponse(data) {
        if (data.success) {
            this.showNotification('Data synchronized', 'success');
            if (data.stats) {
                this.updateStatistics(data.stats);
            }
        }
    }

    showSystemNotification(data) {
        this.showNotification(data.message, data.type || 'info');
    }

    displayUnknownFaceAlert(imageUrl) {
        // Implementation for showing unknown face alert
        console.log('Unknown face detected:', imageUrl);
    }

    showFinalStatistics(statistics) {
        // Implementation for showing final stats
        console.log('Final statistics:', statistics);
    }

    getAttendanceId(studentId) {
        // Implementation to get attendance ID
        return null;
    }

    // ========== Initialization ==========
    
    initializeUIHandlers() {
        // Mark present buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.mark-present')) {
                const btn = e.target.closest('.mark-present');
                const studentId = btn.dataset.studentId;
                this.markAttendance(studentId, 'Present');
            }
        });

        // Mark late buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.mark-late')) {
                const btn = e.target.closest('.mark-late');
                const studentId = btn.dataset.studentId;
                this.markAttendance(studentId, 'Late');
            }
        });

        // Add note buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.add-note')) {
                const btn = e.target.closest('.add-note');
                const studentId = btn.dataset.studentId;
                this.showNoteModal(studentId);
            }
        });

        // Bulk actions
        const markAllPresentBtn = document.getElementById('mark-all-present');
        if (markAllPresentBtn) {
            markAllPresentBtn.addEventListener('click', () => {
                const allIds = this.getAllAbsentStudentIds();
                this.bulkMarkAttendance(allIds, 'Present');
            });
        }

        const markAllAbsentBtn = document.getElementById('mark-all-absent');
        if (markAllAbsentBtn) {
            markAllAbsentBtn.addEventListener('click', () => {
                const unmarkedIds = this.getUnmarkedStudentIds();
                this.bulkMarkAttendance(unmarkedIds, 'Absent');
            });
        }

        // Student search/filter
        const searchInput = document.getElementById('student-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterStudents(e.target.value);
            });
        }
    }

    filterStudents(searchTerm) {
        const term = searchTerm.toLowerCase();
        document.querySelectorAll('.student-card, .student-item').forEach(card => {
            const nameElement = card.querySelector('.student-details h5, .student-name');
            const idElement = card.querySelector('.student-details p, .student-id');
            
            const name = nameElement ? nameElement.textContent.toLowerCase() : '';
            const id = idElement ? idElement.textContent.toLowerCase() : '';
            
            if (name.includes(term) || id.includes(term)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    getAllAbsentStudentIds() {
        const ids = [];
        document.querySelectorAll('.student-card, .student-item').forEach(card => {
            const badge = card.querySelector('.status-badge');
            if (badge && badge.textContent.trim() === 'Absent') {
                ids.push(card.dataset.studentId);
            }
        });
        return ids;
    }

    getUnmarkedStudentIds() {
        const ids = [];
        document.querySelectorAll('.student-card, .student-item').forEach(card => {
            const badge = card.querySelector('.status-badge');
            if (!badge || badge.textContent.trim() === 'Absent') {
                ids.push(card.dataset.studentId);
            }
        });
        return ids;
    }

    showNoteModal(studentId) {
        const modal = document.getElementById('noteModal');
        if (modal) {
            const bsModal = new bootstrap.Modal(modal);
            const studentIdInput = document.getElementById('noteStudentId');
            const noteTextArea = document.getElementById('noteText');
            
            if (studentIdInput) studentIdInput.value = studentId;
            if (noteTextArea) noteTextArea.value = '';
            
            bsModal.show();
        }
    }

    // Cleanup on page unload
    destroy() {
        this.stopRecognition();
        this.leaveSession();
        this.socket.disconnect();
    }
}

// DO NOT auto-initialize - let live_attendance.html do it
window.AttendanceRealtimeHandler = AttendanceRealtimeHandler;
console.log('✅ AttendanceRealtimeHandler class loaded and exposed globally');