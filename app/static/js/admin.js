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
