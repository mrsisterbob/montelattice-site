/* Monte Lattice - the tool web's settle animation, played once per grid when it scrolls into view.
   Its own file, not site.js: the homepage loads no site.js (it binds #theme-toggle itself, and a
   second handler would cancel the first). Every .tool-grid on the page is armed on its own, with
   its own observer and failsafe. The server-rendered markup is already the settled grid, so with
   JS off or reduced motion nothing here runs and nothing is hidden. */
(function () {
  var REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Scattered, then settling into the grid once when it is on screen. The markup is the settled
  // grid; this only adds the classes, and only when motion is allowed.
  function armToolSettle(grid) {
    if (REDUCE_MOTION || !("IntersectionObserver" in window)) return;
    grid.classList.add("is-scattered");
    var failsafe;
    function settle() {
      clearTimeout(failsafe);
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
    failsafe = setTimeout(settle, 6000);
  }

  function armAll() {
    [].slice.call(document.querySelectorAll(".tool-grid")).forEach(armToolSettle);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", armAll);
  } else {
    armAll();
  }
})();
