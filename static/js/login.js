(function () {
  "use strict";
  /* Owner's choice (2026-11-17): when ticked, this computer's browser keeps the user name and password
     and fills them in next time. Log in is still pressed each time. Unticking clears them. */
  const KEY = "di_login";
  const form = document.querySelector(".login-form");
  const box = document.getElementById("remember");
  const user = document.getElementById("id_username");
  const pass = document.getElementById("id_password");
  if (!form || !box || !user || !pass) return;
  user.autocomplete = "username";
  pass.autocomplete = "current-password";
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "null");
    if (saved && saved.u) {
      if (!user.value) user.value = saved.u;
      if (!pass.value) pass.value = saved.p || "";
      box.checked = true;
    }
  } catch (e) { /* Nothing saved, or storage is blocked. */ }
  form.addEventListener("submit", () => {
    try {
      if (box.checked) localStorage.setItem(KEY, JSON.stringify({ u: user.value, p: pass.value }));
      else localStorage.removeItem(KEY);
    } catch (e) { /* Storage is blocked: logging in still works. */ }
  });
})();
