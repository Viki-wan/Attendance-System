import sys
from pathlib import Path

# Allow running this file from the project root or lec_panel/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app
from app.models.session import ClassSession

app = create_app()

with app.app_context():
    s = ClassSession.query.first()
    if s is None:
        print("No class_sessions rows found")
    else:
        print(repr(s.date), repr(s.start_time), type(s.date), type(s.start_time))
