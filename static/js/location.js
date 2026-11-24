/* Togethr · opt-in nearby-city helper.
   Only runs inside [data-geo-city] blocks. Coordinates are never stored. */
(function () {
  "use strict";

  var DEFAULT_ENDPOINT = "/geo/cities/";
  var MAX_LABEL = 100;

  function setStatus(status, message) {
    if (!status) return;
    status.textContent = message || "";
  }

  /* Keep the request on our own origin so coordinates never go to another host. */
  function safeEndpoint(raw) {
    try {
      var anchor = document.createElement("a");
      anchor.href = raw || DEFAULT_ENDPOINT;
      if (anchor.protocol !== window.location.protocol || anchor.host !== window.location.host) {
        return DEFAULT_ENDPOINT;
      }
      return anchor.pathname + anchor.search;
    } catch (e) {
      return DEFAULT_ENDPOINT;
    }
  }

  function clearList(list) {
    while (list.firstChild) list.removeChild(list.firstChild);
  }

  function fillList(list, cities, limit) {
    clearList(list);
    cities.slice(0, limit).forEach(function (city) {
      var label = String(city).replace(/\s+/g, " ").trim().slice(0, MAX_LABEL);
      if (!label) return;
      var option = document.createElement("option");
      option.value = label;
      list.appendChild(option);
    });
    return list.childElementCount;
  }

  function positionError(error) {
    if (!error) return "Location is unavailable. Type your city instead.";
    if (error.code === 1) return "Location permission was denied. Type your city instead.";
    if (error.code === 2) return "We couldn't detect your location. Type your city instead.";
    if (error.code === 3) return "Location took too long. Try again or type your city.";
    return "Location is unavailable. Type your city instead.";
  }

  function initBlock(block, index) {
    var input = block.querySelector("[data-geo-input]") || block.querySelector('input[name="location"]');
    var button = block.querySelector("[data-geo-button]");
    var list = block.querySelector("[data-geo-list]");
    var status = block.querySelector("[data-geo-status]");
    if (!input || !button || !list) return;

    if (!list.id) list.id = "geo-cities-" + index;
    if (status) status.setAttribute("aria-live", "polite");
    button.setAttribute("type", "button");

    var endpoint = safeEndpoint(block.getAttribute("data-geo-endpoint"));
    var limit = parseInt(block.getAttribute("data-geo-limit"), 10) || 3;
    var controller = null;

    function busy(isBusy) {
      button.disabled = isBusy;
      button.setAttribute("aria-busy", String(isBusy));
    }

    if (!window.isSecureContext || !navigator.geolocation) {
      button.disabled = true;
      button.setAttribute("aria-disabled", "true");
      setStatus(status, window.isSecureContext
        ? "Location detection isn't supported by this browser. Type your city instead."
        : "Location detection needs HTTPS (or localhost). Type your city instead.");
      return;
    }

    function showCities(cities) {
      var count = fillList(list, cities, limit);
      if (!count) {
        setStatus(status, "No nearby city found. Type your city instead.");
        return;
      }
      input.setAttribute("list", list.id);
      setStatus(status, "Nearby cities are ready. Pick one or type your own.");
      input.focus();
      if (typeof input.showPicker === "function") {
        try {
          input.showPicker();  /* best effort; focus still shows the saved suggestions */
        } catch (e) {
          /* Some browsers require a fresh user gesture. No action needed. */
        }
      }
    }

    function lookup(position) {
      var separator = endpoint.indexOf("?") === -1 ? "?" : "&";
      var url = endpoint + separator
        + "lat=" + encodeURIComponent(position.coords.latitude.toFixed(6))
        + "&lon=" + encodeURIComponent(position.coords.longitude.toFixed(6));

      if (typeof AbortController !== "undefined") {
        if (controller) controller.abort();
        controller = new AbortController();
      }

      setStatus(status, "Finding nearby cities…");
      var options = { credentials: "same-origin", headers: { "Accept": "application/json" } };
      if (controller) options.signal = controller.signal;

      fetch(url, options).then(function (response) {
        if (!response.ok) throw new Error("lookup failed");
        return response.json();
      }).then(function (data) {
        showCities(Array.isArray(data.cities) ? data.cities : []);
      }).catch(function (error) {
        if (error && error.name === "AbortError") return;
        setStatus(status, "City lookup failed. Type your city instead.");
      }).then(function () {
        controller = null;
        busy(false);
      });
    }

    button.addEventListener("click", function (event) {
      event.preventDefault();
      busy(true);
      clearList(list);
      input.removeAttribute("list");
      setStatus(status, "Detecting your area…");
      navigator.geolocation.getCurrentPosition(lookup, function (error) {
        setStatus(status, positionError(error));
        busy(false);
      }, {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 600000
      });
    });
  }

  function init() {
    var blocks = document.querySelectorAll("[data-geo-city]");
    for (var i = 0; i < blocks.length; i += 1) initBlock(blocks[i], i + 1);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
