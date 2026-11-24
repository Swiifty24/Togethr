/* Togethr · live password checklist.
   The rules below mirror accounts/validators.py and Django's validators; the
   server remains the authority. Weak fragments come from the page (json_script). */
(function () {
  "use strict";

  var fragmentsEl = document.getElementById("weak-fragments");
  var weakFragments = [];
  try { weakFragments = JSON.parse(fragmentsEl.textContent); } catch (e) { /* no list on this page */ }

  var rules = {
    length: function (p) { return p.length >= 8; },
    upper:  function (p) { return /[A-Z]/.test(p); },
    lower:  function (p) { return /[a-z]/.test(p); },
    digit:  function (p) { return /[0-9]/.test(p); },
    special: function (p) { return /[!-\/:-@\[-`{-~]/.test(p); },   // ASCII punctuation
    common: function (p) {
      var lowered = p.toLowerCase();
      return !weakFragments.some(function (f) { return lowered.indexOf(f) !== -1; });
    }
  };

  document.querySelectorAll("form[data-password-form]").forEach(function (form) {
    var input = form.querySelector("[data-password-input]");
    var confirm = form.querySelector("[data-password-confirm]");
    var panel = form.querySelector("[data-password-rules]");
    var matchEl = form.querySelector("[data-match-status]");
    var submit = form.querySelector("[data-password-submit]");
    if (!input) return;
    var optional = panel && panel.hasAttribute("data-optional");

    function evaluate(showUnmet) {
      var value = input.value;
      var allMet = true;
      if (panel) {
        panel.querySelectorAll("[data-rule]").forEach(function (li) {
          var met = rules[li.getAttribute("data-rule")](value);
          li.classList.toggle("met", met);
          li.classList.toggle("unmet", !met && showUnmet && value.length > 0);
          var sr = li.querySelector("[data-sr]");
          if (sr) sr.textContent = met ? " (met)" : " (not met yet)";
          if (!met) allMet = false;
        });
      }
      var matches = confirm ? value === confirm.value : true;
      if (matchEl && confirm) {
        if (!confirm.value) { matchEl.textContent = ""; matchEl.className = "pw-match"; }
        else if (matches) { matchEl.textContent = "Passwords match."; matchEl.className = "pw-match ok"; }
        else { matchEl.textContent = "Passwords don't match yet."; matchEl.className = "pw-match bad"; }
      }
      // Optional password (admin editing a user): empty means "keep current".
      var valid = optional && !value && (!confirm || !confirm.value) ? true : (allMet && matches && value.length > 0);
      if (submit) submit.disabled = !valid;
      return valid;
    }

    input.addEventListener("input", function () { evaluate(true); });
    if (confirm) confirm.addEventListener("input", function () { evaluate(true); });
    form.addEventListener("submit", function (e) {
      if (!evaluate(true)) {
        e.preventDefault();
        input.focus();
      }
    });
    evaluate(false);
  });
})();
