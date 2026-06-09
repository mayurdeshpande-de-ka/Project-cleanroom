import os
from app import app

if __name__ == "__main__":
    # Ensure dotenv has been loaded by app.py
    print("DB_HOST from env:", os.environ.get("DB_HOST"))
    
    print("Testing /api/sync-rds endpoint locally...")
    client = app.test_client()
    response = client.post('/api/sync-rds')
    print("Status Code:", response.status_code)
    try:
        print("Response JSON:", response.get_json())
    except Exception as e:
        print("Response Text:", response.data)
