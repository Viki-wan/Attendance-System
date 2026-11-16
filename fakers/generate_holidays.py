"""
Generate holiday data
"""
import sqlite3
from faker_config import *
from datetime import datetime

def generate_holidays_data(db_path=DB_PATH):
    """Generate and insert holiday data"""
    print("=" * 50)
    print("GENERATING HOLIDAYS")
    print("=" * 50)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    holidays_data = []
    
    for date_str, name in KENYAN_HOLIDAYS:
        holiday = {
            'name': name,
            'date': date_str,
            'description': f"Kenyan Public Holiday: {name}",
            'is_recurring': 0,  # Can be updated manually for recurring holidays
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        holidays_data.append(holiday)
        print(f"✓ {date_str}: {name}")
    
    # Insert into database
    cursor.executemany("""
        INSERT OR REPLACE INTO holidays 
        (name, date, description, is_recurring, created_at)
        VALUES (:name, :date, :description, :is_recurring, :created_at)
    """, holidays_data)
    
    conn.commit()
    conn.close()
    
    print(f"\n✓ Successfully generated {len(holidays_data)} holidays")
    return holidays_data

if __name__ == "__main__":
    generate_holidays_data()