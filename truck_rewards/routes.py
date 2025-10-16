from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
from models import StoreSettings, CartItem, User, Notification, Address, WishlistItem, DriverSponsorAssociation, Purchase, Sponsor
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
@login_required
def store():
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("Please select a sponsor's store from your dashboard.", "info")
        return redirect(url_for('driver_bp.dashboard'))
    return render_template('truck-rewards/index.html')

# --- Products API Endpoint (depends on session) ---
@rewards_bp.route("/products")
@login_required
def products():
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return jsonify({"error": "No sponsor store selected"}), 400

    settings = StoreSettings.query.filter_by(sponsor_id=sponsor_id).first()
    if not settings:
        # Fallback to default if a sponsor hasn't configured their store yet
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
    params = { "limit": 20, "category_ids": category_id }
    if search_query:
        params['q'] = search_query

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
        return jsonify(products)
    except Exception as e:
        print(f"Error fetching products from eBay: {e}")
        return jsonify({"error": "Could not retrieve products from eBay"}), 500

# --- CART FUNCTIONS (now sponsor-aware) ---

@rewards_bp.route("/add_to_cart", methods=['POST'])
@login_required
def add_to_cart():
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return jsonify({"status": "error", "message": "No sponsor selected."}), 400

    item_id = request.form.get('id')
    title = request.form.get('title')
    price = request.form.get('price', type=float)
    points = request.form.get('pointsEquivalent', type=int)
    image_url = request.form.get('image')

    existing_item = CartItem.query.filter_by(user_id=current_user.USER_CODE, item_id=item_id, sponsor_id=sponsor_id).first()

    if existing_item:
        existing_item.quantity += 1
    else:
        new_item = CartItem(
            user_id=current_user.USER_CODE,
            sponsor_id=sponsor_id,
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
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("Please select a sponsor's store to view your cart.", "info")
        return redirect(url_for('driver_bp.dashboard'))
        
    cart_items = CartItem.query.filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).all()
    association = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))
    current_points = association.points if association else 0
    total_points = sum(item.points * item.quantity for item in cart_items)
    addresses = Address.query.filter_by(user_id=current_user.USER_CODE).all()
    
    return render_template('truck-rewards/cart.html', cart_items=cart_items, total_points=total_points, current_points=current_points, addresses=addresses)

@rewards_bp.route("/remove_from_cart/<int:item_id>", methods=['POST'])
@login_required
def remove_from_cart(item_id):
    item_to_remove = CartItem.query.get_or_404(item_id)
    if item_to_remove.user_id != current_user.USER_CODE:
        flash("You are not authorized to modify this item.", "danger")
        return redirect(url_for('rewards_bp.view_cart'))

    db.session.delete(item_to_remove)
    db.session.commit()
    flash("Item removed from your cart.", "info")
    return redirect(url_for('rewards_bp.view_cart'))

@rewards_bp.route("/cart/clear", methods=['POST'])
@login_required
def clear_cart():
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return redirect(url_for('driver_bp.dashboard'))

    CartItem.query.filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).delete()
    db.session.commit()
    flash("Your cart for this sponsor has been cleared.", "info")
    return redirect(url_for('rewards_bp.view_cart'))

@rewards_bp.route("/cart/count")
@login_required
def cart_count():
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return jsonify({'count': 0})
        
    count = db.session.query(db.func.sum(CartItem.quantity)).filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).scalar()
    return jsonify({'count': count or 0})

@rewards_bp.route("/wishlist")
@login_required
def view_wishlist():
    return render_template('truck-rewards/wishlist.html')

@rewards_bp.route("/wishlist/add", methods=['POST'])
@login_required
def add_to_wishlist():
    item_id = request.form.get('id')
    
    existing_item = WishlistItem.query.filter_by(user_id=current_user.USER_CODE, item_id=item_id).first()
    if existing_item:
        return jsonify({"status": "error", "message": "This item is already in your wishlist."})

    new_item = WishlistItem(
        user_id=current_user.USER_CODE,
        item_id=item_id,
        title=request.form.get('title'),
        price=request.form.get('price', type=float),
        points=request.form.get('pointsEquivalent', type=int),
        image_url=request.form.get('image')
    )
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"status": "success", "message": f"'{new_item.title}' has been added to your wishlist."})

@rewards_bp.route("/wishlist/remove/<int:item_id>", methods=['POST'])
@login_required
def remove_from_wishlist(item_id):
    item_to_remove = WishlistItem.query.get_or_404(item_id)
    if item_to_remove.user_id != current_user.USER_CODE:
        flash("You can only remove your own items.", "danger")
        return redirect(url_for('rewards_bp.view_wishlist'))

    db.session.delete(item_to_remove)
    db.session.commit()
    flash("Item removed from your wishlist.", "info")
    return redirect(url_for('rewards_bp.view_wishlist'))

@rewards_bp.route("/checkout", methods=['POST'])
@login_required
def checkout():
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("Your session has expired. Please select a store again.", "danger")
        return redirect(url_for('driver_bp.dashboard'))

    association = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))
    cart_items = CartItem.query.filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).all()
    total_points = sum(item.points * item.quantity for item in cart_items)

    if not association or association.points < total_points:
        flash("You do not have enough points with this sponsor to complete this purchase.", "danger")
        return redirect(url_for('rewards_bp.view_cart'))

    association.points -= total_points

    # Send order confirmation to driver
    if current_user.wants_order_notifications:
        Notification.create_notification(
            recipient_code=current_user.USER_CODE,
            sender_code=sponsor_id,
            message=f"Your order for {total_points} points has been placed successfully!"
        )

    # Notify sponsor of the purchase
    sponsor = Sponsor.query.get(sponsor_id)
    if sponsor:
        for item in cart_items:
            message = f"Driver {current_user.USERNAME} purchased {item.title} for {item.points} points from your catalog."
            Notification.create_notification(
                recipient_code=sponsor.SPONSOR_ID,
                sender_code=current_user.USER_CODE,
                message=message
            )

    # Record purchase and clear cart
    for item in cart_items:
        purchase = Purchase(
            user_id=current_user.USER_CODE,
            sponsor_id=sponsor_id,
            item_id=item.item_id,
            title=item.title,
            points=item.points,
            quantity=item.quantity
        )
        db.session.add(purchase)
        db.session.delete(item)
    
    db.session.commit()

    flash(f"Purchase successful! {total_points} points have been deducted.", "success")
    return redirect(url_for('rewards_bp.store'))