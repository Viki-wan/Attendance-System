class ProgressTracker {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.socket = io();
        this.chart = null;
        this.initializeChart();
        this.initializeSocketHandlers();
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
    }

    initializeChart() {
        const ctx = document.getElementById('attendanceChart').getContext('2d');
        
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
    }

    updateAllMetrics(data) {
        // Update counters
        this.updateCounter('present-count', data.present || 0);
        this.updateCounter('late-count', data.late || 0);
        this.updateCounter('absent-count', data.absent || 0);
        
        // Update progress bar
        this.updateProgressBar(data.attendance_rate || 0);
        
        // Update percentage text
        document.getElementById('attendance-percentage').textContent = 
            `${(data.attendance_rate || 0).toFixed(1)}%`;
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
        
        const event = document.createElement('div');
        event.className = 'timeline-event fade-in';
        event.innerHTML = `
            <div class="timeline-time">${new Date().toLocaleTimeString()}</div>
            <div class="timeline-content">
                <strong>${data.student_name}</strong> marked as 
                <span class="badge bg-${
                    data.status === 'Present' ? 'success' : 
                    data.status === 'Late' ? 'warning' : 
                    'secondary'
                }">${data.status}</span>
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
        const startTime = new Date(data.session_start_time);
        const now = new Date();
        const duration = Math.floor((now - startTime) / 1000 / 60);
        
        const durationElement = document.getElementById('session-duration');
        if (durationElement) {
            durationElement.textContent = `${duration} minutes`;
        }
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const sessionId = document.getElementById('session-id')?.value;
    if (sessionId) {
        window.progressTracker = new ProgressTracker(sessionId);
    }
});