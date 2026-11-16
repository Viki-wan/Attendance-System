import sqlite3, bcrypt
import os
import sys

# Ensure the project root is on sys.path so that `config` can be imported
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.utils_constants import DATABASE_PATH, DEFAULT_ADMIN_USERNAME

conn = sqlite3.connect(DATABASE_PATH)
cur = conn.cursor()

username = DEFAULT_ADMIN_USERNAME  # or set explicitly: 'admin'
new_plain = "admin123"            # or set your new password here

hashed = bcrypt.hashpw(new_plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Ensure the admin row exists; insert if missing
cur.execute("SELECT 1 FROM admin WHERE username=?", (username,))
if not cur.fetchone():
    cur.execute("INSERT INTO admin (username, password) VALUES (?, ?)", (username, hashed))
else:
    cur.execute("UPDATE admin SET password=? WHERE username=?", (hashed, username))

conn.commit()
conn.close()
print("Updated admin password for:", username)