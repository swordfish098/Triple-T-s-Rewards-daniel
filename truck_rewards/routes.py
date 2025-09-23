# Triple-T-s-Rewards-Team12/truck_rewards/routes.py

from flask import Blueprint, render_template, jsonify
import requests
import os
import base64
from models import StoreSettings

# --- Configuration Switch ---
# Set to False to use the live Production environment
USE_SANDBOX = False 

# Blueprint for the truck rewards store
rewards_bp = Blueprint('rewards_bp', __name__, template_folder="../templates")

# --- Helper function to get eBay Access Token ---
def get_ebay_access_token():
    """Gets an OAuth 2.0 application access token from eBay."""
    if USE_SANDBOX:
        app_id = os.getenv('EBAY_APP_ID')
        cert_id = os.getenv('EBAY_CERT_ID')
        url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    else:
        # Use Production Keys
        app_id = os.getenv('EBAY_PROD_APP_ID')
        cert_id = os.getenv('EBAY_PROD_CERT_ID')
        url = "https://api.ebay.com/identity/v1/oauth2/token"

    if not app_id or not cert_id:
        print("Error: eBay API credentials not found. Check your .env file.")
        return None

    credentials = f"{app_id}:{cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    body = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }

    try:
        response = requests.post(url, headers=headers, data=body)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error getting eBay access token: {e}")
        return None

# --- Main Store Route ---
@rewards_bp.route('/')
def store():
    """Renders the main store page."""
    return render_template('truck-rewards/index.html')

# --- Updated Products API Endpoint ---
@rewards_bp.route("/products")
def products():
    """Fetches product data from the eBay API and returns it as JSON."""
    # Get the dynamic settings from the database
    settings = StoreSettings.query.first()
    if not settings:
        # Fallback to defaults if settings aren't in the DB yet
        category_id = "2984"
        point_ratio = 10
    else:
        category_id = settings.ebay_category_id
        point_ratio = settings.point_ratio

    access_token = get_ebay_access_token()
    if not access_token:
        return jsonify({"error": "Could not authenticate with eBay API"}), 500

    if USE_SANDBOX:
        search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    else:
        search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    headers = { "Authorization": f"Bearer {access_token}" }
    params = {
        "category_ids": category_id, # Use the category from the database
        "limit": 20
    }

    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        products = []
        for item in data.get("itemSummaries", []):
            if item.get("image"):
                price_str = item.get("price", {}).get("value", "0.0")
                price_float = float(price_str)
                products.append({
                    "id": item.get("itemId", ""),
                    "title": item.get("title", "No Title"),
                    "price": price_float,
                    "image": item.get("image", {}).get("imageUrl", ""),
                    "pointsEquivalent": int(price_float * point_ratio) # Use the ratio from the database
                })
        
        print(f"Products found: {len(products)}")
        return jsonify(products)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching products from eBay: {e}")
        return jsonify({"error": "Could not retrieve products from eBay"}), 500
