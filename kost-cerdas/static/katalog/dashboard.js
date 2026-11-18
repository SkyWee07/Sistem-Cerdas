(() => {
  const form = document.getElementById("gemini-explain-form");
  if (!form) return;

  const button = document.getElementById("gemini-explain-button");
  const label = button?.querySelector(".button-label");
  const status = document.getElementById("gemini-loading-status");

  form.addEventListener("submit", () => {
    form.setAttribute("aria-busy", "true");
    if (button) button.disabled = true;
    if (label) label.textContent = "Sedang menjelaskan…";
    if (status) status.hidden = false;
  });
})();
