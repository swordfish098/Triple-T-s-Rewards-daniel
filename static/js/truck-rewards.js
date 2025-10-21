// static/js/truck-rewards.js

async function loadProducts(query = '', minPrice = '', maxPrice = '') {
  const container = document.getElementById("products"); // Define container early for error handling
  try {
    let url = `/truck-rewards/products?q=${encodeURIComponent(query)}`;
    if (minPrice) url += `&min_price=${encodeURIComponent(minPrice)}`;
    if (maxPrice) url += `&max_price=${encodeURIComponent(maxPrice)}`;

    const response = await fetch(url);
    if (!response.ok) { // Check if response was successful
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const products = await response.json();

    container.innerHTML = ""; // Clear previous products

    if (products.error) { // Check for API errors returned in JSON
        container.innerHTML = `<p>Error: ${products.error}</p>`;
        return;
    }

    if (!Array.isArray(products) || products.length === 0) { // Ensure products is an array
      container.innerHTML = "<p>No products found matching your criteria.</p>";
      return;
    }

    products.forEach(p => {
      const card = document.createElement("div");
      card.className = "product-card";
      // Use a default placeholder if image URL is missing
      const imageUrl = p.image || 'https://ir.ebaystatic.com/cr/v/c1/s_1x2.gif'; // Standard eBay placeholder

      // Escape product data correctly for HTML attribute
      const productDataString = JSON.stringify(p).replace(/'/g, "&apos;");

      card.innerHTML = `
        <img src="${imageUrl}" alt="${p.title || 'Product Image'}">
        <div class="title">${p.title || 'No Title'}</div>
        <div class="price">$${p.price ? p.price.toFixed(2) : 'N/A'}</div>
        <div class="points">${p.pointsEquivalent || 0} points</div>
        <button class="add-to-cart-btn" data-product='${productDataString}'>Add to Cart</button>
        <button class="add-to-wishlist-btn" data-product='${productDataString}'>Add to Wishlist</button>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading products:", err);
    // Display a user-friendly error message
    if (container) { // Ensure container exists before trying to set innerHTML
        container.innerHTML = "<p>Sorry, there was an error loading products. Please try again later.</p>";
    }
  }
}

// Keep the version that disables the button
async function addToCart(productData, button) {
  // Disable the button immediately
  button.disabled = true;
  button.textContent = 'Adding...';

  try {
    // Attempt to get CSRF token, handle if not found
    const csrfInput = document.querySelector('input[name="csrf_token"]');
    if (!csrfInput) {
        throw new Error('CSRF token not found.');
    }
    const csrfToken = csrfInput.value;

    const response = await fetch('/truck-rewards/add_to_cart', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken // Ensure header name matches backend expectation
      },
      // Ensure productData is correctly formatted
      body: new URLSearchParams(productData).toString()
    });

    if (response.ok) {
      const result = await response.json(); // Assuming backend sends JSON confirmation
      alert(result.message || `'${productData.title}' was added to your cart!`); // Use message from backend if available
      fetchCartCount(); // Update cart count display
    } else {
       // Try to get error message from response body
       let errorMsg = 'Failed to add item to cart.';
       try {
           const errorResult = await response.json();
           if (errorResult && errorResult.message) {
               errorMsg = errorResult.message;
           }
       } catch (parseError) {
            console.error("Could not parse error response:", parseError);
       }
       throw new Error(errorMsg);
    }
  } catch (err) {
    console.error("Error adding to cart:", err);
    alert(`Error: ${err.message || "Could not add item to cart."}`);
  } finally {
    // Re-enable the button after the request is complete, regardless of success/failure
    button.disabled = false;
    button.textContent = 'Add to Cart';
  }
}

async function addToWishlist(productData, button) {
    // Disable button temporarily
    button.disabled = true;
    button.textContent = 'Adding...';

    try {
        const csrfInput = document.querySelector('input[name="csrf_token"]');
        if (!csrfInput) {
            throw new Error('CSRF token not found.');
        }
        const csrfToken = csrfInput.value;

        const response = await fetch('/truck-rewards/wishlist/add', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken
        },
        body: new URLSearchParams(productData).toString()
        });

        const result = await response.json(); // Always expect JSON back
        alert(result.message); // Display message from backend (success or error)

        if (!response.ok) {
             console.error("Server error adding to wishlist:", result.message);
        }

    } catch (err) {
        console.error("Error adding to wishlist:", err);
        alert(`Error: ${err.message || "Could not add item to wishlist."}`);
    } finally {
         // Re-enable button
         button.disabled = false;
         button.textContent = 'Add to Wishlist';
    }
}

// Function to update cart count in the navbar (assuming you have an element with id="cart-count")
async function fetchCartCount() {
    try {
        const response = await fetch('/truck-rewards/cart/count');
        if (!response.ok) {
            throw new Error('Failed to fetch cart count');
        }
        const data = await response.json();
        const cartCountElement = document.getElementById('cart-count');
        if (cartCountElement) {
            cartCountElement.textContent = data.count || 0;
        }
    } catch (error) {
        console.error('Error fetching cart count:', error);
        // Optionally display a small error indicator instead of count
        const cartCountElement = document.getElementById('cart-count');
        if (cartCountElement) {
             cartCountElement.textContent = '?'; // Indicate error fetching count
        }
    }
}


document.addEventListener('DOMContentLoaded', () => {
  // Initial load
  loadProducts();
  fetchCartCount(); // Fetch count on page load

  const searchForm = document.getElementById('search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (event) => {
      event.preventDefault(); // Prevent default form submission
      const searchInput = document.getElementById('search-input');
      const minPriceInput = document.getElementById('min-price');
      const maxPriceInput = document.getElementById('max-price');
      // Perform search
      loadProducts(searchInput.value, minPriceInput.value, maxPriceInput.value);
    });
  }

  // Use event delegation on the products container
  const productsContainer = document.getElementById('products');
  if (productsContainer) {
      productsContainer.addEventListener('click', (event) => {
        // Check if the clicked element is an 'Add to Cart' button
        if (event.target && event.target.classList.contains('add-to-cart-btn')) {
          try {
              const productData = JSON.parse(event.target.dataset.product);
              // Pass the clicked button to the function
              addToCart(productData, event.target);
          } catch(e) {
              console.error("Failed to parse product data for cart:", e);
              alert("Error processing product data.");
          }
        }
        // Check if the clicked element is an 'Add to Wishlist' button
        if (event.target && event.target.classList.contains('add-to-wishlist-btn')) {
           try {
              const productData = JSON.parse(event.target.dataset.product);
              // Pass the button to the function
              addToWishlist(productData, event.target);
           } catch(e) {
               console.error("Failed to parse product data for wishlist:", e);
               alert("Error processing product data.");
           }
        }
      });
  } else {
      console.error("Products container not found");
  }

}); // End DOMContentLoaded