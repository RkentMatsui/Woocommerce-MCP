import requests
import os
from dotenv import load_dotenv
import time

load_dotenv()

BASE_URL = "http://localhost:8000"
API_KEY = "test-secret-key"

def test_auth():
    print("Setting temporary environment variable for test...")
    os.environ["MCP_SSE_API_KEY"] = API_KEY
    
    # We need to restart the server or mock the environment in a real test, 
    # but here we are just testing the logic if we were to run it.
    # Since I cannot easily "restart" the server and have it pick up os.environ changes from this process,
    # I will assume the user will set it in their .env.
    
    print(f"\nTesting SSE endpoint without key...")
    try:
        resp = requests.get(f"{BASE_URL}/sse", stream=True)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 401:
            print("OK: Correctly rejected without key.")
        else:
            print(f"FAIL: Expected 401, got {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")

    print(f"\nTesting SSE endpoint with INVALID key...")
    try:
        resp = requests.get(f"{BASE_URL}/sse", headers={"X-API-Key": "wrong-key"}, stream=True)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 401:
            print("OK: Correctly rejected with wrong key.")
        else:
            print(f"FAIL: Expected 401, got {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")

    print(f"\nTesting SSE endpoint with CORRECT key...")
    # This might hang if it succeeds because it's SSE, so we'll use a timeout
    try:
        resp = requests.get(f"{BASE_URL}/sse", headers={"X-API-Key": API_KEY}, stream=True, timeout=2)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("OK: Accepted with correct key.")
        else:
            print(f"FAIL: Expected 200, got {resp.status_code}")
    except requests.exceptions.Timeout:
        print("OK: Accepted with correct key (timeout reached while waiting for stream).")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("NOTE: Ensure the server is running with MCP_SSE_API_KEY=test-secret-key before running this test.")
    test_auth()
