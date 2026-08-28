/* Monte Lattice - the site's ONE animation: the numbers in the "Live from the Job Engine"
   strip count up once when scrolled into view. Everything else on the site is static.
   Respects prefers-reduced-motion (snaps straight to the final value, no tween). */
(function () {
  var REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function formatValue(el, n) {
    var suffix = el.dataset.suffix || "";
    var isFloat = String(el.dataset.target).indexOf(".") !== -1;
    return (isFloat ? n.toFixed(1) : Math.round(n)) + suffix;
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

  // Called by home.html once the API fills in each element's data-target.
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

  window.MonteLattice = { armCountUp: armCountUp };
})();
