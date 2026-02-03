from woocommerce import API
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

# Initialize WooCommerce API
wcapi = API(
    url=os.getenv("WC_URL"),
    consumer_key=os.getenv("WC_CONSUMER_KEY"),
    consumer_secret=os.getenv("WC_CONSUMER_SECRET"),
    version="wc/v3"
)

def test_connection():
    print("Testing WooCommerce connection...")
    try:
        # Test fetching a single product as a connectivity check
        response = wcapi.get("products", params={"per_page": 1})
        
        if response.status_code == 200:
            print("✓ Connection successful!")
            products = response.json()
            if products:
                print(f"✓ Found sample product: {products[0].get('name')} (ID: {products[0].get('id')})")
            else:
                print("✓ Connected, but no products found in store.")
        else:
            print(f"✗ Connection failed with status code: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"✗ An error occurred: {str(e)}")

if __name__ == "__main__":
    test_connection()