(() => {
  const toggle = document.querySelector("[data-mobile-nav-toggle]");
  const nav = document.querySelector("[data-mobile-nav]");

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const isOpen = nav.dataset.open === "true";
      nav.dataset.open = String(!isOpen);
      toggle.setAttribute("aria-expanded", String(!isOpen));
    });
  }

  document.querySelectorAll("[data-cta]").forEach((element) => {
    element.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("cutctx:cta", { detail: { action: element.dataset.cta } }));
    });
  });
})();
