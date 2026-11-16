from app import create_app, db
from app.models.user import Instructor

app = create_app()

with app.app_context():
    # Find all instructors with scrypt hashes
    instructors = Instructor.query.filter(
        Instructor.password.like('scrypt:%')
    ).all()
    
    print(f"Found {len(instructors)} instructors with scrypt hashes")
    
    for instructor in instructors:
        print(f"Resetting password for: {instructor.instructor_id}")
        instructor.set_password(instructor.instructor_id)
    
    db.session.commit()
    print("✅ All passwords reset to instructor_id")