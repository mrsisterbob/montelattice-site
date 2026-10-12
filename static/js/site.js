/* Monte Lattice - the site's two animations, both played once when scrolled into view:
   the figures on /lattice and /job-engine count up, and the tool logos on /lattice settle into
   their grid around the mark. Everything else on the site is static. Both respect
   prefers-reduced-motion (the number snaps to its final value; the logos never scatter), and
   the server-rendered markup is already the finished state with JS off. */
(function () {
  var REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function formatValue(el, n) {
    var suffix = el.dataset.suffix || "";
    var isFloat = String(el.dataset.target).indexOf(".") !== -1;
    if (isFloat) return n.toFixed(1) + suffix;
    var whole = Math.round(n);
    // data-group is opt-in: the /job-engine tiles print "1,234", so the animation must end as
    // "1,234" and not "1234". The /lattice strip does not set it and is unchanged.
    return (el.hasAttribute("data-group") ? whole.toLocaleString("en-US") : whole) + suffix;
  }

  function countUp(el) {
    var target = parseFloat(el.dataset.target);
    if (isNaN(target)) return;
    if (REDUCE_MOTION || target === 0) { el.textContent = formatValue(el, target); return; }

    var duration = 900;
    var start = null;
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / duration);
      var eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      el.textContent = formatValue(el, target * eased);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  // Called by home.html and job_engine.html once the page is rendered with each element's data-target.
  function armCountUp() {
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-count][data-target]"));
    if (!els.length) return;

    if (!("IntersectionObserver" in window)) {
      els.forEach(countUp);
      return;
    }

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          countUp(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.5 });

    els.forEach(function (el) { observer.observe(el); });
  }

  // Tool logos on /lattice: scattered, then settling into the grid once when it is on screen.
  // The markup is the settled grid; this only adds the classes, and only when motion is allowed.
  function armToolSettle() {
    var grid = document.querySelector(".tool-grid");
    if (!grid || REDUCE_MOTION || !("IntersectionObserver" in window)) return;
    grid.classList.add("is-scattered");
    function settle() {
      grid.classList.remove("is-scattered");
      grid.classList.add("is-settling");
      observer.disconnect();
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { if (entry.isIntersecting) settle(); });
    }, { threshold: 0.4 });
    observer.observe(grid);
    // Failsafe: a grid that never intersects (hidden container, a preview that does not scroll)
    // must not stay invisible.
    setTimeout(settle, 6000);
  }

  // Relative-time formatter shared by the Console cockpit (freshness stamps, Today strip).
  function formatRelative(ts) {
    if (!ts) return "never";
    var then = new Date(String(ts).replace(" ", "T"));
    if (isNaN(then.getTime())) return String(ts);
    var secs = Math.max(0, (Date.now() - then.getTime()) / 1000);
    if (secs < 90) return "just now";
    var mins = Math.round(secs / 60);
    if (mins < 90) return mins + " min ago";
    var hrs = Math.round(mins / 60);
    if (hrs < 36) return hrs + "h ago";
    var days = Math.round(hrs / 24);
    return days + "d ago";
  }

  // Light/dark toggle. The inline script in base.html has already applied any stored choice by
  // the time this runs; this only handles the click. Every page opens light whatever the OS
  // prefers, so no stored choice means light and the first click goes to dark.
  function armThemeToggle() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var root = document.documentElement;
      var current = root.getAttribute("data-theme");
      if (!current) current = "light";
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("ml-theme", next); } catch (e) { /* private mode: this session only */ }
    });
  }

  function armAll() {
    armThemeToggle();
    armToolSettle();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", armAll);
  } else {
    armAll();
  }

  window.MonteLattice = { armCountUp: armCountUp, formatRelative: formatRelative };
})();
