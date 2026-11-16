"""
Admin Settings Routes (Phase 7a, calendar added in 7b, rollover in 7c, yearly promotion in 7d)
System settings with validated values: low-attendance threshold, lecturer
correction window, face match sensitivity and final year of study, plus the academic
calendar (the semester dates, one set per academic year), the semester rollover and the
yearly promotion. The definitions, validation and logging live in SettingsAdminService,
RolloverService and PromotionService; this module only moves data in and out.
"""

from flask import (Blueprint, render_template, request, redirect, url_for, flash,
                   Response)
from flask_login import login_required, current_user

from app.decorators.auth import admin_required
from app.services.promotion_service import PromotionService, get_promotion_state
from app.services.rollover_service import RolloverService, get_rollover_state
from app.services.settings_admin_service import SettingsAdminService

admin_settings_bp = Blueprint('admin_settings', __name__, url_prefix='/admin/settings')

service = SettingsAdminService()
rollover_service = RolloverService()
promotion_service = PromotionService()


def _render(overrides=None, errors=None, year=None, calendar_overrides=None, calendar_errors=None):
    return render_template('admin/settings/index.html',
                           groups=service.grouped(overrides), errors=errors or {},
                           calendar=service.calendar_view(year, calendar_overrides),
                           calendar_errors=calendar_errors or {},
                           rollover=get_rollover_state(),
                           promotion=get_promotion_state())


@admin_settings_bp.route('/')
@login_required
@admin_required
def index():
    return _render(year=request.args.get('year', type=int))


@admin_settings_bp.route('/save', methods=['POST'])
@login_required
@admin_required
def save():
    ok, message, errors = service.save(request.form, current_user.username)
    if errors:
        # Redisplay with what was typed (200, not 400: the app's 400 handler would replace the page)
        flash(message, 'danger')
        return _render(overrides=request.form, errors=errors)
    flash(message, 'success' if ok else 'danger')
    return redirect(url_for('admin_settings.index'))


@admin_settings_bp.route('/reset/<key>', methods=['POST'])
@login_required
@admin_required
def reset(key):
    ok, message = service.reset(key, current_user.username)
    flash(message, 'success' if ok else 'danger')
    return redirect(url_for('admin_settings.index'))


# ----------------------------------------------------------------------
# Academic calendar (one set of four dates per academic year)
# ----------------------------------------------------------------------

@admin_settings_bp.route('/calendar/save', methods=['POST'])
@login_required
@admin_required
def calendar_save():
    year = request.form.get('academic_year', type=int)
    ok, message, errors = service.save_calendar(year, request.form, current_user.username)
    if errors:
        flash(message, 'danger')
        return _render(year=year, calendar_overrides=request.form, calendar_errors=errors)
    flash(message, 'success' if ok else 'danger')
    _flash_if_rollover_due(ok)
    return redirect(url_for('admin_settings.index', year=year) + '#calendar')


@admin_settings_bp.route('/calendar/reset/<int:year>', methods=['POST'])
@login_required
@admin_required
def calendar_reset(year):
    ok, message = service.reset_calendar(year, current_user.username)
    flash(message, 'success' if ok else 'danger')
    _flash_if_rollover_due(ok)
    return redirect(url_for('admin_settings.index', year=year) + '#calendar')


def _flash_if_rollover_due(changed):
    """After a calendar edit: say so when the campus semester now needs a rollover."""
    if not changed:
        return
    state = get_rollover_state()
    if state.get('due'):
        flash(state['message'] + " Review it under Semester rollover.", 'warning')


# ----------------------------------------------------------------------
# Semester rollover (preview first, then run once; see RolloverService)
# ----------------------------------------------------------------------

@admin_settings_bp.route('/rollover')
@login_required
@admin_required
def rollover():
    return render_template('admin/settings/rollover.html', **rollover_service.page())


@admin_settings_bp.route('/rollover/run', methods=['POST'])
@login_required
@admin_required
def rollover_run():
    ok, message, _result = rollover_service.run(
        current_user.username, request.form.get('fingerprint', ''))
    flash(message, 'success' if ok else 'danger')
    return redirect(url_for('admin_settings.rollover'))


@admin_settings_bp.route('/rollover/skipped.csv')
@login_required
@admin_required
def rollover_skipped():
    result = rollover_service.skipped_csv()
    if result is None:
        flash("No rollover is due, so there is no list of skipped students.", 'info')
        return redirect(url_for('admin_settings.rollover'))
    data, filename = result
    return Response(data, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


# ----------------------------------------------------------------------
# Yearly promotion (preview first, hold-backs, then run once per academic year)
# ----------------------------------------------------------------------

def _render_promotion(hold_ids=None, pasted_text=''):
    return render_template('admin/settings/promotion.html',
                           **promotion_service.page(hold_ids, pasted_text))


@admin_settings_bp.route('/promotion')
@login_required
@admin_required
def promotion():
    return _render_promotion()


@admin_settings_bp.route('/promotion/preview', methods=['POST'])
@login_required
@admin_required
def promotion_preview():
    # Rendered directly (200): the page shows the preview for the ticked boxes and pasted IDs
    return _render_promotion(request.form.getlist('hold'), request.form.get('hold_ids', ''))


@admin_settings_bp.route('/promotion/run', methods=['POST'])
@login_required
@admin_required
def promotion_run():
    ok, message, _result = promotion_service.run(
        current_user.username, request.form.get('fingerprint', ''), request.form.getlist('hold'))
    flash(message, 'success' if ok else 'danger')
    return redirect(url_for('admin_settings.promotion'))


@admin_settings_bp.route('/promotion/baseline', methods=['POST'])
@login_required
@admin_required
def promotion_baseline():
    ok, message = promotion_service.record_baseline(current_user.username)
    flash(message, 'success' if ok else 'danger')
    return redirect(url_for('admin_settings.promotion'))


@admin_settings_bp.route('/promotion/export', methods=['POST'])
@login_required
@admin_required
def promotion_export():
    result = promotion_service.export_csv(request.form.get('kind', 'all'), request.form.getlist('hold'))
    if result is None:
        flash("No promotion is due, so there is no list to download.", 'info')
        return redirect(url_for('admin_settings.promotion'))
    data, filename = result
    return Response(data, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})