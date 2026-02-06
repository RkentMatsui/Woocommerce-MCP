from woocommerce import API
from dotenv import load_dotenv
import os
import json
import requests
import base64

# Load environment variables
load_dotenv()

# Initialize WooCommerce API
wcapi = API(
    url=os.getenv("WC_URL"),
    consumer_key=os.getenv("WC_CONSUMER_KEY"),
    consumer_secret=os.getenv("WC_CONSUMER_SECRET"),
    version="wc/v3"
)

def test_woocommerce():
    print("Testing WooCommerce connection...")
    try:
        response = wcapi.get("products", params={"per_page": 1})
        if response.status_code == 200:
            print("OK: WooCommerce: Connection successful!")
            products = response.json()
            if products:
                print(f"OK: WooCommerce: Found sample product: {products[0].get('name')} (ID: {products[0].get('id')})")
        else:
            print(f"FAIL: WooCommerce: Failed (Status: {response.status_code})")
    except Exception as e:
        print(f"ERROR: WooCommerce: Error: {str(e)}")

def test_nova_api_discovery():
    base_url = f"{os.getenv('WC_URL').rstrip('/')}/wp-json/nova/v1"
    print("\nDiscovering Nova B2B endpoints...")
    try:
        resp = requests.get(base_url)
        if resp.status_code == 200:
            routes = sorted(list(resp.json().get("routes", {}).keys()))
            print(f"OK: Nova: Found {len(routes)} routes in namespace.")
            print("Detected Routes:")
            for r in routes:
                print(f"  - {r}")
                
            has_ticket = any("ticket-details" in r for r in routes)
            if has_ticket:
                print("OK: Nova: Endpoint /ticket-details found.")
            else:
                # Try a simpler check
                has_ticket = any("ticket-details" in r for r in routes)
                if has_ticket:
                    print("OK: Nova: Endpoint /ticket-details found (approximate match).")
                else:
                    print("FAIL: Nova: Endpoint /ticket-details NOT found in discovery!")
        else:
            print(f"FAIL: Nova: Namespace discovery failed (Status: {resp.status_code})")
    except Exception as e:
        print(f"ERROR: Nova: Discovery error: {str(e)}")

def test_nova_api():
    base_url = f"{os.getenv('WC_URL').rstrip('/')}/wp-json/nova/v1"
    api_key = os.getenv("NOVA_API_KEY")
    username = os.getenv("WP_USERNAME")
    password = os.getenv("WP_APP_PASSWORD")

    print("\nTesting Nova B2B custom endpoints...")
    
    # Test Public Endpoint
    try:
        resp = requests.get(f"{base_url}/orders")
        if resp.status_code == 200:
            print("OK: Nova: Public endpoint (/orders) accessible.")
        else:
            print(f"FAIL: Nova: Public endpoint failed (Status: {resp.status_code})")
    except Exception as e:
        print(f"ERROR: Nova: Public endpoint error: {str(e)}")

    # Test API Key Endpoint
    if api_key:
        try:
            resp = requests.get(f"{base_url}/nova_orders", headers={"X-API-Key": api_key})
            if resp.status_code == 200:
                print("OK: Nova: API Key authentication successful (/nova_orders).")
            else:
                print(f"FAIL: Nova: API Key authentication failed (Status: {resp.status_code})")
        except Exception as e:
            print(f"ERROR: Nova: API Key error: {str(e)}")
    else:
        print("! Nova: Skipping API Key test (NOVA_API_KEY not set).")

    # Test Basic Auth Endpoint
    if username and password:
        try:
            # According to theme_guide.md, ticket-details might need an email parameter
            params = {"email": username} if "@" in username else None
            
            resp = requests.get(
                f"{base_url}/ticket-details/1", 
                auth=(username, password),
                params=params
            )
            
            # We expect 404 or success, but NOT 401/403
            if resp.status_code in [200, 404]:
                print(f"OK: Nova: Basic Auth accepted (Status: {resp.status_code}).")
            elif resp.status_code == 401:
                print(f"FAIL: Nova: Basic Auth failed (Status: 401 Unauthorized).")
                print("  Tip: Ensure the Application Password is correct and Application Passwords are enabled in WordPress.")
                print(f"  Auth tried: {username} : [HIDDEN]")
            else:
                print(f"FAIL: Nova: Basic Auth failed (Status: {resp.status_code})")
                print(f"  Response: {resp.text[:200]}")
        except Exception as e:
            print(f"ERROR: Nova: Basic Auth error: {str(e)}")
    else:
        print("! Nova: Skipping Basic Auth test (WP_USERNAME/WP_APP_PASSWORD not set).")

if __name__ == "__main__":
    test_woocommerce()
    test_nova_api_discovery()
    test_nova_api()