from lec_panel.app.models.session import ClassSession
s = ClassSession.query.first()
print(repr(s.date), repr(s.start_time), type(s.date), type(s.start_time))