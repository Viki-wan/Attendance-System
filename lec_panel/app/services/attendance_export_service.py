"""
Attendance Export Service (Phase 6c)
Builds CSV / Excel / PDF exports of the Phase 6b attendance views.

Design notes:

- Every export is built from AttendanceAdminService methods (the same numbers
  and the same filters as the pages), never from ReportService, which is
  lecturer-scoped (instructor_id) and uses a different rate rule.

- A builder returns a plain "report" dict (title, meta, summary, columns, rows).
  The three renderers only know that shape, so adding a report means adding a
  builder, not touching the renderers.

- CSV is a clean table (UTF-8 with BOM so Excel opens it correctly). Excel and
  PDF also carry a title, the filters used and a summary block.

- Cells that start with = + - @ are prefixed with an apostrophe so a student
  name or note can never run as a spreadsheet formula (CSV/Excel injection).

- PDF needs WeasyPrint. It is imported only when a PDF is requested, so a
  missing or half-installed WeasyPrint never breaks the other formats.

- Exports are capped at MAX_EXPORT_ROWS; the caller is told to narrow the
  filters instead of getting a half file.

Builders raise ExportError(message) for anything the admin should be told.
"""

import csv
import io
import logging
import re
from datetime import datetime
from importlib.util import find_spec

from jinja2 import Template

from app.services.attendance_admin_service import (
    HELD_STATUSES, AttendanceAdminService,
)
from app.services.settings_admin_service import get_low_threshold
from config.constants import ActivityType

logger = logging.getLogger(__name__)

MAX_EXPORT_ROWS = 20000
CHUNK = 500   # rows fetched per page while collecting

FORMATS = {
    'csv': 'text/csv',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'pdf': 'application/pdf',
}
# Only the reports people print get a PDF
PDF_REPORTS = ('session', 'class')

STATUS_FILLS = {'Present': 'D4EDDA', 'Late': 'FFF3CD', 'Absent': 'F8D7DA', 'Excused': 'D1ECF1'}
LOW_FILL = 'F8D7DA'
_FORMULA_START = ('=', '+', '-', '@', '\t', '\r')


class ExportError(Exception):
    """A problem the admin should be told about in plain words."""


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def pdf_installed():
    """Cheap check (no import) used to decide whether to offer PDF buttons."""
    return find_spec('weasyprint') is not None


def _slug(text):
    return re.sub(r'[^A-Za-z0-9._-]+', '-', str(text)).strip('-') or 'report'


def _cell(value):
    """Value safe to write to CSV/Excel: None -> '', formula-looking text defused."""
    if value is None:
        return ''
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def _fmt_rate(rate):
    return '—' if rate is None else f"{rate:.1f}%"


def _filters_text(date_from=None, date_to=None, course=None, year=None, class_id=None,
                  status=None, low=False, query=None):
    parts = []
    if date_from and date_to:
        parts.append(f"dates {date_from.isoformat()} to {date_to.isoformat()}")
    elif date_from:
        parts.append(f"dates from {date_from.isoformat()}")
    elif date_to:
        parts.append(f"dates up to {date_to.isoformat()}")
    if course:
        parts.append(f"course {course}")
    if year:
        parts.append(f"year {year}")
    if class_id:
        parts.append(f"class matching '{class_id}'")
    if query:
        parts.append(f"search '{query}'")
    if status:
        parts.append(f"status {status}")
    if low:
        parts.append(f"low attendance (under {get_low_threshold():g}%)")
    return ', '.join(parts) if parts else 'none (all data)'


def _report(key, title, name, columns, rows, meta=None, summary=None, filters='',
            rate_col=None, status_col=None, pdf_skip=(), landscape=False):
    return {
        'key': key, 'title': title, 'name': name, 'columns': columns, 'rows': rows,
        'meta': meta or [], 'summary': summary or [], 'filters': filters,
        'rate_idx': columns.index(rate_col) if rate_col else None,
        'status_idx': columns.index(status_col) if status_col else None,
        'pdf_skip': set(pdf_skip), 'landscape': landscape,
    }


def _counts_summary(t):
    """Summary lines from a _summarise() dict."""
    return [('Present', t['Present']), ('Late', t['Late']), ('Absent', t['Absent']),
            ('Excused', t['Excused']), ('Records', t['records']),
            ('Attended (Present + Late)', t['attended']), ('Rate', _fmt_rate(t['rate']))]


# ----------------------------------------------------------------------
# Renderers
# ----------------------------------------------------------------------

def _to_csv(report):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(report['columns'])
    for row in report['rows']:
        writer.writerow([_cell(v) for v in row])
    return buf.getvalue().encode('utf-8-sig')


def _to_xlsx(report):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    columns, rows = report['columns'], report['rows']
    low_threshold = get_low_threshold()   # read once per report, at call time
    bold = Font(bold=True)
    thin = Side(style='thin', color='FFBBBBBB')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill('solid', start_color='FF2C3E50', end_color='FF2C3E50')

    wb = Workbook()
    ws = wb.active
    ws.title = re.sub(r'[\[\]:*?/\\]', '-', report['title'])[:31]

    r = 1
    ws.cell(r, 1, report['title']).font = Font(size=14, bold=True)
    r += 1
    for label, value in report['meta']:
        ws.cell(r, 1, label).font = bold
        ws.cell(r, 2, _cell(value))
        r += 1
    if report['summary']:
        r += 1
        ws.cell(r, 1, 'Summary').font = Font(size=11, bold=True)
        r += 1
        for label, value in report['summary']:
            ws.cell(r, 1, label).font = bold
            ws.cell(r, 2, _cell(value))
            r += 1
    r += 1

    header_row = r
    for ci, head in enumerate(columns, 1):
        c = ws.cell(r, ci, head)
        c.font = Font(bold=True, color='FFFFFFFF')
        c.fill = head_fill
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        c.border = border
    r += 1

    rate_idx, status_idx = report['rate_idx'], report['status_idx']
    for row in rows:
        for ci, value in enumerate(row, 1):
            value = _cell(value)
            c = ws.cell(r, ci, None if value == '' else value)
            c.border = border
            if rate_idx is not None and ci - 1 == rate_idx and isinstance(value, (int, float)):
                c.number_format = '0.0'
                if value < low_threshold:
                    c.fill = PatternFill('solid', start_color='FF' + LOW_FILL, end_color='FF' + LOW_FILL)
            if status_idx is not None and ci - 1 == status_idx and value in STATUS_FILLS:
                fill = 'FF' + STATUS_FILLS[value]
                c.fill = PatternFill('solid', start_color=fill, end_color=fill)
        r += 1

    for ci, head in enumerate(columns, 1):
        longest = max([len(str(head))] + [len(str(row[ci - 1])) for row in rows[:500]
                                          if row[ci - 1] is not None])
        ws.column_dimensions[get_column_letter(ci)].width = min(max(longest + 2, 10), 45)
    ws.column_dimensions['A'].width = max(ws.column_dimensions['A'].width or 0, 24)

    ws.freeze_panes = f"A{header_row + 1}"
    if rows:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{r - 1}"
    ws.print_title_rows = f"{header_row}:{header_row}"
    ws.page_setup.orientation = 'landscape' if len(columns) > 7 else 'portrait'

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


_PDF_TEMPLATE = Template("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{ title }}</title>
<style>
@page { size: A4 {{ orientation }}; margin: 1.5cm 1.3cm;
        @bottom-center { content: "Page " counter(page) " of " counter(pages);
                         font-family: Arial, sans-serif; font-size: 8pt; color: #777; } }
body { font-family: Arial, Helvetica, sans-serif; font-size: 9pt; color: #222; }
h1 { font-size: 16pt; margin: 0 0 6pt; color: #2c3e50; }
.meta td { border: none; padding: 1pt 10pt 1pt 0; font-size: 9pt; }
.meta td:first-child { font-weight: bold; white-space: nowrap; }
.summary { margin: 8pt 0 10pt; }
.chip { display: inline-block; border: 1px solid #ccc; border-radius: 3pt; padding: 2pt 7pt;
        margin: 0 4pt 4pt 0; background: #f4f6f8; }
.chip b { margin-left: 3pt; }
table.data { width: 100%; border-collapse: collapse; margin-top: 6pt; }
table.data th { background: #34495e; color: #fff; padding: 4pt 5pt; text-align: left; font-size: 8.5pt; }
table.data td { border: 1px solid #ddd; padding: 3pt 5pt; }
table.data tr { page-break-inside: avoid; }
table.data tbody tr:nth-child(even) { background: #fafafa; }
.num { text-align: right; }
.st-present { background: #d4edda; } .st-late { background: #fff3cd; }
.st-absent { background: #f8d7da; } .st-excused { background: #d1ecf1; }
.low { background: #f8d7da; color: #721c24; font-weight: bold; }
.foot { margin-top: 10pt; font-size: 8pt; color: #777; }
</style></head><body>
<h1>{{ title }}</h1>
<table class="meta">
{% for label, value in meta %}<tr><td>{{ label }}</td><td>{{ value }}</td></tr>{% endfor %}
</table>
{% if summary %}<div class="summary">
{% for label, value in summary %}<span class="chip">{{ label }}<b>{{ value }}</b></span>{% endfor %}
</div>{% endif %}
<table class="data">
<thead><tr>{% for h in headers %}<th>{{ h }}</th>{% endfor %}</tr></thead>
<tbody>
{% for row in rows %}<tr>{% for c in row %}<td class="{{ c.c }}">{{ c.t }}</td>{% endfor %}</tr>
{% endfor %}</tbody></table>
{% if not rows %}<p>No rows.</p>{% endif %}
<div class="foot">Generated {{ generated }} UTC &middot; Attended = Present + Late; Excused counts as expected but not attended.
Rates under {{ threshold }}% are highlighted.</div>
</body></html>""", autoescape=True)


def _pdf_rows(report):
    keep = [i for i, h in enumerate(report['columns']) if h not in report['pdf_skip']]
    rate_idx, status_idx = report['rate_idx'], report['status_idx']
    low_threshold = get_low_threshold()
    out = []
    for row in report['rows']:
        cells = []
        for i in keep:
            v = row[i]
            css = []
            if v is None:
                text = ''
            elif isinstance(v, float):
                text = f"{v:.1f}%" if i == rate_idx else f"{v:g}"
                css.append('num')
            elif isinstance(v, int):
                text = str(v)
                css.append('num')
            else:
                text = str(v)
            if i == rate_idx and isinstance(v, (int, float)) and v < low_threshold:
                css.append('low')
            if i == status_idx:
                css.append('st-' + str(v).lower().replace(' ', '-'))
            cells.append({'t': text, 'c': ' '.join(css)})
        out.append(cells)
    return [report['columns'][i] for i in keep], out


def _to_pdf(report):
    if not pdf_installed():
        raise ExportError("PDF export is not available: WeasyPrint is not installed on this server. "
                          "Use Excel or CSV instead")
    try:
        from weasyprint import HTML
    except Exception as e:   # ImportError, or OSError when its native libraries are missing
        logger.error(f"WeasyPrint could not be loaded: {e}")
        raise ExportError("PDF export is not available: WeasyPrint could not be loaded on this server. "
                          "Use Excel or CSV instead")
    headers, rows = _pdf_rows(report)
    html = _PDF_TEMPLATE.render(
        title=report['title'], meta=report['meta'], summary=report['summary'],
        headers=headers, rows=rows, threshold=f"{get_low_threshold():g}",
        orientation='landscape' if report['landscape'] else 'portrait',
        generated=datetime.utcnow().strftime('%Y-%m-%d %H:%M'))
    try:
        return HTML(string=html).write_pdf()
    except Exception as e:
        logger.error(f"PDF build error: {e}")
        raise ExportError("Could not build the PDF. Use Excel or CSV instead")


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------

class AttendanceExportService:
    """Report builders (from the 6b service) plus the three renderers."""

    def __init__(self):
        self._att = AttendanceAdminService()

    # ---- paging helper ------------------------------------------------

    @staticmethod
    def _collect(fetch, rows_key, total_key):
        """Walk every page of a paged 6b method. Returns (first_page_result, all_rows)."""
        first = fetch(1)
        if first is None:
            return None, []
        total = first[total_key]
        if total > MAX_EXPORT_ROWS:
            raise ExportError(f"This export has {total:,} rows; the limit is {MAX_EXPORT_ROWS:,}. "
                              f"Narrow the filters and try again")
        rows = list(first[rows_key])
        page = 1
        while page < first['pages']:
            page += 1
            rows.extend(fetch(page)[rows_key])
        return first, rows

    # ---- builders -----------------------------------------------------

    def session_report(self, session_id):
        """One session's sheet: every expected student, including those with no record."""
        data = self._att.get_sheet(session_id)
        if not data:
            raise ExportError("Session not found")
        s, sm = data['session'], data['summary']
        if s['status'] not in HELD_STATUSES:
            raise ExportError("Only held sessions (completed or ongoing) have attendance to export")

        columns = ['Student ID', 'Name', 'Status', 'Method', 'Confidence (%)', 'Marked by',
                   'Marked at (UTC)', 'In class now', 'Corrected by admin', 'Last note']
        rows = []
        for e in data['entries']:
            conf = None
            if e['confidence'] is not None and e['status'] in ('Present', 'Late'):
                conf = round(e['confidence'] * 100)
            rows.append([
                e['student_id'], e['name'], e['status'] or 'No record', e['method'], conf,
                e['marked_by'] if e['has_row'] else '', e['timestamp'],
                'Yes' if e['in_class'] else 'No', 'Yes' if e['corrected'] else '', e['last_note'],
            ])
        meta = [
            ('Session', f"#{s['session_id']}"),
            ('Class', f"{s['class_id']} - {s['class_name']}"),
            ('Course', f"{s['course_code']} {s['course_name']}".strip()),
            ('Year', s['year']),
            ('Date', f"{s['day_name']} {s['date_raw']}".strip()),
            ('Time', f"{s['start_time']}-{s['end_time']}"),
            ('Session status', s['status'].capitalize()),
        ]
        summary = [('Present', sm['Present']), ('Late', sm['Late']), ('Absent', sm['Absent']),
                   ('Excused', sm['Excused']), ('No record', sm['no_record']),
                   ('Expected', sm['expected']), ('Attended (Present + Late)', sm['attended']),
                   ('Rate', _fmt_rate(sm['rate']))]
        return _report('session', 'Session attendance sheet',
                       f"attendance_sheet_{s['class_id']}_{s['date_raw']}", columns, rows,
                       meta=meta, summary=summary, status_col='Status',
                       pdf_skip=('Last note',), landscape=True)

    def class_report(self, class_id, date_from=None, date_to=None, sort='student'):
        """One class: per-student numbers over the completed sessions in range."""
        d = self._att.class_detail(class_id, date_from, date_to, sort=sort)
        if not d:
            raise ExportError("Class not found")
        c = d['class']
        columns = ['Student ID', 'Name', 'Present', 'Late', 'Absent', 'Excused',
                   'Records', 'Attended', 'Rate (%)']
        rows = [[s['student_id'], s['name'], s['Present'], s['Late'], s['Absent'], s['Excused'],
                 s['records'], s['attended'], s['rate']] for s in d['students']]
        filters = _filters_text(date_from=date_from, date_to=date_to)
        meta = [
            ('Class', f"{c['class_id']} - {c['class_name']}"),
            ('Course', f"{c['course_code']} {c.get('course_name') or ''}".strip()),
            ('Year', c['year']),
            ('Filters', filters),
            ('Sessions held (completed)', d['sessions_held']),
            ('Students listed', f"{len(d['students'])} active students of course {c['course_code']}, year {c['year']}"),
        ]
        return _report('class', 'Class attendance', f"attendance_class_{c['class_id']}",
                       columns, rows, meta=meta, summary=_counts_summary(d['totals']),
                       filters=filters, rate_col='Rate (%)')

    def classes_report(self, date_from=None, date_to=None, course_code=None, year=None,
                       class_id=None, sort='class', low_only=False):
        """One row per class (same rows as the Classes tab)."""
        items = self._att.class_summaries(
            date_from=date_from, date_to=date_to, course_code=course_code, year=year,
            class_id=class_id, sort=sort, low_only=low_only)
        if len(items) > MAX_EXPORT_ROWS:
            raise ExportError("Too many classes to export; narrow the filters")
        columns = ['Class ID', 'Class name', 'Course', 'Year', 'Sessions', 'Present', 'Late',
                   'Absent', 'Excused', 'Records', 'Attended', 'Rate (%)']
        rows = [[i['class_id'], i['class_name'], i['course_code'], i['year'], i['sessions'],
                 i['Present'], i['Late'], i['Absent'], i['Excused'], i['records'],
                 i['attended'], i['rate']] for i in items]
        filters = _filters_text(date_from, date_to, course_code, year, class_id, low=low_only)
        title = 'Low-attendance classes' if low_only else 'Attendance by class'
        meta = [('Filters', filters), ('Classes', len(rows)),
                ('Scope', 'Completed sessions only')]
        return _report('classes', title, 'attendance_classes_low' if low_only else 'attendance_classes',
                       columns, rows, meta=meta, filters=filters, rate_col='Rate (%)',
                       landscape=True)

    def sessions_report(self, date_from=None, date_to=None, course_code=None, year=None,
                        class_id=None, status=None, low_only=False):
        """Held sessions (same rows as the Sessions tab)."""
        def fetch(page):
            return self._att.list_held_sessions(
                date_from=date_from, date_to=date_to, course_code=course_code, year=year,
                class_id=class_id, status=status, low_only=low_only, page=page, per_page=CHUNK)
        _, items = self._collect(fetch, 'rows', 'total')
        columns = ['Date', 'Day', 'Start', 'End', 'Class ID', 'Class name', 'Course', 'Year',
                   'Status', 'Present', 'Late', 'Absent', 'Excused', 'Attended', 'Expected', 'Rate (%)']
        rows = []
        for r in items:
            c = r['counts']
            rows.append([r['date_raw'], r['day_label'], r['start_time'], r['end_time'],
                         r['class_id'], r['class_name'], r['course_code'], r['year'],
                         r['status'].capitalize(), c['Present'], c['Late'], c['Absent'],
                         c['Excused'], r['attendance_count'], r['total_students'], r['rate']])
        filters = _filters_text(date_from, date_to, course_code, year, class_id, status, low_only)
        meta = [('Filters', filters), ('Sessions', len(rows))]
        return _report('sessions', 'Held sessions', 'attendance_sessions', columns, rows,
                       meta=meta, filters=filters, rate_col='Rate (%)', landscape=True)

    def students_report(self, query=None, course_code=None, year=None, low_only=False):
        """Students with their overall attendance (same rows as the Students tab)."""
        def fetch(page):
            return self._att.list_students(query=query, course_code=course_code, year=year,
                                           low_only=low_only, page=page, per_page=CHUNK)
        _, items = self._collect(fetch, 'rows', 'total')
        columns = ['Student ID', 'Name', 'Course', 'Year', 'Active', 'Records', 'Present', 'Late',
                   'Absent', 'Excused', 'Attended', 'Rate (%)']
        rows = [[i['student_id'], i['name'], i['course'], i['year'], 'Yes' if i['is_active'] else 'No',
                 i['records'], i['Present'], i['Late'], i['Absent'], i['Excused'],
                 i['attended'], i['rate']] for i in items]
        filters = _filters_text(course=course_code, year=year, low=low_only, query=query)
        title = 'Low-attendance students' if low_only else 'Attendance by student'
        meta = [('Filters', filters), ('Students', len(rows)),
                ('Scope', 'Completed sessions only')]
        return _report('students', title, 'attendance_students_low' if low_only else 'attendance_students',
                       columns, rows, meta=meta, filters=filters, rate_col='Rate (%)',
                       landscape=True)

    def student_report(self, student_id, date_from=None, date_to=None):
        """One student's session-by-session history."""
        def fetch(page):
            return self._att.get_student(student_id, date_from, date_to, page=page, per_page=CHUNK)
        first, items = self._collect(fetch, 'history', 'total_rows')
        if not first:
            raise ExportError("Student not found")
        st = first['student']
        columns = ['Date', 'Start', 'End', 'Class ID', 'Class', 'Session', 'Status', 'Method',
                   'Confidence (%)', 'Corrected by admin']
        rows = []
        for h in items:
            conf = None
            if h['confidence'] is not None and h['status'] in ('Present', 'Late'):
                conf = round(h['confidence'] * 100)
            rows.append([h['date_raw'], h['start_time'], h['end_time'], h['class_id'], h['class_name'],
                         h['session_status'].capitalize(), h['status'], h['method'], conf,
                         'Yes' if h['corrected'] else ''])
        filters = _filters_text(date_from=date_from, date_to=date_to)
        meta = [
            ('Student', f"{st['student_id']} - {st['name']}"),
            ('Cohort', f"{st['course']} year {st['year']}" if st['year'] else st['course']),
            ('Active', 'Yes' if st['is_active'] else 'No'),
            ('Filters', filters),
            ('Scope', 'Rates count completed sessions only; the history also lists ongoing ones'),
        ]
        summary = _counts_summary(first['totals'])
        for c in first['per_class']:
            summary.append((f"Class {c['class_id']}", f"{c['attended']}/{c['records']} ({_fmt_rate(c['rate'])})"))
        return _report('student', 'Student attendance history', f"attendance_student_{st['student_id']}",
                       columns, rows, meta=meta, summary=summary, filters=filters,
                       status_col='Status', landscape=True)

    # ---- output -------------------------------------------------------

    def render(self, report, fmt):
        """(bytes, mimetype) for the report in the requested format."""
        if fmt == 'csv':
            data = _to_csv(report)
        elif fmt == 'xlsx':
            data = _to_xlsx(report)
        elif fmt == 'pdf':
            if report['key'] not in PDF_REPORTS:
                raise ExportError("PDF is not offered for this report")
            data = _to_pdf(report)
        else:
            raise ExportError("Unknown export format")
        return data, FORMATS[fmt]

    @staticmethod
    def filename(report, fmt):
        return f"{_slug(report['name'])}_{datetime.now().strftime('%Y%m%d')}.{fmt}"

    def log_export(self, admin_username, report, fmt):
        """Audit trail. Never raises: a logging problem must not lose the download."""
        try:
            self._att._log_admin_activity(
                admin_username, getattr(ActivityType, 'REPORT_GENERATED', 'report_generated'),
                f"Admin exported {report['title'].lower()} as {fmt.upper()}; "
                f"filters: {report['filters'] or 'n/a'}; {len(report['rows'])} row(s)")
        except Exception as e:
            logger.error(f"Export logging error: {e}")