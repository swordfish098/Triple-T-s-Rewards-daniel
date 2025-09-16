async function loadProducts() {
  try {
    const response = await fetch("/truck-rewards/products");
    const products = await response.json();

    const container = document.getElementById("products");
    container.innerHTML = "";

    products.forEach(p => {
      const card = document.createElement("div");
      card.className = "product-card";
      card.innerHTML = `
        <img src="${p.image}" alt="${p.title}">
        <div class="title">${p.title}</div>
        <div class="price">$${p.price.toFixed(2)}</div>
        <div class="points">${p.pointsEquivalent} points</div>
        <button onclick="redeem(${p.id})">Redeem</button>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error("Error loading products:", err);
  }
}

function redeem(productId) {
  alert("Redeem product with ID: " + productId);
  // TODO: Hook up to a Flask /redeem endpoint
}

loadProducts();