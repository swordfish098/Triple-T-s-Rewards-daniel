# truck_rewards/routes.py

# --- Merged Imports ---
# Kept session from HEAD
from flask import Blueprint, render_template, jsonify, request, flash, redirect, url_for, session
from flask_login import login_required, current_user
# Kept DriverSponsorAssociation, Purchase, Sponsor from HEAD
# Kept AuditLog for checkout logging
from models import StoreSettings, CartItem, User, Notification, Address, WishlistItem, DriverSponsorAssociation, Purchase, Sponsor, AuditLog
# Kept db, requests, os, base64
from extensions import db
import requests
import os
import base64
# Import logging constant
from common.logging import DRIVER_POINTS


# --- Configuration Switch ---
USE_SANDBOX = False # Keep this setting

# --- Blueprint Definition ---
rewards_bp = Blueprint('rewards_bp', __name__, template_folder="../templates")

# --- Helper function to get eBay Access Token ---
# (Keep as is)
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
        print("Error: eBay API credentials not found in environment variables.")
        return None

    credentials = f"{app_id}:{cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    body = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope" # Use production scope
    }
    try:
        response = requests.post(url, headers=headers, data=body)
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e: # Catch specific requests errors
        print(f"Error getting eBay access token: {e}")
        return None
    except Exception as e: # Catch other potential errors (e.g., JSON parsing)
         print(f"Unexpected error getting eBay token: {e}")
         return None

# --- Main Store Route (Using HEAD logic - requires sponsor selection) ---
@rewards_bp.route('/')
@login_required # Keep login required
def store():
    # Check if a sponsor store is selected in the session
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("Please select a sponsor's store from your dashboard first.", "info")
        return redirect(url_for('driver_bp.dashboard')) # Redirect driver to dashboard to select

    # Fetch sponsor name for display
    sponsor = Sponsor.query.get(sponsor_id)
    sponsor_name = sponsor.ORG_NAME if sponsor else "Selected Store"

    return render_template('truck-rewards/index.html', sponsor_name=sponsor_name)

# --- Products API Endpoint (Using HEAD logic - depends on session sponsor) ---
@rewards_bp.route("/products")
@login_required # Keep login required
def products():
    # Get selected sponsor from session
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return jsonify({"error": "No sponsor store selected in session"}), 400

    # Get sponsor-specific settings or use defaults
    settings = StoreSettings.query.filter_by(sponsor_id=sponsor_id).first()
    if not settings:
        category_id = "2984" # Default eBay category
        point_ratio = 10     # Default point ratio
    else:
        category_id = settings.ebay_category_id
        point_ratio = settings.point_ratio

    # Get search/filter parameters
    search_query = request.args.get('q', '') # Default to empty string
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')

    # Get eBay token
    access_token = get_ebay_access_token()
    if not access_token:
        # Log this error server-side as well
        print("Failed to get eBay access token for product search.")
        return jsonify({"error": "Could not authenticate with eBay API"}), 500

    # Set up eBay API call
    if USE_SANDBOX:
        search_url = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"
    else:
        search_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    headers = { "Authorization": f"Bearer {access_token}" }
    params = {
        "limit": 20, # Keep limit reasonable
        "category_ids": category_id
    }
    if search_query:
        params['q'] = search_query

    # Apply filters (Using combined logic)
    filters = []
    if min_price or max_price:
        # Ensure prices are valid numbers if provided
        price_range_parts = []
        try:
            if min_price: price_range_parts.append(f"{float(min_price):.2f}")
            else: price_range_parts.append("")
            if max_price: price_range_parts.append(f"{float(max_price):.2f}")
            else: price_range_parts.append("")
            price_range = f"price:[{price_range_parts[0]}..{price_range_parts[1]}]"
            filters.append(price_range)
            filters.append("priceCurrency:USD") # Assume USD
        except ValueError:
             print(f"Invalid price filter received: min='{min_price}', max='{max_price}'")
             # Optionally return error or just ignore invalid price filters
             pass # Ignoring invalid price filters for now
    if filters:
        params['filter'] = ",".join(filters)

    # Make API call and process results
    try:
        response = requests.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        products = []
        # Check if itemSummaries exists and is a list
        item_summaries = data.get("itemSummaries", [])
        if not isinstance(item_summaries, list):
             print(f"Unexpected format for itemSummaries: {item_summaries}")
             item_summaries = []


        for item in item_summaries:
            # Basic validation of item structure
             image_data = item.get("image")
             price_data = item.get("price")
             if image_data and price_data:
                try:
                    price_str = price_data.get("value", "0.0")
                    price_float = float(price_str)
                    # Ensure points are calculated correctly
                    points_equivalent = int(price_float * point_ratio) if point_ratio > 0 else 0

                    products.append({
                        "id": item.get("itemId", ""), # itemId is crucial
                        "title": item.get("title", "No Title Available"),
                        "price": price_float,
                        "image": image_data.get("imageUrl", ""),
                        "pointsEquivalent": points_equivalent
                    })
                except (ValueError, TypeError) as e:
                     print(f"Error processing item {item.get('itemId')}: {e}. Price data: {price_data}")
                     continue # Skip items with invalid price data

        return jsonify(products)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching products from eBay: {e}. URL: {search_url}, Params: {params}")
        return jsonify({"error": f"Could not retrieve products from eBay: {e}"}), 500
    except Exception as e: # Catch other errors like JSON decoding
        print(f"Unexpected error processing eBay response: {e}")
        return jsonify({"error": "An unexpected error occurred while fetching products."}), 500


# --- CART FUNCTIONS (Using HEAD logic - sponsor-aware) ---

@rewards_bp.route("/add_to_cart", methods=['POST'])
@login_required
def add_to_cart():
    # Get sponsor_id from session
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return jsonify({"status": "error", "message": "No sponsor selected. Please go to your dashboard and select a store."}), 400

    # Get item details from form
    item_id = request.form.get('id')
    title = request.form.get('title')
    price = request.form.get('price', type=float)
    points = request.form.get('pointsEquivalent', type=int)
    image_url = request.form.get('image')

    # Basic validation
    if not all([item_id, title, price is not None, points is not None]):
         return jsonify({"status": "error", "message": "Missing item data."}), 400


    # Check if item already exists in cart for this user and sponsor
    existing_item = CartItem.query.filter_by(
        user_id=current_user.USER_CODE,
        item_id=item_id,
        sponsor_id=sponsor_id # Filter by sponsor
    ).first()

    if existing_item:
        existing_item.quantity += 1
    else:
        new_item = CartItem(
            user_id=current_user.USER_CODE,
            sponsor_id=sponsor_id, # Store sponsor_id
            item_id=item_id,
            title=title,
            price=price,
            points=points,
            image_url=image_url,
            quantity=1 # Start with quantity 1
        )
        db.session.add(new_item)

    try:
        db.session.commit()
        return jsonify({"status": "success", "message": f"'{title}' added to your cart."})
    except Exception as e:
        db.session.rollback()
        print(f"Error adding to cart: {e}")
        return jsonify({"status": "error", "message": "Database error adding item to cart."}), 500


@rewards_bp.route("/cart")
@login_required
def view_cart():
    # Get sponsor_id from session (HEAD logic)
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("Please select a sponsor's store from your dashboard to view the cart.", "info")
        return redirect(url_for('driver_bp.dashboard'))

    # Fetch cart items for the current user AND sponsor
    cart_items = CartItem.query.filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).all()

    # Get sponsor-specific points balance (HEAD logic)
    association = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))
    current_points = association.points if association else 0

    # Calculate total points for items in the current sponsor's cart
    total_points = sum(item.points * item.quantity for item in cart_items)

    # Get user addresses
    addresses = Address.query.filter_by(user_id=current_user.USER_CODE).order_by(Address.is_default.desc()).all()

    # Get sponsor name for display
    sponsor = Sponsor.query.get(sponsor_id)
    sponsor_name = sponsor.ORG_NAME if sponsor else "Selected Store"


    return render_template('truck-rewards/cart.html',
                           cart_items=cart_items,
                           total_points=total_points,
                           current_points=current_points, # Pass sponsor-specific balance
                           addresses=addresses,
                           sponsor_name=sponsor_name)


@rewards_bp.route("/remove_from_cart/<int:cart_item_id>", methods=['POST']) # Use cart item's own ID
@login_required
def remove_from_cart(cart_item_id):
    # Fetch by CartItem's primary key
    item_to_remove = CartItem.query.get_or_404(cart_item_id)

    # Authorization check (HEAD logic)
    if item_to_remove.user_id != current_user.USER_CODE:
        flash("You are not authorized to modify this cart item.", "danger")
        return redirect(url_for('rewards_bp.view_cart'))

    try:
        db.session.delete(item_to_remove)
        db.session.commit()
        flash(f"'{item_to_remove.title}' removed from your cart.", "info")
    except Exception as e:
         db.session.rollback()
         print(f"Error removing item from cart: {e}")
         flash("Error removing item from cart.", "danger")

    return redirect(url_for('rewards_bp.view_cart'))


@rewards_bp.route("/cart/clear", methods=['POST'])
@login_required
def clear_cart():
    # Get sponsor_id from session (HEAD logic)
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("No sponsor store selected.", "warning")
        return redirect(url_for('driver_bp.dashboard'))

    # Delete only items for the current user AND sponsor (HEAD logic)
    deleted_count = CartItem.query.filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).delete()
    try:
        db.session.commit()
        if deleted_count > 0:
            flash("Your cart for this sponsor has been cleared.", "info")
        else:
            flash("Your cart for this sponsor was already empty.", "info")
    except Exception as e:
         db.session.rollback()
         print(f"Error clearing cart: {e}")
         flash("Error clearing cart.", "danger")

    return redirect(url_for('rewards_bp.view_cart'))


@rewards_bp.route("/cart/count")
@login_required
def cart_count():
    # Get sponsor_id from session (HEAD logic)
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        return jsonify({'count': 0}) # No sponsor selected, count is 0 for that "store"

    # Count items for the current user AND sponsor (HEAD logic)
    count = db.session.query(db.func.sum(CartItem.quantity)).filter_by(
        user_id=current_user.USER_CODE,
        sponsor_id=sponsor_id
    ).scalar()

    return jsonify({'count': count or 0}) # Return 0 if count is None


# --- WISHLIST FUNCTIONS (Mostly consistent, keep HEAD structure) ---

@rewards_bp.route("/wishlist")
@login_required
def view_wishlist():
    # Fetch wishlist items for the current user
    wishlist_items = WishlistItem.query.filter_by(user_id=current_user.USER_CODE).all()
    return render_template('truck-rewards/wishlist.html', wishlist_items=wishlist_items)


@rewards_bp.route("/wishlist/add", methods=['POST'])
@login_required
def add_to_wishlist():
    item_id = request.form.get('id')
    title = request.form.get('title')
    price = request.form.get('price', type=float)
    points = request.form.get('pointsEquivalent', type=int)
    image_url = request.form.get('image')

    # Basic validation
    if not all([item_id, title, price is not None, points is not None]):
         return jsonify({"status": "error", "message": "Missing item data."}), 400

    # Prevent duplicates (Consistent logic)
    existing_item = WishlistItem.query.filter_by(user_id=current_user.USER_CODE, item_id=item_id).first()
    if existing_item:
        return jsonify({"status": "error", "message": "This item is already in your wishlist."}), 409 # Conflict status


    new_item = WishlistItem(
        user_id=current_user.USER_CODE,
        item_id=item_id,
        title=title,
        price=price,
        points=points,
        image_url=image_url
    )
    try:
        db.session.add(new_item)
        db.session.commit()
        return jsonify({"status": "success", "message": f"'{new_item.title}' added to your wishlist."})
    except Exception as e:
         db.session.rollback()
         print(f"Error adding to wishlist: {e}")
         return jsonify({"status": "error", "message": "Database error adding item to wishlist."}), 500


@rewards_bp.route("/wishlist/remove/<int:wishlist_item_id>", methods=['POST']) # Use wishlist item's own ID
@login_required
def remove_from_wishlist(wishlist_item_id):
    # Fetch by WishlistItem's primary key
    item_to_remove = WishlistItem.query.get_or_404(wishlist_item_id)

    # Authorization check (Consistent logic)
    if item_to_remove.user_id != current_user.USER_CODE:
        flash("You can only remove your own wishlist items.", "danger")
        return redirect(url_for('rewards_bp.view_wishlist'))

    try:
        db.session.delete(item_to_remove)
        db.session.commit()
        flash(f"'{item_to_remove.title}' removed from your wishlist.", "info")
    except Exception as e:
         db.session.rollback()
         print(f"Error removing from wishlist: {e}")
         flash("Error removing item from wishlist.", "danger")

    return redirect(url_for('rewards_bp.view_wishlist'))


# --- CHECKOUT FUNCTION (Using HEAD logic - sponsor-aware) ---

@rewards_bp.route("/checkout", methods=['POST'])
@login_required
def checkout():
    # Get sponsor_id from session (HEAD logic)
    sponsor_id = session.get('current_sponsor_id')
    if not sponsor_id:
        flash("Your session may have expired or no sponsor store is selected. Please select a store from your dashboard.", "danger")
        return redirect(url_for('driver_bp.dashboard'))

    # Get sponsor-specific association and cart items (HEAD logic)
    association = DriverSponsorAssociation.query.get((current_user.USER_CODE, sponsor_id))
    cart_items = CartItem.query.filter_by(user_id=current_user.USER_CODE, sponsor_id=sponsor_id).all()

    if not cart_items:
         flash("Your cart for this sponsor is empty.", "warning")
         return redirect(url_for('rewards_bp.view_cart'))


    total_points = sum(item.points * item.quantity for item in cart_items)

    # Check points balance with this specific sponsor (HEAD logic)
    if not association or association.points < total_points:
        flash(f"You do not have enough points ({association.points if association else 0}) with this sponsor to complete this purchase ({total_points} needed).", "danger")
        return redirect(url_for('rewards_bp.view_cart'))

    # --- Process Purchase ---
    try:
        # 1. Deduct points from association
        association.points -= total_points

        # 2. Log the point deduction event (HEAD logic)
        log_entry = AuditLog(
            EVENT_TYPE=DRIVER_POINTS,
            DETAILS=f"Points deducted for purchase by driver {current_user.USERNAME} (ID: {current_user.USER_CODE}). Amount: -{total_points} from Sponsor ID: {sponsor_id}."
        )
        db.session.add(log_entry)

        # 3. Create Purchase records (HEAD logic)
        purchases_to_add = []
        for item in cart_items:
            purchase = Purchase(
                user_id=current_user.USER_CODE,
                sponsor_id=sponsor_id,
                item_id=item.item_id,
                title=item.title,
                points=item.points,
                quantity=item.quantity,
                purchase_date=db.func.now() # Use database function for timestamp
            )
            purchases_to_add.append(purchase)
            db.session.delete(item) # Delete item from cart

        db.session.add_all(purchases_to_add)

        # 4. Commit transaction
        db.session.commit()

        # --- Notifications (After successful commit) ---
        # Send order confirmation to driver (HEAD logic)
        if current_user.wants_order_notifications:
            try:
                Notification.create_notification(
                    recipient_code=current_user.USER_CODE,
                    sender_code=sponsor_id, # Sponsor is sender contextually
                    message=f"✅ Your order for {total_points} points from sponsor {Sponsor.query.get(sponsor_id).ORG_NAME if Sponsor.query.get(sponsor_id) else sponsor_id} has been placed successfully!"
                )
            except Exception as e:
                 print(f"Error sending order confirmation notification: {e}")


        # Notify sponsor of the purchase (HEAD logic)
        sponsor = Sponsor.query.get(sponsor_id)
        if sponsor:
            # Maybe send one summary notification instead of one per item?
            items_summary = ", ".join([f"{item.quantity}x {item.title}" for item in cart_items])
            message = f"📢 New Order: Driver {current_user.USERNAME} placed an order for {total_points} points. Items: {items_summary}."
            try:
                Notification.create_notification(
                    recipient_code=sponsor.SPONSOR_ID,
                    sender_code=current_user.USER_CODE, # Driver initiated
                    message=message
                )
            except Exception as e:
                 print(f"Error sending sponsor purchase notification: {e}")

        flash(f"Purchase successful! {total_points} points have been deducted.", "success")
        return redirect(url_for('rewards_bp.store')) # Redirect back to store page

    except Exception as e:
        db.session.rollback() # Rollback all changes on error
        print(f"Checkout error: {e}")
        flash(f"An error occurred during checkout: {e}. Please try again.", "danger")
        return redirect(url_for('rewards_bp.view_cart')) # Redirect back to cart on failure