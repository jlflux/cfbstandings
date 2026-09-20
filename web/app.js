// Three small behaviours: pick a league, expand a team's game log, and show
// the update time in the reader's own timezone.
(function () {
  "use strict";

  var store = {
    get: function (key) {
      try { return localStorage.getItem(key); } catch (e) { return null; }
    },
    set: function (key, value) {
      try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
    }
  };

  /* ---- league picker ---------------------------------------------- */
  var pills = Array.prototype.slice.call(document.querySelectorAll(".pill"));
  var leagues = Array.prototype.slice.call(document.querySelectorAll(".league[data-slug]"));

  function show(slug, remember) {
    var found = false;
    leagues.forEach(function (section) {
      var on = section.getAttribute("data-slug") === slug;
      section.classList.toggle("is-active", on);
      if (on) found = true;
    });
    if (!found) return false;
    pills.forEach(function (pill) {
      pill.classList.toggle("on", pill.getAttribute("data-slug") === slug);
    });
    if (remember) store.set("cfb-league", slug);
    return true;
  }

  pills.forEach(function (pill) {
    pill.addEventListener("click", function () {
      var slug = pill.getAttribute("data-slug");
      if (show(slug, true) && history.replaceState) {
        history.replaceState(null, "", "#" + slug);
      }
    });
  });

  if (leagues.length) {
    var fromHash = (location.hash || "").replace(/^#/, "");
    if (!fromHash || !show(fromHash, false)) {
      show(store.get("cfb-league") || leagues[0].getAttribute("data-slug"), false);
    }
    window.addEventListener("hashchange", function () {
      show((location.hash || "").replace(/^#/, ""), true);
    });
  }

  /* ---- team game log ---------------------------------------------- */
  document.querySelectorAll(".team-toggle").forEach(function (button) {
    button.addEventListener("click", function () {
      var detail = document.getElementById(button.getAttribute("aria-controls"));
      if (!detail) return;
      var open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", open ? "false" : "true");
      detail.hidden = open;
    });
  });

  /* ---- local time, and logos ESPN failed to serve ------------------ */
  document.querySelectorAll("time[data-utc]").forEach(function (el) {
    var raw = el.getAttribute("data-utc");
    var when = raw ? new Date(raw) : null;
    if (!when || isNaN(when.getTime())) return;
    el.textContent = "updated " + new Intl.DateTimeFormat(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
      timeZoneName: "short"
    }).format(when);
    el.title = raw;
  });

  document.querySelectorAll("img.logo").forEach(function (img) {
    if (img.complete && img.naturalWidth === 0) img.classList.add("failed");
    img.addEventListener("error", function () { img.classList.add("failed"); });
  });
})();
