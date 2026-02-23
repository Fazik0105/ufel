document.addEventListener("DOMContentLoaded", () => {
  const pages = document.querySelectorAll(".page");

  const topNavLinks = document.querySelectorAll(".navbar a[data-page]");
  const mobileNavLinks = document.querySelectorAll(".mobile-menu a[data-page]");
  const homeButtons = document.querySelectorAll(".home-btn[data-page]");

  function showPage(pageId) {
    // pages
    pages.forEach(p => p.classList.remove("active"));
    const target = document.getElementById(pageId);
    if (target) target.classList.add("active");

    // top navbar active
    topNavLinks.forEach(a => a.classList.toggle("active", a.dataset.page === pageId));

    // mobile navbar active (xohlasang)
    mobileNavLinks.forEach(a => a.classList.toggle("active", a.dataset.page === pageId));
  }

  function bindLinks(links) {
    links.forEach(a => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const pageId = a.dataset.page;
        if (!pageId) return;

        showPage(pageId);

        // mobile menu yopish (agar ochiq bo‘lsa)
        const mobileMenu = document.getElementById("mobileMenu");
        if (mobileMenu) mobileMenu.classList.remove("active");
      });
    });
  }

  bindLinks(topNavLinks);
  bindLinks(mobileNavLinks);
  bindLinks(homeButtons);

  // start holat: HTML’da qaysi page active bo‘lsa, shuni olamiz
  const initial = document.querySelector(".page.active")?.id || "home";
  showPage(initial);
});
