# jchampion136/triple-t-s-rewards-team12/Triple-T-s-Rewards-Team12-51de9b373ff72c36ad6ce76b39ff03679a536ebc/truck_rewards/routes.py

from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import StoreSettings, CartItem, User
from extensions import db
import requests
import os
import base64

# --- Configuration Switch ---
USE_SANDBOX = False 

# Blueprint for the truck rewards store
rewards_bp = Blueprint('rewards_bp', __name__, template_folder="../templates")

# --- Helper function to get eBay Access Token ---
def get_ebay_access_token():
    if USE_SANDBOX:
        app_id = os.getenv('EBAY_APP_ID')
        cert_id = os.getenv('EBAY_CERT_ID')
        url = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
    else:
        app_id = os.getenv('EBAY_PROD_APP_ID')
        cert_id = os.getenv('EBAY_PROD_CERT_ID')
        url = "https://api.ebay.com/identity/v1/oauth2/token"

    if not app_id or not cert_id:
        print("Error: eBay API credentials not found.")
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
    except Exception as e:
        print(f"Error getting eBay access token: {e}")
        return None

# --- Main Store Route ---
@rewards_bp.route('/')
def store():
    return render_template('truck-rewards/index.html')

# --- Products API Endpoint ---
@rewards_bp.route("/products")
def products():
    settings = StoreSettings.query.first()
    if not settings:
        category_id = "2984"
        point_ratio = 10
    else:
        category_id = settings.ebay_category_id
        point_ratio = settings.point_ratio
    search_query = request.args.get('q')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    access_token = get_ebay_access_token()
    if not access_token:
        return jsonify({"error": "Could not authenticate with eBay API"}), 500
    if USE_SANDBOX:
        search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    else:
        search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = { "Authorization": f"Bearer {access_token}" }
    params = { "limit": 20 }
    if search_query:
        params['q'] = search_query
        params['category_ids'] = category_id
    else:
        params['category_ids'] = category_id
    filters = []
    if min_price or max_price:
        price_range = f"price:[{min_price or ''}..{max_price or ''}]"
        filters.append(price_range)
        filters.append("priceCurrency:USD")
    if filters:
        params['filter'] = ",".join(filters)
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
                    "pointsEquivalent": int(price_float * point_ratio)
                })
        print(f"Products found: {len(products)}")
        return jsonify(products)
    except Exception as e:
        print(f"Error fetching products from eBay: {e}")
        return jsonify({"error": "Could not retrieve products from eBay"}), 500

# --- CART FUNCTIONS ---

@rewards_bp.route("/add_to_cart", methods=['POST'])
@login_required
def add_to_cart():
    """Adds an item to the current user's cart."""
    item_id = request.form.get('id')
    title = request.form.get('title')
    price = request.form.get('price', type=float)
    points = request.form.get('pointsEquivalent', type=int)
    image_url = request.form.get('image')

    existing_item = CartItem.query.filter_by(user_id=current_user.USER_CODE, item_id=item_id).first()

    if existing_item:
        existing_item.quantity += 1
    else:
        new_item = CartItem(
            user_id=current_user.USER_CODE,
            item_id=item_id,
            title=title,
            price=price,
            points=points,
            image_url=image_url
        )
        db.session.add(new_item)
    
    db.session.commit()
    return jsonify({"status": "success", "message": f"'{title}' has been added to your cart."})

@rewards_bp.route("/cart")
@login_required
def view_cart():
    """Displays the user's shopping cart."""
    cart_items = CartItem.query.filter_by(user_id=current_user.USER_CODE).all()
    total_points = sum(item.points * item.quantity for item in cart_items)
    return render_template('truck-rewards/cart.html', cart_items=cart_items, total_points=total_points)

@rewards_bp.route("/remove_from_cart/<int:item_id>", methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """Removes an item from the cart."""
    item_to_remove = CartItem.query.get_or_404(item_id)
    if item_to_remove.user_id != current_user.USER_CODE:
        flash("You can only remove your own items.", "danger")
        return redirect(url_for('rewards_bp.view_cart'))

    db.session.delete(item_to_remove)
    db.session.commit()
    flash("Item removed from your cart.", "info")
    return redirect(url_for('rewards_bp.view_cart'))

@rewards_bp.route("/checkout", methods=['POST'])
@login_required
def checkout():
    """Processes the cart purchase."""
    cart_items = CartItem.query.filter_by(user_id=current_user.USER_CODE).all()
    total_points = sum(item.points * item.quantity for item in cart_items)

    if current_user.POINTS < total_points:
        flash("You do not have enough points to complete this purchase.", "danger")
        return redirect(url_for('rewards_bp.view_cart'))

    current_user.POINTS -= total_points
    for item in cart_items:
        db.session.delete(item)
    
    db.session.commit()

    flash(f"Purchase successful! {total_points} points have been deducted.", "success")
    return redirect(url_for('rewards_bp.store'))

# --- END: NEW CART FUNCTIONS ---