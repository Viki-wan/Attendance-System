class NotificationHandler {
    constructor(userId) {
        this.userId = userId;
        this.socket = io();
        this.notifications = [];
        this.unreadCount = 0;
        
        this.initializeSocketHandlers();
        this.initializeUIHandlers();
        this.requestNotifications();
    }

    initializeSocketHandlers() {
        this.socket.on('connect', () => {
            // Join user-specific room
            this.socket.emit('join_room', {
                room: `user_${this.userId}`
            });
        });

        this.socket.on('new_notification', (notification) => {
            this.addNotification(notification);
            this.showToast(notification);
            this.playNotificationSound();
            this.updateBadge();
        });

        this.socket.on('notification_read', (data) => {
            this.markAsRead(data.notification_id);
            this.updateBadge();
        });

        this.socket.on('notifications_list', (data) => {
            this.notifications = data.notifications;
            this.renderNotifications();
            this.updateBadge();
        });
    }

    initializeUIHandlers() {
        // Bell icon click
        document.getElementById('notification-bell')?.addEventListener('click', () => {
            this.toggleNotificationPanel();
        });

        // Mark all as read
        document.getElementById('mark-all-read')?.addEventListener('click', () => {
            this.markAllAsRead();
        });

        // Clear all notifications
        document.getElementById('clear-all')?.addEventListener('click', () => {
            this.clearAll();
        });
    }

    requestNotifications() {
        this.socket.emit('request_notifications', {
            user_id: this.userId,
            limit: 50
        });
    }

    addNotification(notification) {
        this.notifications.unshift(notification);
        
        // Keep only last 50
        if (this.notifications.length > 50) {
            this.notifications = this.notifications.slice(0, 50);
        }
        
        if (!notification.is_read) {
            this.unreadCount++;
        }
        
        this.renderNotifications();
    }

    renderNotifications() {
        const container = document.getElementById('notification-list');
        if (!container) return;
        
        if (this.notifications.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-inbox fs-1"></i>
                    <p>No notifications</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = this.notifications.map(notif => `
            <div class="notification-item ${notif.is_read ? 'read' : 'unread'}" 
                 data-notification-id="${notif.id}">
                <div class="notification-icon ${notif.type}">
                    <i class="bi bi-${this.getIconForType(notif.type)}"></i>
                </div>
                <div class="notification-content">
                    <h6>${notif.title}</h6>
                    <p>${notif.message}</p>
                    <span class="notification-time">${this.formatTime(notif.created_at)}</span>
                </div>
                ${!notif.is_read ? `
                    <button class="btn btn-sm btn-link mark-read-btn" 
                            data-notification-id="${notif.id}">
                        <i class="bi bi-check"></i>
                    </button>
                ` : ''}
            </div>
        `).join('');
        
        // Add click handlers
        container.querySelectorAll('.mark-read-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.notificationId);
                this.markNotificationAsRead(id);
            });
        });
    }

    showToast(notification) {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center border-0 bg-${
            notification.type === 'success' ? 'success' :
            notification.type === 'warning' ? 'warning' :
            notification.type === 'error' ? 'danger' :
            'info'
        } text-white`;
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${notification.title}</strong><br>
                    ${notification.message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        data-bs-dismiss="toast"></button>
            </div>
        `;
        
        const container = document.getElementById('toast-container');
        container.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 5000
        });
        bsToast.show();
        
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    markNotificationAsRead(notificationId) {
        this.socket.emit('mark_notification_read', {
            notification_id: notificationId
        });
    }

    markAsRead(notificationId) {
        const notif = this.notifications.find(n => n.id === notificationId);
        if (notif && !notif.is_read) {
            notif.is_read = true;
            this.unreadCount = Math.max(0, this.unreadCount - 1);
            this.renderNotifications();
        }
    }

    markAllAsRead() {
        this.notifications.forEach(notif => {
            if (!notif.is_read) {
                this.markNotificationAsRead(notif.id);
            }
        });
    }

    clearAll() {
        if (confirm('Clear all notifications?')) {
            this.notifications = [];
            this.unreadCount = 0;
            this.renderNotifications();
            this.updateBadge();
            
            // Emit to server
            this.socket.emit('clear_all_notifications', {
                user_id: this.userId
            });
        }
    }

    updateBadge() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            if (this.unreadCount > 0) {
                badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
                badge.style.display = 'inline-block';
            } else {
                badge.style.display = 'none';
            }
        }
    }

    toggleNotificationPanel() {
        const panel = document.getElementById('notification-panel');
        if (panel) {
            panel.classList.toggle('show');
        }
    }

    getIconForType(type) {
        const icons = {
            'info': 'info-circle',
            'success': 'check-circle',
            'warning': 'exclamation-triangle',
            'error': 'x-circle'
        };
        return icons[type] || 'bell';
    }

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        
        return date.toLocaleDateString();
    }

    playNotificationSound() {
        const audio = new Audio('/static/sounds/notification.mp3');
        audio.volume = 0.3;
        audio.play().catch(() => {
            // Ignore if sound fails
        });
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const userId = document.getElementById('user-id')?.value;
    if (userId) {
        window.notificationHandler = new NotificationHandler(userId);
    }
});