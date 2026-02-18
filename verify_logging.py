import os
import sys
import shutil
from app import create_app

def verify_logging():
    print("Initializing app...")
    try:
        app = create_app()
    except ImportError as e:
        print(f"CRITICAL ERROR: Failed to import app: {e}")
        return

    print("Logging messages...")
    app.logger.debug("This is a DEBUG message")
    app.logger.info("This is an INFO message")
    app.logger.warning("This is a WARNING message")
    app.logger.error("This is an ERROR message")
    
    # Check if log file exists
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join('logs', today_str, 'app.log')
    
    if os.path.exists(log_file):
        print(f"SUCCESS: Log file created at {log_file}")
        with open(log_file, 'r') as f:
            content = f.read()
            if "This is a DEBUG message" in content:
                print("SUCCESS: Log content verified")
            else:
                print("ERROR: Log content missing specific messages")
    else:
        print(f"ERROR: Log file not found at {log_file}")

    print("Verification complete.")

if __name__ == "__main__":
    verify_logging()
