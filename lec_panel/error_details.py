# error_details.py
from flask import Flask
import traceback
import sys

app = Flask(__name__)

@app.route('/')
def index():
    return "Working!"

if __name__ == '__main__':
    try:
        print("Python version:", sys.version)
        print("Attempting to start Flask on 127.0.0.1:5001...")
        app.run(host='127.0.0.1', port=5001, debug=True)
    except Exception as e:
        print("\n" + "="*60)
        print("FULL ERROR DETAILS:")
        print("="*60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nFull traceback:")
        traceback.print_exc()
        print("="*60)