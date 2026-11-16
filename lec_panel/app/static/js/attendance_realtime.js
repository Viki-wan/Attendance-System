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
        
        this.initializeSocketHandlers();
        this.initializeUIHandlers();
        this.joinSession();
        this.startHeartbeat();
    }

    // ========== Socket Event Handlers ==========
    
    initializeSocketHandlers() {
        // Connection events
        this.socket.on('connect', () => {
            console.log('âœ… Connected to server');
            this.showNotification('Connected', 'success');
            this.joinSession();
        });

        this.socket.on('disconnect', () => {
            console.log('â�œ Disconnected from server');
            this.showNotification('Disconnected - Reconnecting...', 'warning');
        });

        this.socket.on('error', (data) => {
            console.error('Socket error:', data);
            this.showNotification(data.message || 'An error occurred', 'error');
        });

        // Recognition events
        this.socket.on('student_recognized', (data) => {
            this.handleStudentRecognized(data);
        });

        this.socket.on('attendance_marked', (data) => {
            this.handleAttendanceMarked(data);
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

        // Attendance events
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
        // Request all necessary data on join
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
        }, 30000); // Every 30 seconds
    }

    // ========== Recognition Handlers ==========
    
    handleStudentRecognized(data) {
        const {student_id, student_name, confidence, status} = data;
        
        // Add to recognized set
        this.recognizedStudents.add(student_id);
        
        // Show toast notification
        this.showNotification(
            `Recognized: ${student_name} (${(confidence * 100).toFixed(1)}%)`,
            'success'
        );
        
        // Update UI
        this.updateStudentStatus(student_id, status);
        
        // Add to recent recognitions feed
        this.addToRecentFeed({
            student_name,
            confidence,
            timestamp: new Date().toLocaleTimeString()
        });
        
        // Play sound (optional)
        this.playRecognitionSound();
    }

    handleAttendanceMarked(data) {
        const {student_id, student_name, status, method} = data;
        
        // Update student card
        this.updateStudentStatus(student_id, status);
        
        // Show notification
        const methodText = method === 'manual' ? '(Manual)' : '(Auto)';
        this.showNotification(
            `${student_name} marked as ${status} ${methodText}`,
            'info'
        );
        
        // Request updated statistics
        this.requestStats();
    }

    handleUnknownFace(data) {
        const {image_url, timestamp, location} = data;
        
        // Show alert
        this.showNotification(
            'Unknown person detected in camera',
            'warning'
        );
        
        // Optionally display image
        if (image_url) {
            this.displayUnknownFaceAlert(image_url);
        }
    }

    // ========== UI Updates ==========
    
    updateStudentStatus(studentId, status) {
        const studentCard = document.querySelector(
            `[data-student-id="${studentId}"]`
        );
        
        if (studentCard) {
            // Remove all status classes
            studentCard.classList.remove(
                'status-present', 
                'status-absent', 
                'status-late'
            );
            
            // Add new status class
            studentCard.classList.add(`status-${status.toLowerCase()}`);
            
            // Update status badge
            const badge = studentCard.querySelector('.status-badge');
            if (badge) {
                badge.textContent = status;
                badge.className = `status-badge badge bg-${
                    status === 'Present' ? 'success' : 
                    status === 'Late' ? 'warning' : 
                    'secondary'
                }`;
            }
            
            // Update timestamp
            const timestamp = studentCard.querySelector('.timestamp');
            if (timestamp) {
                timestamp.textContent = new Date().toLocaleTimeString();
            }
        }
    }

    updateStatistics(stats) {
        // Update counters
        document.getElementById('present-count').textContent = 
            stats.present || 0;
        document.getElementById('late-count').textContent = 
            stats.late || 0;
        document.getElementById('absent-count').textContent = 
            stats.absent || 0;
        document.getElementById('total-count').textContent = 
            stats.total_expected || 0;
        
        // Update attendance rate
        const rate = stats.attendance_rate || 0;
        document.getElementById('attendance-rate').textContent = 
            `${rate.toFixed(1)}%`;
    }

    updateProgressBar(stats) {
        const progressBar = document.getElementById('attendance-progress');
        const rate = stats.attendance_rate || 0;
        
        progressBar.style.width = `${rate}%`;
        progressBar.setAttribute('aria-valuenow', rate);
        
        // Change color based on rate
        progressBar.className = 'progress-bar';
        if (rate >= 80) {
            progressBar.classList.add('bg-success');
        } else if (rate >= 60) {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-danger');
        }
    }

    updateStudentList(students) {
        const container = document.getElementById('student-list');
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
            indicator.textContent = isActive ? 
                'Recognition Active' : 
                'Recognition Stopped';
        }
    }

    showNotification(message, type = 'info') {
        // Use Bootstrap Toast
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
        container.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove after hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    playRecognitionSound() {
        // Optional: Play sound on recognition
        const audio = new Audio('/static/sounds/recognition.mp3');
        audio.volume = 0.3;
        audio.play().catch(() => {
            // Ignore if sound fails
        });
    }

    handleSessionEnded(data) {
        this.showNotification('Session has ended', 'info');
        
        // Show final statistics modal
        this.showFinalStatistics(data.statistics);
        
        // Disable controls
        this.disableControls();
    }

    disableControls() {
        document.querySelectorAll('.session-control-btn').forEach(btn => {
            btn.disabled = true;
        });
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
        document.getElementById('mark-all-present')?.addEventListener('click', () => {
            const allIds = this.getAllAbsentStudentIds();
            this.bulkMarkAttendance(allIds, 'Present');
        });

        document.getElementById('mark-all-absent')?.addEventListener('click', () => {
            const unmarkedIds = this.getUnmarkedStudentIds();
            this.bulkMarkAttendance(unmarkedIds, 'Absent');
        });

        // Student search/filter
        document.getElementById('student-search')?.addEventListener('input', (e) => {
            this.filterStudents(e.target.value);
        });
    }

    filterStudents(searchTerm) {
        const term = searchTerm.toLowerCase();
        document.querySelectorAll('.student-card').forEach(card => {
            const name = card.querySelector('.student-details h5').textContent.toLowerCase();
            const id = card.querySelector('.student-details p').textContent.toLowerCase();
            
            if (name.includes(term) || id.includes(term)) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    getAllAbsentStudentIds() {
        const ids = [];
        document.querySelectorAll('.student-card').forEach(card => {
            const badge = card.querySelector('.status-badge');
            if (badge && badge.textContent.trim() === 'Absent') {
                ids.push(card.dataset.studentId);
            }
        });
        return ids;
    }

    getUnmarkedStudentIds() {
        const ids = [];
        document.querySelectorAll('.student-card').forEach(card => {
            const badge = card.querySelector('.status-badge');
            if (!badge || badge.textContent.trim() === 'Absent') {
                ids.push(card.dataset.studentId);
            }
        });
        return ids;
    }

    showNoteModal(studentId) {
        const modal = new bootstrap.Modal(document.getElementById('noteModal'));
        document.getElementById('noteStudentId').value = studentId;
        document.getElementById('noteText').value = '';
        modal.show();
    }

    // Cleanup on page unload
    destroy() {
        this.leaveSession();
        this.socket.disconnect();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const sessionId = document.getElementById('session-id')?.value;
    const userId = document.getElementById('user-id')?.value;
    
    if (sessionId && userId) {
        window.attendanceHandler = new AttendanceRealtimeHandler(sessionId, userId);
        
        // Cleanup on page unload
        window.addEventListener('beforeunload', () => {
            window.attendanceHandler.destroy();
        });
    }
});