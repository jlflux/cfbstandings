// Two small touches only: local timestamps, and remembering which
// <details> panels the reader opened.
(function () {
  "use strict";

  document.querySelectorAll("time.updated[data-utc]").forEach(function (el) {
    var raw = el.getAttribute("data-utc");
    if (!raw) return;
    var when = new Date(raw);
    if (isNaN(when.getTime())) return;
    var fmt = new Intl.DateTimeFormat(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
      timeZoneName: "short"
    });
    el.textContent = "updated " + fmt.format(when);
    el.title = raw;
  });

  // ESPN occasionally drops a logo; hide it rather than show a broken glyph.
  document.querySelectorAll("img.logo").forEach(function (img) {
    if (img.complete && img.naturalWidth === 0) img.classList.add("failed");
    img.addEventListener("error", function () {
      img.classList.add("failed");
    });
  });

  var KEY = "cfb-open-panels";
  var open;
  try {
    open = JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch (e) {
    open = [];
  }

  document.querySelectorAll("details").forEach(function (el, i) {
    var id = (el.closest("section") ? el.closest("section").id : "") + ":" + el.className + ":" + i;
    if (open.indexOf(id) !== -1) el.open = true;
    el.addEventListener("toggle", function () {
      var at = open.indexOf(id);
      if (el.open && at === -1) open.push(id);
      if (!el.open && at !== -1) open.splice(at, 1);
      try {
        localStorage.setItem(KEY, JSON.stringify(open));
      } catch (e) {
        /* private browsing: not worth caring about */
      }
    });
  });
})();
