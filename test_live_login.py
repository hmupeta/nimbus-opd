import urllib.request
import json

BACKEND_URL = "https://nimbus-backend-c400.onrender.com"

def test_login(email, password):
    url = f"{BACKEND_URL}/api/auth/login/"
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, 
        headers={"Content-Type": "application/json"}, 
        method="POST"
    )
    
    print(f"Testing login for {email}...")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            print("✅ SUCCESS! Backend accepted the login.")
            print(f"Token starts with: {data['access'][:20]}...")
    except urllib.error.HTTPError as e:
        print(f"❌ FAILED (HTTP {e.code})")
        print(f"Reason: {e.read().decode()}")
    except Exception as e:
        print(f"❌ CONNECTION ERROR: {e}")

# Test the superadmin
test_login("superadmin@nimbus.local", "demo")