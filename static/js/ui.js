/* Togethr · shared UI behaviour: mobile nav, sidebar drawer, dismissible alerts, password visibility */
(function () {
  "use strict";

  /* ---- Public header: hamburger menu ---- */
  var navToggle = document.querySelector("[data-nav-toggle]");
  var siteNav = document.getElementById("site-nav");
  function setNav(open) {
    if (!navToggle || !siteNav) return;
    siteNav.classList.toggle("open", open);
    navToggle.setAttribute("aria-expanded", String(open));
  }
  if (navToggle && siteNav) {
    navToggle.addEventListener("click", function () {
      setNav(navToggle.getAttribute("aria-expanded") !== "true");
    });
    siteNav.addEventListener("click", function (e) {
      if (e.target.closest("a")) setNav(false);
    });
  }

  /* ---- App shell: sidebar drawer on tablet/mobile ---- */
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.querySelector(".sidebar-backdrop");
  var menuBtns = document.querySelectorAll("[data-sidebar-toggle]");
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
    if (backdrop) backdrop.classList.toggle("open", open);
    menuBtns.forEach(function (b) { b.setAttribute("aria-expanded", String(open)); });
    document.body.style.overflow = open ? "hidden" : "";
  }
  menuBtns.forEach(function (b) { b.addEventListener("click", function () { setSidebar(true); }); });
  document.querySelectorAll("[data-sidebar-close]").forEach(function (el) {
    el.addEventListener("click", function () { setSidebar(false); });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { setNav(false); setSidebar(false); }
  });
  window.addEventListener("resize", function () {
    if (window.innerWidth > 1024) setSidebar(false);
    if (window.innerWidth > 860) setNav(false);
  });

  /* ---- Dismissible alerts ---- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-dismiss]");
    if (!btn) return;
    var alert = btn.closest(".alert");
    if (alert) alert.remove();
  });

  /* ---- Show / hide password ---- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-toggle-password]");
    if (!btn) return;
    var input = document.getElementById(btn.getAttribute("data-toggle-password"));
    if (!input) return;
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.setAttribute("aria-pressed", String(show));
    btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
  });
})();
