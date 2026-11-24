/* Togethr · verification page: digits-only input, expiry countdown, resend cooldown */
(function () {
  "use strict";

  var code = document.querySelector("[data-code-input]");
  if (code) {
    code.addEventListener("input", function () {
      code.value = code.value.replace(/\D/g, "").slice(0, 6);
    });
    code.addEventListener("paste", function (e) {
      var text = (e.clipboardData || window.clipboardData).getData("text") || "";
      e.preventDefault();
      code.value = text.replace(/\D/g, "").slice(0, 6);
    });
    code.focus();
  }

  function pad(n) { return n < 10 ? "0" + n : String(n); }

  /* Expiry countdown */
  var expiry = document.querySelector("[data-expires-in]");
  var timeEl = document.querySelector("[data-expiry-time]");
  if (expiry && timeEl) {
    var left = parseInt(expiry.getAttribute("data-expires-in"), 10) || 0;
    var tick = function () {
      if (left <= 0) {
        expiry.textContent = "This code has expired. Request a new one below.";
        return;
      }
      timeEl.textContent = Math.floor(left / 60) + ":" + pad(left % 60);
      left -= 1;
      setTimeout(tick, 1000);
    };
    tick();
  }

  /* Resend cooldown */
  var resend = document.querySelector("[data-resend]");
  if (resend) {
    var wait = parseInt(resend.getAttribute("data-resend-wait"), 10) || 0;
    var label = resend.textContent;
    var countdown = function () {
      if (wait <= 0) { resend.disabled = false; resend.textContent = label; return; }
      resend.disabled = true;
      resend.textContent = "Resend code in " + wait + "s";
      wait -= 1;
      setTimeout(countdown, 1000);
    };
    countdown();
  }
})();
