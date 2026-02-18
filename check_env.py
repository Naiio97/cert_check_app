
try:
    from dotenv import load_dotenv
    print("SUCCESS: load_dotenv imported successfully")
except ImportError as e:
    print(f"ERROR: {e}")
except Exception as e:
    print(f"ERROR: {e}")
