// Theme Toggle Functionality
const themeToggle = document.getElementById('themeToggle');
const body = document.body;

// Check for saved theme preference or default to light
const currentTheme = localStorage.getItem('theme') || 'light';
body.setAttribute('data-theme', currentTheme);

// Update toggle icon based on theme
function updateThemeIcon() {
    const icon = themeToggle.querySelector('i');
    if (body.getAttribute('data-theme') === 'dark') {
        icon.className = 'fas fa-sun';
    } else {
        icon.className = 'fas fa-moon';
    }
}
updateThemeIcon();
themeToggle.addEventListener('click', () => {
    const currentTheme = body.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    body.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon();
});
// Simulate real-time updates
function updateStats() {
    const statValues = document.querySelectorAll('.stat-value');
    const progressBars = document.querySelectorAll('.progress-bar');
    // Add subtle animations to show data is live
    statValues.forEach(stat => {
        stat.style.transform = 'scale(1.02)';
        setTimeout(() => {
            stat.style.transform = 'scale(1)';
        }, 200);
    });
}
setInterval(updateStats, 30000);
// Navigation active state
if (document.querySelectorAll('.nav-link')) {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
            link.classList.add('active');
        });
    });
}
// Widget interactions
if (document.querySelectorAll('.quick-action-btn')) {
    document.querySelectorAll('.quick-action-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            btn.style.transform = 'scale(0.95)';
            setTimeout(() => {
                btn.style.transform = 'scale(1)';
            }, 150);
            // Here you would typically trigger the actual action
            console.log('Quick action triggered:', btn.querySelector('.quick-action-label').textContent);
        });
    });
}
// Auto-refresh functionality (placeholder for real implementation)
function autoRefresh() {
    console.log('Auto-refreshing dashboard data...');
    // This would typically make AJAX calls to update widget data
}
setInterval(autoRefresh, 30000);

function updateDashboardWidgets(data) {
    // Stats Widget
    document.querySelector('.stat-value[style*="var(--primary-color)"]').textContent = data.stats.total_sessions;
    document.querySelector('.stat-value[style*="var(--success-color)"]').textContent = data.stats.completed;
    document.querySelector('.stat-value[style*="var(--warning-color)"]').textContent = data.stats.ongoing;
    document.querySelector('.stat-value[style*="var(--text-secondary)"]').textContent = data.stats.avg_attendance + '%';

    // Session Overview Widget
    const sessionList = document.querySelector('.session-list');
    if (sessionList) {
        sessionList.innerHTML = '';
        data.sessions.forEach(session => {
            sessionList.innerHTML += `
            <div class="session-item">
                <div class="session-info">
                    <h4>${session.title}</h4>
                    <p>${session.time} • ${session.location}</p>
                    <div class="progress">
                        <div class="progress-bar" style="width: ${session.progress}%;"></div>
                    </div>
                </div>
                <span class="session-status status-${session.status.toLowerCase()}">${session.status}</span>
            </div>`;
        });
    }

    // Activity Feed Widget
    const activityFeed = document.querySelector('.activity-feed');
    if (activityFeed) {
        activityFeed.innerHTML = '';
        data.activity_feed.forEach(activity => {
            activityFeed.innerHTML += `
            <div class="activity-item">
                <div class="activity-icon" style="background-color: ${activity.color};">
                    <i class="fas ${activity.icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-text">${activity.text}</div>
                    <div class="activity-time">${activity.time_ago}</div>
                </div>
            </div>`;
        });
    }

    // Attendance Summary Widget
    document.querySelectorAll('.progress-bar[style*="var(--success-color)"]').forEach(bar => {
        bar.style.width = data.attendance_summary.week + '%';
    });
    document.querySelectorAll('.progress-bar[style*="var(--primary-color)"]').forEach(bar => {
        bar.style.width = data.attendance_summary.month + '%';
    });
    document.querySelectorAll('.progress-bar[style*="#8b5cf6"]').forEach(bar => {
        bar.style.width = data.attendance_summary.semester + '%';
    });
    // Update the numbers
    document.querySelectorAll('.widget .stat-label').forEach(label => {
        if (label.textContent.includes('This Week')) {
            label.nextElementSibling.textContent = data.attendance_summary.week + '%';
        } else if (label.textContent.includes('This Month')) {
            label.nextElementSibling.textContent = data.attendance_summary.month + '%';
        } else if (label.textContent.includes('This Semester')) {
            label.nextElementSibling.textContent = data.attendance_summary.semester + '%';
        }
    });

    // Camera Status Widget
    const cameraWidget = document.querySelector('.widget-header .fa-video')?.closest('.widget');
    if (cameraWidget) {
        const statLabels = cameraWidget.querySelectorAll('.stat-label');
        statLabels[0].previousElementSibling.innerHTML = '<i class="fas fa-circle"></i>';
        statLabels[0].textContent = data.camera_status.online ? 'Camera Online' : 'Camera Offline';
        statLabels[1].previousElementSibling.textContent = data.camera_status.resolution;
        statLabels[2].previousElementSibling.textContent = data.camera_status.light_quality;
        statLabels[3].previousElementSibling.textContent = data.camera_status.recognition_rate + '%';
    }
}

function pollDashboardData() {
    fetch('/dashboard/data')
        .then(res => res.json())
        .then(data => {
            updateDashboardWidgets(data);
        });
}

setInterval(pollDashboardData, 30000); // 30 seconds
// Initial fetch
pollDashboardData();

console.log('Dashboard initialized successfully'); 