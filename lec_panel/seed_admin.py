"""
One-off script to seed the single admin account, bypassing the
interactive `flask create-admin` CLI prompt (which has been unreliable
under Windows PowerShell piping).

Usage (from the lec_panel folder, with venv active):
    python seed_admin.py

Edit USERNAME / PASSWORD below if you want different values, then
delete this file once the admin account is confirmed working — it's a
one-time setup script, not part of the app.
"""
from app import create_app, db
from app.models.user import Admin

USERNAME = "admin"
PASSWORD = "admin123"

app = create_app()

with app.app_context():
    existing = Admin.get_by_username(USERNAME)
    if existing:
        print(f'Admin user "{USERNAME}" already exists (id={existing.id}). Nothing to do.')
    else:
        admin = Admin(username=USERNAME)
        admin.set_password(PASSWORD)
        db.session.add(admin)
        db.session.commit()
        print(f'\u2713 Admin user "{USERNAME}" created successfully (id={admin.id}).')