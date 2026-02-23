// app.js
document.addEventListener("DOMContentLoaded", () => {
  const navLinks = document.querySelectorAll(".nav a[data-page]");
  const pages = document.querySelectorAll("section.page");
  if (!navLinks.length || !pages.length) return;

  function showPage(pageId){
    const target = document.getElementById(pageId);
    if (!target) return;

    pages.forEach(p => {
      if (p === target) return;
      p.classList.remove("active");
      p.style.opacity = "0";
    });

    target.classList.add("active");
    requestAnimationFrame(() => (target.style.opacity = "1"));

    navLinks.forEach(a => a.classList.toggle("active", a.dataset.page === pageId));
  }

  pages.forEach(p => (p.style.opacity = "0"));

  const initial = document.querySelector(".nav a.active[data-page]")?.dataset.page
    || navLinks[0].dataset.page;

  showPage(initial);

  navLinks.forEach(a => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      showPage(a.dataset.page);
    });
  });
});
