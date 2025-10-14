/* =========================================================
   Triple T's Rewards – Navbar + Theme Control
   Handles: user menu dropdown, theme persistence, sidebar toggle
   ========================================================= */
   document.addEventListener("DOMContentLoaded", () => {
    // === User menu toggle ===
    const userMenuToggle = document.querySelector(".user-menu-toggle");
    const userMenu = document.querySelector(".user-menu");
  
    if (userMenuToggle && userMenu) {
      userMenuToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        userMenu.classList.toggle("open");
      });
  
      // Close dropdown when clicking outside
      document.addEventListener("click", () => {
        userMenu.classList.remove("open");
      });
    }
  
    // === Sidebar toggle (if present) ===
    const sidebarToggle = document.querySelector(".sidebar-toggle");
    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", () => {
        document.body.classList.toggle("is-sidebar-open");
      });
    }
  
    // === Theme toggle & persistence ===
    const themeBtn = document.getElementById("themeToggle");
    const currentTheme = localStorage.getItem("theme");
  
    if (currentTheme === "dark") {
      document.body.classList.add("dark-theme");
    } else if (currentTheme === "light") {
      document.body.classList.remove("dark-theme");
    }
  
    if (themeBtn) {
      themeBtn.addEventListener("click", (e) => {
        e.preventDefault();
        document.body.classList.toggle("dark-theme");
  
        // Save preference
        localStorage.setItem(
          "theme",
          document.body.classList.contains("dark-theme") ? "dark" : "light"
        );
      });
    }
  });
  