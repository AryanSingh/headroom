(() => {
  const toggle = document.querySelector("[data-mobile-nav-toggle]");
  const nav = document.querySelector("[data-mobile-nav]");

  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const nextOpen = nav.dataset.open !== "true";
      nav.dataset.open = String(nextOpen);
      toggle.setAttribute("aria-expanded", String(nextOpen));
    });
  }

  document.querySelectorAll('[data-mobile-nav]').forEach((navigation) => {
    if (navigation.querySelector('a[href="/licenses"]')) return;
    const link = document.createElement('a');
    link.href = '/licenses';
    link.textContent = 'Licenses';
    navigation.insertBefore(link, navigation.querySelector('.button'));
  });

  document.querySelectorAll('.footer-links').forEach((navigation) => {
    if (navigation.querySelector('a[href="/licenses"]')) return;
    const link = document.createElement('a');
    link.href = '/licenses';
    link.textContent = 'Licenses';
    navigation.append(link);
  });

  document.querySelectorAll("[data-cta]").forEach((element) => {
    element.addEventListener("click", () => {
      window.dispatchEvent(new CustomEvent("cutctx:cta", {
        detail: {
          action: element.dataset.cta,
          placement: element.dataset.ctaPlacement || "unspecified",
        },
      }));
    });
  });
})();
