// Minimal progressive-enhancement helpers for the FileService admin UI.
document.addEventListener("click", (event) => {
  const el = event.target.closest("[data-copy]");
  if (!el) return;
  const value = el.getAttribute("data-copy");
  navigator.clipboard?.writeText(value).then(() => {
    const prev = el.textContent;
    el.textContent = "Copied!";
    setTimeout(() => {
      el.textContent = prev;
    }, 1200);
  });
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form.matches("[data-confirm]")) {
    if (!window.confirm(form.getAttribute("data-confirm"))) {
      event.preventDefault();
    }
  }
});

// Click-triggered modals: [data-modal-open="id"] opens, [data-modal-close]
// (or a click on the dim overlay) closes. Forms live inside, so they only
// render when invoked — never permanently on the page.
function closeModal(overlay) {
  if (overlay) overlay.hidden = true;
}

document.addEventListener("click", (event) => {
  const opener = event.target.closest("[data-modal-open]");
  if (opener) {
    const overlay = document.getElementById(opener.getAttribute("data-modal-open"));
    if (overlay) {
      overlay.hidden = false;
      const field = overlay.querySelector("input, select, textarea");
      if (field) field.focus();
    }
    return;
  }
  if (event.target.closest("[data-modal-close]")) {
    closeModal(event.target.closest(".modal-overlay"));
    return;
  }
  // Click on the dim backdrop (outside the .modal box) closes it.
  if (event.target.classList.contains("modal-overlay")) {
    closeModal(event.target);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document
      .querySelectorAll(".modal-overlay:not([hidden])")
      .forEach(closeModal);
  }
});
