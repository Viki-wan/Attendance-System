# Deployment Guide

This guide covers deploying the Face Recognition Attendance System to production environments.

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Server Requirements](#server-requirements)
- [Production Setup](#production-setup)
- [Database Configuration](#database-configuration)
- [Web Server Configuration](#web-server-configuration)
- [Security Considerations](#security-considerations)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)
- [Scaling](#scaling)

## Pre-Deployment Checklist

- [ ] Python 3.8+ installed
- [ ] Redis server configured and running
- [ ] Database created and migrations applied
- [ ] Environment variables configured
- [ ] SSL certificate obtained (for HTTPS)
- [ ] Firewall rules configured
- [ ] Backup strategy implemented
- [ ] Monitoring tools installed
- [ ] Log rotation configured
- [ ] Security audit completed

## Server Requirements

### Minimum Requirements

- **CPU**: 2 cores (4+ recommended)
- **RAM**: 4GB (8GB+ recommended)
- **Storage**: 20GB SSD (50GB+ recommended)
- **Network**: 100 Mbps
- **OS**: Linux (Ubuntu 20.04+ recommended) or Windows Server 2019+

### Recommended Production Setup

- **CPU**: 4-8 cores
- **RAM**: 16GB+
- **Storage**: 100GB+ SSD with backups
- **Network**: 1 Gbps
- **OS**: Ubuntu 22.04 LTS or Windows Server 2022

### Software Stack

- Python 3.8-3.12
- Redis 6.0+
- PostgreSQL 12+ (optional, SQLite works for small deployments)
- Nginx 1.18+ (reverse proxy)
- Gunicorn or uWSGI (WSGI server)
- Supervisor or systemd (process management)

## Production Setup

### Step 1: Server Preparation

**Ubuntu/Debian:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3.10 python3.10-venv python3-pip -y
sudo apt install redis-server postgresql -y
sudo apt install nginx supervisor -y

# Install system dependencies for face recognition
sudo apt install cmake libopenblas-dev liblapack-dev -y
```

**CentOS/RHEL:**
```bash
sudo yum update -y
sudo yum install python3 python3-pip redis postgresql -y
sudo yum install nginx supervisor -y
```

### Step 2: Application Deployment

```bash
# Create application user
sudo adduser --system --group attendance

# Create application directory
sudo mkdir -p /opt/attendance-system
sudo chown attendance:attendance /opt/attendance-system

# Clone repository (as attendance user)
sudo -u attendance git clone <repository-url> /opt/attendance-system

# Create virtual environment
cd /opt/attendance-system
sudo -u attendance python3 -m venv venv
sudo -u attendance venv/bin/pip install --upgrade pip
sudo -u attendance venv/bin/pip install -r requirements.txt
```

### Step 3: Environment Configuration

Create `/opt/attendance-system/.env`:

```env
# Flask Configuration
SECRET_KEY=<generate-strong-secret-key>
FLASK_CONFIG=production
DEBUG=False

# Database
DATABASE_URL=postgresql://user:password@localhost/attendance
# Or for SQLite:
# DATABASE_URL=sqlite:///attendance.db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=<redis-password>

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Email
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=<your-email>
MAIL_PASSWORD=<app-password>

# Server
PORT=5000
HOST=127.0.0.1

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
REMEMBER_COOKIE_SECURE=True
WTF_CSRF_ENABLED=True

# Face Recognition
FACE_RECOGNITION_TOLERANCE=0.6
FACE_RECOGNITION_MODEL=hog

# Logging
LOG_LEVEL=INFO
```

**Generate Secret Key:**
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 4: Database Setup

**PostgreSQL (Recommended for Production):**

```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE attendance;
CREATE USER attendance_user WITH PASSWORD 'strong_password';
GRANT ALL PRIVILEGES ON DATABASE attendance TO attendance_user;
\q
```

Update `.env`:
```env
DATABASE_URL=postgresql://attendance_user:strong_password@localhost/attendance
```

**Run Migrations:**
```bash
cd /opt/attendance-system/lec_panel
sudo -u attendance venv/bin/flask db upgrade
```

### Step 5: Static Files & Permissions

```bash
# Create required directories
sudo -u attendance mkdir -p /opt/attendance-system/uploads/{faces,encodings,reports,unknown_faces}
sudo -u attendance mkdir -p /opt/attendance-system/logs
sudo -u attendance mkdir -p /opt/attendance-system/backups

# Set permissions
sudo chmod -R 755 /opt/attendance-system/uploads
sudo chmod -R 755 /opt/attendance-system/logs
```

## Web Server Configuration

### Option 1: Gunicorn + Nginx (Recommended)

**Install Gunicorn:**
```bash
sudo -u attendance venv/bin/pip install gunicorn gevent
```

**Gunicorn Configuration (`/opt/attendance-system/gunicorn_config.py`):**
```python
bind = "127.0.0.1:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "/opt/attendance-system/logs/gunicorn_access.log"
errorlog = "/opt/attendance-system/logs/gunicorn_error.log"
loglevel = "info"
```

**Nginx Configuration (`/etc/nginx/sites-available/attendance`):**
```nginx
server {
    listen 80;
    server_name attendance.example.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name attendance.example.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/attendance.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/attendance.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Client Body Size (for file uploads)
    client_max_body_size 20M;
    
    # Static Files
    location /static {
        alias /opt/attendance-system/lec_panel/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # Student Images
    location /student_images {
        alias /opt/attendance-system/student_images;
        expires 7d;
    }
    
    # WebSocket Support
    location /socket.io {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
    
    # Application
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

**Enable Site:**
```bash
sudo ln -s /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option 2: uWSGI + Nginx

**Install uWSGI:**
```bash
sudo -u attendance venv/bin/pip install uwsgi
```

**uWSGI Configuration (`/opt/attendance-system/uwsgi.ini`):**
```ini
[uwsgi]
module = app:create_app()
callable = app
master = true
processes = 4
threads = 2
socket = 127.0.0.1:5000
chmod-socket = 660
vacuum = true
die-on-term = true
logto = /opt/attendance-system/logs/uwsgi.log
```

### Process Management with Supervisor

**Supervisor Config (`/etc/supervisor/conf.d/attendance.conf`):**
```ini
[program:attendance-web]
command=/opt/attendance-system/venv/bin/gunicorn -c /opt/attendance-system/gunicorn_config.py "app:create_app()"
directory=/opt/attendance-system/lec_panel
user=attendance
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/opt/attendance-system/logs/supervisor_web.log

[program:attendance-celery]
command=/opt/attendance-system/venv/bin/celery -A celery_worker.celery worker --loglevel=info --concurrency=4
directory=/opt/attendance-system/lec_panel
user=attendance
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/opt/attendance-system/logs/supervisor_celery.log
environment=PYTHONPATH="/opt/attendance-system/lec_panel"
```

**Start Services:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start attendance-web
sudo supervisorctl start attendance-celery
```

## Security Considerations

### 1. SSL/TLS Certificate

**Using Let's Encrypt:**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d attendance.example.com
```

### 2. Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. Application Security

- **Change default admin password**
- **Use strong SECRET_KEY**
- **Enable CSRF protection**
- **Set secure cookie flags**
- **Implement rate limiting**
- **Regular security updates**

### 4. Database Security

- Use strong passwords
- Limit database access to application server only
- Enable SSL connections (PostgreSQL)
- Regular backups with encryption

### 5. File Permissions

```bash
# Restrict access to sensitive files
sudo chmod 600 /opt/attendance-system/.env
sudo chmod 600 /opt/attendance-system/attendance.db
```

## Monitoring & Logging

### Application Logs

Logs are stored in `/opt/attendance-system/logs/`:
- `app.log` - Application logs
- `gunicorn_access.log` - HTTP access logs
- `gunicorn_error.log` - Error logs
- `supervisor_*.log` - Process logs

### Log Rotation

**Configure logrotate (`/etc/logrotate.d/attendance`):**
```
/opt/attendance-system/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 attendance attendance
    sharedscripts
    postrotate
        supervisorctl restart attendance-web
        supervisorctl restart attendance-celery
    endscript
}
```

### Monitoring Tools

**System Monitoring:**
- `htop` - CPU and memory usage
- `iotop` - Disk I/O
- `nethogs` - Network usage

**Application Monitoring:**
- Flask-APM (Application Performance Monitoring)
- Sentry (Error tracking)
- Prometheus + Grafana (Metrics)

## Backup & Recovery

### Database Backups

**PostgreSQL:**
```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/opt/attendance-system/backups"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U attendance_user attendance > "$BACKUP_DIR/db_backup_$DATE.sql"
# Keep last 30 days
find "$BACKUP_DIR" -name "db_backup_*.sql" -mtime +30 -delete
```

**SQLite:**
```bash
#!/bin/bash
BACKUP_DIR="/opt/attendance-system/backups"
DATE=$(date +%Y%m%d_%H%M%S)
cp attendance.db "$BACKUP_DIR/attendance_$DATE.db"
# Keep last 30 days
find "$BACKUP_DIR" -name "attendance_*.db" -mtime +30 -delete
```

### File Backups

```bash
# Backup uploads and encodings
tar -czf "/opt/attendance-system/backups/files_$(date +%Y%m%d).tar.gz" \
    uploads/ face_encodings/ student_images/
```

### Automated Backup Script

Create `/opt/attendance-system/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/attendance-system/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
pg_dump -U attendance_user attendance > "$BACKUP_DIR/db_$DATE.sql"

# Backup files
tar -czf "$BACKUP_DIR/files_$DATE.tar.gz" uploads/ face_encodings/ student_images/

# Upload to remote storage (optional)
# rsync -avz "$BACKUP_DIR/" user@backup-server:/backups/attendance/
```

**Schedule with cron:**
```bash
# Daily backup at 2 AM
0 2 * * * /opt/attendance-system/backup.sh
```

## Scaling

### Horizontal Scaling

1. **Load Balancer**: Use Nginx as load balancer
2. **Multiple Workers**: Run multiple Gunicorn instances
3. **Redis Cluster**: For high availability
4. **Database Replication**: PostgreSQL master-slave setup

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Use SSD storage
- Optimize database queries
- Enable caching aggressively

### Celery Scaling

```bash
# Run multiple Celery workers on different servers
celery -A celery_worker.celery worker --hostname=worker1@%h
celery -A celery_worker.celery worker --hostname=worker2@%h
```

## Maintenance

### Regular Tasks

- **Daily**: Check logs, monitor disk space
- **Weekly**: Review performance metrics
- **Monthly**: Security updates, backup verification
- **Quarterly**: Full system audit

### Updates

```bash
# Pull latest code
cd /opt/attendance-system
sudo -u attendance git pull

# Update dependencies
sudo -u attendance venv/bin/pip install -r requirements.txt

# Run migrations
cd lec_panel
sudo -u attendance venv/bin/flask db upgrade

# Restart services
sudo supervisorctl restart attendance-web
sudo supervisorctl restart attendance-celery
```

---

**For troubleshooting, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)**

