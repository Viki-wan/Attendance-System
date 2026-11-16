class ProgressTracker {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.socket = io();
        this.chart = null;
        
        // Delayed initialization to ensure DOM is ready
        setTimeout(() => {
            this.initializeChart();
        }, 100);
        
        this.initializeSocketHandlers();
        
        console.log('✅ ProgressTracker initialized');
    }

    initializeSocketHandlers() {
        this.socket.on('session_progress', (data) => {
            this.updateAllMetrics(data);
            this.updateChart(data);
            this.updateTimeline(data);
        });

        this.socket.on('attendance_marked', (data) => {
            this.animateCounter(data.status);
            this.addTimelineEvent(data);
        });
        
        this.socket.on('session_stats', (data) => {
            this.updateAllMetrics(data);
        });
    }

    initializeChart() {
        const canvas = document.getElementById('attendanceChart');
        
        // Only initialize if canvas exists
        if (!canvas) {
            console.log('Chart canvas not found - skipping chart initialization');
            return;
        }
        
        const ctx = canvas.getContext('2d');
        
        if (typeof Chart === 'undefined') {
            console.log('Chart.js not loaded - skipping chart initialization');
            return;
        }
        
        this.chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Present', 'Late', 'Absent'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.8)',
                        'rgba(255, 193, 7, 0.8)',
                        'rgba(220, 53, 69, 0.8)'
                    ],
                    borderColor: [
                        'rgba(40, 167, 69, 1)',
                        'rgba(255, 193, 7, 1)',
                        'rgba(220, 53, 69, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? 
                                    ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                },
                animation: {
                    animateScale: true,
                    animateRotate: true
                }
            }
        });
        
        console.log('✅ Chart initialized');
    }

    updateAllMetrics(data) {
        if (!data) return;
        
        // Update counters
        this.updateCounter('present-count', data.present || 0);
        this.updateCounter('late-count', data.late || 0);
        this.updateCounter('absent-count', data.absent || 0);
        
        // Update marked and pending counts
        const marked = (data.present || 0) + (data.late || 0);
        const total = data.total_expected || 0;
        const pending = total - marked;
        
        this.updateCounter('marked-count', marked);
        this.updateCounter('pending-count', pending);
        this.updateCounter('total-count', total);
        
        // Update progress bar
        const attendanceRate = data.attendance_rate || 0;
        this.updateProgressBar(attendanceRate);
        
        // Update percentage text
        const percentageElement = document.getElementById('attendance-percentage');
        if (percentageElement) {
            percentageElement.textContent = attendanceRate.toFixed(1);
        }
        
        // Update progress text
        const progressText = document.getElementById('progress-text');
        if (progressText) {
            progressText.textContent = `${marked}/${total}`;
        }
    }

    updateCounter(elementId, newValue) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const currentValue = parseInt(element.textContent) || 0;
        
        if (currentValue !== newValue) {
            this.animateValue(element, currentValue, newValue, 500);
        }
    }

    animateValue(element, start, end, duration) {
        if (!element) return;
        
        const range = end - start;
        const increment = range / (duration / 16);
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            
            if ((increment > 0 && current >= end) || 
                (increment < 0 && current <= end)) {
                current = end;
                clearInterval(timer);
            }
            
            element.textContent = Math.round(current);
        }, 16);
    }

    updateProgressBar(percentage) {
        const progressBar = document.getElementById('attendance-progress-bar');
        if (!progressBar) return;
        
        progressBar.style.width = `${percentage}%`;
        progressBar.setAttribute('aria-valuenow', percentage);
        
        // Update color
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
        if (percentage >= 80) {
            progressBar.classList.add('bg-success');
        } else if (percentage >= 60) {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-danger');
        }
    }

    updateChart(data) {
        if (!this.chart) return;
        
        this.chart.data.datasets[0].data = [
            data.present || 0,
            data.late || 0,
            data.absent || 0
        ];
        
        this.chart.update('active');
    }

    animateCounter(status) {
        const statusMap = {
            'Present': 'present-count',
            'Late': 'late-count',
            'Absent': 'absent-count'
        };
        
        const elementId = statusMap[status];
        if (!elementId) return;
        
        const element = document.getElementById(elementId);
        if (element) {
            element.classList.add('counter-bump');
            setTimeout(() => {
                element.classList.remove('counter-bump');
            }, 600);
        }
    }

    addTimelineEvent(data) {
        const timeline = document.getElementById('attendance-timeline');
        if (!timeline) return;
        
        // Remove empty state if exists
        const emptyState = timeline.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        const event = document.createElement('div');
        event.className = 'timeline-event fade-in';
        event.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <strong>${data.student_name}</strong> marked as 
                    <span class="badge bg-${
                        data.status === 'Present' ? 'success' : 
                        data.status === 'Late' ? 'warning' : 
                        'secondary'
                    }">${data.status}</span>
                </div>
                <small class="text-muted">${new Date().toLocaleTimeString()}</small>
            </div>
        `;
        
        timeline.insertBefore(event, timeline.firstChild);
        
        // Keep only last 20 events
        while (timeline.children.length > 20) {
            timeline.removeChild(timeline.lastChild);
        }
    }

    updateTimeline(data) {
        // Update session duration
        if (data.session_start_time) {
            const startTime = new Date(data.session_start_time);
            const now = new Date();
            const duration = Math.floor((now - startTime) / 1000 / 60);
            
            const durationElement = document.getElementById('session-duration');
            if (durationElement) {
                durationElement.textContent = `${duration} minutes`;
            }
        }
    }
    
    /**
     * Manually refresh statistics from server
     */
    async refresh() {
        if (!this.sessionId) return;
        
        try {
            // Correct URL pattern: /lecturer/attendance/<session_id>/sync
            const response = await fetch(`/lecturer/attendance/${this.sessionId}/sync`);
            const data = await response.json();
            
            if (data.success && data.stats) {
                this.updateAllMetrics(data.stats);
            }
        } catch (error) {
            console.error('Failed to refresh statistics:', error);
        }
    }
}

// DO NOT auto-initialize - let live_attendance.html do it
window.ProgressTracker = ProgressTracker;
console.log('✅ ProgressTracker class loaded and exposed globally');