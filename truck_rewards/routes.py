from flask import Blueprint, render_template, jsonify
import requests

# Blueprint for the truck rewards store
rewards_bp = Blueprint('rewards_bp', __name__, template_folder="../templates")

@rewards_bp.route('/')
def store():
    """Renders the main store page."""
    return render_template('truck-rewards/index.html')

@rewards_bp.route("/products")
def products():
    """Fetches product data from the Fake Store API and returns it as JSON."""
    try:
        response = requests.get("https://fakestoreapi.com/products")
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        # Convert price to a "points equivalent" (e.g., 1 USD = 10 points)
        products = [
            {
                "id": item["id"],
                "title": item["title"],
                "price": item["price"],
                "image": item["image"],
                "pointsEquivalent": int(item["price"] * 10)
            }
            for item in data
        ]
        return jsonify(products)
    except requests.exceptions.RequestException as e:
        # Log the error and return a user-friendly message
        print(f"Error fetching products: {e}")
        return jsonify({"error": "Could not retrieve products"}), 500