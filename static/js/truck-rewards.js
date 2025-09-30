async function loadProducts(query = '', minPrice = '', maxPrice = '') {
  try {
    let url = `/truck-rewards/products?q=${encodeURIComponent(query)}`;
    if (minPrice) url += `&min_price=${encodeURIComponent(minPrice)}`;
    if (maxPrice) url += `&max_price=${encodeURIComponent(maxPrice)}`;

    const response = await fetch(url);
    const products = await response.json();

    const container = document.getElementById("products");
    container.innerHTML = "";

    if (products.length === 0) {
      container.innerHTML = "<p>No products found matching your criteria.</p>";
      return;
    }

    products.forEach(p => {
      const card = document.createElement("div");
      card.className = "product-card";
      const imageUrl = p.image || 'https://i.ebayimg.com/images/g/placeholder/s-l225.jpg';
      
      // Store product data as a JSON string in a data attribute
      const productData = JSON.stringify(p);

      card.innerHTML = `
        <img src="${imageUrl}" alt="${p.title}">
        <div class="title">${p.title}</div>
        <div class="price">$${p.price.toFixed(2)}</div>
        <div class="points">${p.pointsEquivalent} points</div>
        <button class="add-to-cart-btn" data-product='${productData}'>Add to Cart</button>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading products:", err);
    container.innerHTML = "<p>Error loading products.</p>";
  }
}

// Function to handle adding item to cart ---
async function addToCart(productData) {
  try {
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;

    const response = await fetch('/truck-rewards/add_to_cart', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken 
      },
      body: new URLSearchParams(productData)
    });

    if (response.ok) {
      alert(`'${productData.title}' was added to your cart!`);
    } else {
      throw new Error('Failed to add item to cart.');
    }
  } catch (err) {
    console.error("Error adding to cart:", err);
    alert("There was an error adding the item to your cart.");
  }
}

// Event listener for the page
document.addEventListener('DOMContentLoaded', () => {
  loadProducts(); 

  const searchForm = document.getElementById('search-form');
  if (searchForm) {
    searchForm.addEventListener('submit', (event) => {
      event.preventDefault(); 
      const searchInput = document.getElementById('search-input');
      const minPriceInput = document.getElementById('min-price');
      const maxPriceInput = document.getElementById('max-price');
      loadProducts(searchInput.value, minPriceInput.value, maxPriceInput.value);
    });
  }

  // Use event delegation to handle clicks on buttons that are added dynamically
  document.getElementById('products').addEventListener('click', (event) => {
    if (event.target && event.target.classList.contains('add-to-cart-btn')) {
      const productData = JSON.parse(event.target.dataset.product);
      addToCart(productData);
    }
  });
});