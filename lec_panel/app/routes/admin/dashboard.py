"""
Admin Dashboard Routes
Campus-wide overview: entity counts and recent activity across all users.
"""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import date
import logging

from app.decorators.auth import admin_required
from app.services.admin_service import AdminService
from app.services.rollover_service import get_rollover_state
from app.services.promotion_service import get_promotion_state

logger = logging.getLogger(__name__)

admin_dashboard_bp = Blueprint('admin_dashboard', __name__, url_prefix='/admin/dashboard')


@admin_dashboard_bp.route('/')
@login_required
@admin_required
def index():
    """Admin dashboard - campus-wide stats and recent activity."""
    admin_service = AdminService()

    try:
        dashboard_data = admin_service.get_dashboard_stats()

        return render_template(
            'admin/dashboard.html',
            stats=dashboard_data['stats'],
            recent_activity=dashboard_data['recent_activity'],
            current_date=date.today(),
            current_user=current_user,
            rollover=get_rollover_state(),
            promotion=get_promotion_state()
        )

    except Exception as e:
        logger.error(f'Error loading admin dashboard: {str(e)}', exc_info=True)

        empty_stats = {
            'total_students': 0,
            'total_lecturers': 0,
            'total_courses': 0,
            'total_classes': 0,
            'today_sessions': 0,
            'today_completed': 0,
        }

        return render_template(
            'admin/dashboard.html',
            stats=empty_stats,
            recent_activity=[],
            current_date=date.today(),
            current_user=current_user,
            rollover=None,
            promotion=None
        )