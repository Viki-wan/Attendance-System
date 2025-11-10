"""
Celery Worker Entry Point
Run with: python -m celery -A celery_worker.celery worker --loglevel=info --pool=solo
For beat scheduler: celery -A celery_worker.celery beat --loglevel=info
"""

from celery.schedules import crontab
from app import create_app, celery as celery_app

# Create Flask app and push context
app = create_app()
app.app_context().push()

# Now configure Celery with the Flask app config
# This ensures Celery uses Redis from config, not default AMQP
celery_app.conf.update(
    broker_url=app.config['CELERY_BROKER_URL'],
    result_backend=app.config['CELERY_RESULT_BACKEND'],
    task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
    result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
    accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
    timezone=app.config.get('CELERY_TIMEZONE', 'UTC'),
    enable_utc=app.config.get('CELERY_ENABLE_UTC', True),
    task_track_started=app.config.get('CELERY_TASK_TRACK_STARTED', True),
    task_time_limit=app.config.get('CELERY_TASK_TIME_LIMIT', 300),
    task_soft_time_limit=app.config.get('CELERY_TASK_SOFT_TIME_LIMIT', 240),
)

# Configure Celery beat schedule
celery_app.conf.beat_schedule = {
    'send-session-reminders': {
        'task': 'app.tasks.email_tasks.send_session_reminders',
        'schedule': crontab(minute=0),  # Every hour
    },
    'send-weekly-summaries': {
        'task': 'app.tasks.email_tasks.send_weekly_summaries',
        'schedule': crontab(day_of_week=1, hour=8, minute=0),  # Monday 8 AM
    },
    'check-low-attendance': {
        'task': 'app.tasks.email_tasks.check_low_attendance',
        'schedule': crontab(hour=18, minute=0),  # Daily at 6 PM
    },
}

# Make celery available for celery command
celery = celery_app

# Print configuration for debugging
if __name__ == '__main__':
    print('\n' + '='*60)
    print('🔧 Celery Worker Configuration')
    print('='*60)
    print(f'Broker URL: {celery_app.conf.broker_url}')
    print(f'Result Backend: {celery_app.conf.result_backend}')
    print(f'Timezone: {celery_app.conf.timezone}')
    print('='*60 + '\n')