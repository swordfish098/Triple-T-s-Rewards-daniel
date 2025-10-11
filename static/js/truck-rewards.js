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
        <button class="add-to-wishlist-btn" data-product='${productData}'>Add to Wishlist</button>
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
      fetchCartCount(); // Update cart count in navbar
    } else {
      throw new Error('Failed to add item to cart.');
    }
  } catch (err) {
    console.error("Error adding to cart:", err);
    alert("There was an error adding the item to your cart.");
  }
}

// Function to handle adding item to wishlist ---
async function addToWishlist(productData) {
  try {
    const csrfToken = document.querySelector('input[name="csrf_token"]').value;

    const response = await fetch('/truck-rewards/wishlist/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken 
      },
      body: new URLSearchParams(productData)
    });

    const result = await response.json();
    alert(result.message);

  } catch (err) {
    console.error("Error adding to wishlist:", err);
    alert("There was an error adding the item to your wishlist.");
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
    if (event.target && event.target.classList.contains('add-to-wishlist-btn')) {
      const productData = JSON.parse(event.target.dataset.product);
      addToWishlist(productData);
    }
  });
});

document.addEventListener('DOMContentLoaded', function() {
  const submenuToggles = document.querySelectorAll('.submenu-toggle');

  // Function to handle the collapse logic
  function collapseMenu(targetMenu, toggleElement) {
      // Step 1: Set height to current calculated height (e.g., 150px)
      // This is CRITICAL for the animation to work on subsequent closes
      targetMenu.style.height = targetMenu.scrollHeight + 'px';
      
      // Step 2: Use a small delay to ensure the browser registers the height change
      setTimeout(() => {
          targetMenu.classList.add('collapsed');
          targetMenu.style.height = '0'; // Start transition to 0
          toggleElement.classList.remove('expanded');
      }, 10);
  }

  // Function to handle the expansion logic
  function expandMenu(targetMenu, toggleElement) {
      targetMenu.classList.remove('collapsed');
      targetMenu.style.height = targetMenu.scrollHeight + 'px'; // Set transition height
      toggleElement.classList.add('expanded');

      // After the transition ends, set height to 'auto'
      const transitionEndHandler = () => {
          targetMenu.style.height = 'auto'; // CRITICAL: Allows re-opening
          targetMenu.removeEventListener('transitionend', transitionEndHandler);
      };
      targetMenu.addEventListener('transitionend', transitionEndHandler, { once: true });
  }

  // --- INITIAL LOAD (Auto-Expand Active Menu) ---
  const activeToggle = document.querySelector('.submenu-toggle.expanded');
  if (activeToggle) {
      const targetMenu = document.getElementById(activeToggle.getAttribute('data-target'));
      if (targetMenu) {
          targetMenu.classList.remove('collapsed');
          targetMenu.style.height = 'auto'; // Start open
      }
  }
  // --- END INITIAL LOAD ---

  submenuToggles.forEach(toggle => {
      toggle.addEventListener('click', function(e) {
          e.preventDefault(); 
          e.stopPropagation(); // Prevents double-toggling
          
          const targetMenu = document.getElementById(this.getAttribute('data-target'));
          if (!targetMenu) return;

          // Check if it has a height set, or if it has the collapsed class
          // Use scrollHeight > 0 as a proxy for open state when height is 'auto'
          const isOpen = targetMenu.style.height !== '0px' && targetMenu.classList.contains('collapsed') === false;

          if (isOpen) {
              collapseMenu(targetMenu, this);
          } else {
              expandMenu(targetMenu, this);
          }
      });
  });
});