#!/usr/bin/env python3
"""
Re-lay the campus timetable so it has no clashes.

The faker only avoided clashes inside a cohort. Lecturers were assigned
afterwards, so the generated timetable double-books them all over the place.
This script keeps every class's slot count and slot length, keeps to the slot
times already used in the data, and moves each slot to a day and time where:

    * the class's lecturer(s) are free,
    * no other class of the same course + year + semester is running, and
    * the class has no other slot at that time.

Class sessions are NEVER touched: attendance history stays exactly as it is.
Only the weekly timetable rows of the classes in scope are replaced, and the
new rows get the upcoming semester window (so they are not 'expired').

It is a dry run unless you pass --apply. With --apply it first copies the
database to <db>.bak-<timestamp>.

    python tools/relayout_timetable.py --db "path/to/attendance.db"
    python tools/relayout_timetable.py --db "path/to/attendance.db" --apply

Stop the Flask server before using --apply.
"""

import argparse
import importlib.util
import os
import random
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path


def _load_calendar_rules():
    """
    The semester rules live in app/utils/calendar_rules.py (standard library only),
    the same file the web app uses. Load it by path so this tool needs neither the
    Flask app nor an app context, and keeps no copy of the dates.
    """
    path = Path(__file__).resolve().parent.parent / 'app' / 'utils' / 'calendar_rules.py'
    if not path.is_file():
        sys.exit(f"Cannot find the shared calendar rules: {path}")
    spec = importlib.util.spec_from_file_location('calendar_rules', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules['calendar_rules'] = module
    spec.loader.exec_module(module)
    return module


rules = _load_calendar_rules()
DAY_NAMES = {0: 'Sun', 1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat'}


def to_min(hhmm):
    hours, minutes = str(hhmm)[:5].split(':')
    return int(hours) * 60 + int(minutes)


def to_hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def overlaps(s1, e1, s2, e2):
    return s1 < e2 and s2 < e1


def load_calendar(conn):
    """
    Read the academic calendar the admin saved on /admin/settings (one
    'academic_calendar_<year>' row per academic year in the settings table).
    Returns (windows_for, stored): windows_for(year) gives the effective windows
    of an academic year (saved dates, else the defaults), stored lists the years
    that have saved dates. A missing settings table or an unusable row means defaults.
    """
    stored = {}
    try:
        for key, value in conn.execute(
                "SELECT setting_key, setting_value FROM settings "
                "WHERE setting_key LIKE ?", (rules.KEY_PREFIX + '%',)):
            year = rules.year_from_key(key)
            windows = rules.parse_windows(value)
            if year is not None and windows is not None and rules.is_valid_windows(year, windows):
                stored[year] = windows
    except sqlite3.Error:
        pass

    def windows_for(academic_year):
        return stored.get(academic_year) or rules.default_windows(academic_year)

    return windows_for, stored


def semester_window(semester, today, windows_for):
    """The (start, end) of the semester window that contains today or is the next to begin."""
    return rules.semester_window(semester, today, windows_for)


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------

def load(conn, semesters):
    ph = ",".join("?" * len(semesters))
    classes = {}
    for cid, course, year, sem in conn.execute(
            f"SELECT class_id, course_code, year, semester FROM classes "
            f"WHERE is_active = 1 AND semester IN ({ph})", semesters):
        classes[cid] = {'course': course, 'year': year, 'sem': int(sem)}

    lecturers = {cid: set() for cid in classes}
    for cid, iid in conn.execute("SELECT class_id, instructor_id FROM class_instructors"):
        if cid in lecturers:
            lecturers[cid].add(iid)

    entries = []
    for row in conn.execute(
            "SELECT id, class_id, day_of_week, start_time, end_time FROM timetable "
            "WHERE is_active = 1"):
        if row[1] in classes:
            entries.append({'id': row[0], 'class_id': row[1], 'day': row[2],
                            'start': to_min(row[3]), 'end': to_min(row[4])})
    return classes, lecturers, entries


def count_clashes(placements, classes, lecturers):
    """placements: iterable of (class_id, day, start, end). Mirrors the app's rules."""
    by_slot = {}
    for cid, day, start, end in placements:
        by_slot.setdefault((classes[cid]['sem'], day), []).append((cid, start, end))

    counts = {'lecturer': 0, 'cohort': 0, 'class': 0}
    for items in by_slot.values():
        for i, (a, a_s, a_e) in enumerate(items):
            for b, b_s, b_e in items[i + 1:]:
                if not overlaps(a_s, a_e, b_s, b_e):
                    continue
                if a == b:
                    counts['class'] += 1
                    continue
                if lecturers[a] & lecturers[b]:
                    counts['lecturer'] += 1
                if (classes[a]['course'], classes[a]['year']) == (classes[b]['course'], classes[b]['year']):
                    counts['cohort'] += 1
    return counts


# ----------------------------------------------------------------------
# Placement
# ----------------------------------------------------------------------

def candidate_slots(pool, duration):
    """Slot times already used in the data with this length; else an hourly grid."""
    slots = sorted(s for s in pool if s[1] - s[0] == duration)
    if slots:
        return slots
    return [(m, m + duration) for m in range(8 * 60, 18 * 60 - duration + 1, 60)]


def attempt(items, classes, lecturers, pools, days, rng):
    lec_load, cohort_load = {}, {}
    for it in items:
        c = classes[it['class_id']]
        cohort_load[(c['course'], c['year'], c['sem'])] = cohort_load.get((c['course'], c['year'], c['sem']), 0) + 1
        for lec in lecturers[it['class_id']]:
            lec_load[(lec, c['sem'])] = lec_load.get((lec, c['sem']), 0) + 1

    def difficulty(it):
        c = classes[it['class_id']]
        busiest = max((lec_load.get((l, c['sem']), 0) for l in lecturers[it['class_id']]), default=0)
        return busiest * 2 + cohort_load[(c['course'], c['year'], c['sem'])] + it['duration'] / 60

    order = sorted(items, key=lambda it: -(difficulty(it) + rng.random() * 0.5))

    busy_lec, busy_cohort, busy_class = {}, {}, {}
    placed, unplaced = [], []

    for it in order:
        cid, dur = it['class_id'], it['duration']
        c = classes[cid]
        cohort = (c['course'], c['year'], c['sem'])
        best_cost, best = None, []

        for day in days:
            lec_busy = [busy_lec.get((l, c['sem'], day), []) for l in lecturers[cid]]
            coh_busy = busy_cohort.get((cohort, day), [])
            cls_busy = busy_class.get((cid, day), [])

            for start, end in candidate_slots(pools[c['sem']], dur):
                if any(overlaps(start, end, s, e) for s, e in coh_busy):
                    continue
                if any(overlaps(start, end, s, e) for s, e in cls_busy):
                    continue
                if any(overlaps(start, end, s, e) for busy in lec_busy for s, e in busy):
                    continue

                # Prefer quieter days so the week stays balanced
                cost = (sum(e - s for s, e in coh_busy) / 60
                        + max((sum(e - s for s, e in b) for b in lec_busy), default=0) / 60
                        + (100 if cls_busy else 0) + rng.random() * 0.5)
                if best_cost is None or cost < best_cost - 1e-9:
                    best_cost, best = cost, [(day, start, end)]
                elif abs(cost - best_cost) <= 1e-9:
                    best.append((day, start, end))

        if not best:
            unplaced.append(it)
            continue

        day, start, end = rng.choice(best)
        for lec in lecturers[cid]:
            busy_lec.setdefault((lec, c['sem'], day), []).append((start, end))
        busy_cohort.setdefault((cohort, day), []).append((start, end))
        busy_class.setdefault((cid, day), []).append((start, end))
        placed.append({'class_id': cid, 'day': day, 'start': start, 'end': end})

    return placed, unplaced


def solve(items, classes, lecturers, pools, days, seed, attempts):
    best = None
    for i in range(attempts):
        placed, unplaced = attempt(items, classes, lecturers, pools, days, random.Random(seed + i))
        if best is None or len(unplaced) < len(best[1]):
            best = (placed, unplaced)
        if not unplaced:
            break
    return best


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Re-lay the timetable so it has no clashes.")
    ap.add_argument('--db', required=True, help="path to the SQLite database file")
    ap.add_argument('--semester', default='all', choices=['1', '2', 'all'])
    ap.add_argument('--days', default='1,2,3,4,5', help="teaching days, 0=Sunday (default Mon-Fri)")
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--attempts', type=int, default=300, help="random restarts to find a full solution")
    ap.add_argument('--today', help="override today's date (YYYY-MM-DD), for testing")
    ap.add_argument('--apply', action='store_true', help="write the changes (default: dry run)")
    args = ap.parse_args()

    if not os.path.isfile(args.db):
        sys.exit(f"Database not found: {args.db}")

    today = datetime.strptime(args.today, '%Y-%m-%d').date() if args.today else date.today()
    semesters = [1, 2] if args.semester == 'all' else [int(args.semester)]
    days = [int(d) for d in args.days.split(',') if d.strip() != '']

    conn = sqlite3.connect(args.db)
    windows_for, stored_years = load_calendar(conn)
    classes, lecturers, entries = load(conn, semesters)
    if not entries:
        sys.exit("No active timetable entries found for those semesters; nothing to do.")

    items = [{'class_id': e['class_id'], 'duration': e['end'] - e['start']} for e in entries]
    pools = {s: {(e['start'], e['end']) for e in entries if classes[e['class_id']]['sem'] == s}
             for s in semesters}

    print(f"Database : {args.db}")
    print(f"Mode     : {'APPLY' if args.apply else 'dry run (nothing is written)'}")
    print(f"Today    : {today}")
    print("Calendar : " + (("saved dates for " + ", ".join(rules.year_label(y) for y in sorted(stored_years))
                            + ", defaults for other years") if stored_years else "defaults (no saved dates)") + "\n")

    before = count_clashes([(e['class_id'], e['day'], e['start'], e['end']) for e in entries],
                           classes, lecturers)
    print(f"Before   : {len(entries)} slots in {len({e['class_id'] for e in entries})} classes - "
          f"{before['lecturer']} lecturer clashes, {before['cohort']} cohort clashes, "
          f"{before['class']} same-class clashes")

    all_placed, all_unplaced = [], []
    for sem in semesters:
        sem_items = [it for it in items if classes[it['class_id']]['sem'] == sem]
        if not sem_items:
            continue
        placed, unplaced = solve(sem_items, classes, lecturers, pools, days, args.seed, args.attempts)
        all_placed += placed
        all_unplaced += unplaced
        per_day = {d: sum(1 for p in placed if p['day'] == d) for d in days}
        print(f"\nSemester {sem}: {len(sem_items)} slots -> {len(placed)} placed, {len(unplaced)} could not be placed")
        print("  per day : " + ", ".join(f"{DAY_NAMES[d]} {n}" for d, n in per_day.items()))

    after = count_clashes([(p['class_id'], p['day'], p['start'], p['end']) for p in all_placed],
                          classes, lecturers)
    print(f"\nAfter    : {after['lecturer']} lecturer clashes, {after['cohort']} cohort clashes, "
          f"{after['class']} same-class clashes")

    if all_unplaced:
        print("\nCould not be placed (they will have NO slot until you add one by hand):")
        load_by_lec = {}
        for it in items:
            for lec in lecturers[it['class_id']]:
                load_by_lec[lec] = load_by_lec.get(lec, 0) + 1
        for it in all_unplaced:
            c = classes[it['class_id']]
            lecs = ", ".join(f"{l} ({load_by_lec.get(l, 0)} slots)" for l in sorted(lecturers[it['class_id']])) or "no lecturer"
            print(f"  {it['class_id']}  {c['course']} year {c['year']}  {it['duration'] // 60}h  lecturers: {lecs}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write this layout.")
        return

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup, n = f"{args.db}.bak-{stamp}", 1
    while os.path.exists(backup):          # never overwrite an earlier backup
        n += 1
        backup = f"{args.db}.bak-{stamp}-{n}"
    shutil.copy2(args.db, backup)
    print(f"\nBackup written: {backup}")

    windows = {s: semester_window(s, today, windows_for) for s in semesters}
    try:
        conn.execute("BEGIN")
        ids = [e['id'] for e in entries]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            conn.execute(f"DELETE FROM timetable WHERE id IN ({','.join('?' * len(chunk))})", chunk)
        conn.executemany(
            "INSERT INTO timetable (class_id, day_of_week, start_time, end_time, is_active, "
            "effective_from, effective_to) VALUES (?, ?, ?, ?, 1, ?, ?)",
            [(p['class_id'], p['day'], to_hhmm(p['start']), to_hhmm(p['end']),
              windows[classes[p['class_id']]['sem']][0].isoformat(),
              windows[classes[p['class_id']]['sem']][1].isoformat())
             for p in all_placed])
        conn.commit()
    except Exception:
        conn.rollback()
        print("FAILED - nothing was changed. Your backup is untouched.")
        raise

    print(f"Done: {len(entries)} old entries replaced by {len(all_placed)} new ones.")
    for s, (start, end) in windows.items():
        print(f"  Semester {s} entries are effective {start} to {end}")
    print("Open the Timetable > Conflicts page to confirm, then use Generate sessions.")


if __name__ == '__main__':
    main()