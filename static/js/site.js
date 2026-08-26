/* Shared site behavior: parallax on the skyline backdrop, and scroll-reveal animation on
   panels/tiles. Respects prefers-reduced-motion throughout - no motion at all for users who've
   asked for it, not just "less". */
(function () {
  const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- Parallax: the skyline drifts slower than the page scrolls, so it reads as sitting
  // behind/below the content rather than pasted flat onto it. Skipped on the home page's
  // interactive backdrop - there, the viewBox-growth effect in initDepthDescent() already
  // supplies scroll-driven motion (revealing lower floors), and letting both effects fight
  // over the same transform/positioning would just look janky. ---
  function initParallax() {
    const backdrop = document.querySelector(".rapture-backdrop");
    if (backdrop && backdrop.classList.contains("rapture-backdrop--interactive")) return;
    const svg = document.querySelector(".rapture-backdrop svg");
    if (!svg || REDUCE_MOTION) return;

    const PARALLAX_FACTOR = 0.18; // fraction of scroll distance the skyline actually moves
    const MAX_OFFSET_PX = 70; // caps drift so buildings never scroll fully out of frame
    let ticking = false;

    function update() {
      const offset = Math.min(window.scrollY * PARALLAX_FACTOR, MAX_OFFSET_PX);
      svg.style.transform = `translateX(-50%) translateY(${offset}px)`;
      ticking = false;
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });
  }

  // --- Scroll reveal: panels/tiles fade + rise into place the first time they enter view. ---
  function initScrollReveal() {
    const targets = document.querySelectorAll(".ornate-panel, .metric-tile, .project-card");
    if (!targets.length) return;

    if (REDUCE_MOTION) {
      targets.forEach((el) => el.classList.add("reveal-visible"));
      return;
    }

    targets.forEach((el) => el.classList.add("reveal-pending"));

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );

    targets.forEach((el) => observer.observe(el));
  }

  // --- Depth descent (home page only): as you scroll toward the project cards, a purple
  // atmospheric tone blends in and the skyline reveals far more floors than it first appeared
  // to have - "these buildings looked like 20 stories, but they never end" - driven by a
  // single --descent (0-1) CSS variable (read by rapture.css) plus a direct viewBox height
  // change (SVG attributes aren't reachable from CSS). Building ROOFS stay visually fixed
  // because the SVG is top-anchored (see .rapture-backdrop svg { top: 0 } in rapture.css) -
  // growing the viewBox only reveals more of what's drawn BELOW them, never moves the top. ---
  function initDepthDescent() {
    const backdrop = document.querySelector(".rapture-backdrop--interactive");
    const svg = backdrop && backdrop.querySelector("svg");
    if (!backdrop || !svg) return;

    const BASE_VIEWBOX_HEIGHT = 570; // must match the SVG's authored viewBox height
    const MAX_EXTRA_HEIGHT = 2200; // how many extra "floors" of viewBox become revealable
    let ticking = false;

    function update() {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      const progress = scrollable > 0 ? Math.min(1, window.scrollY / scrollable) : 0;
      backdrop.style.setProperty("--descent", progress.toFixed(3));

      if (!REDUCE_MOTION) {
        const extraHeight = progress * MAX_EXTRA_HEIGHT;
        const totalHeight = BASE_VIEWBOX_HEIGHT + extraHeight;
        svg.setAttribute("viewBox", `0 -70 1600 ${totalHeight.toFixed(0)}`);
      }
      ticking = false;
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });
    window.addEventListener("resize", update);
    update();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initParallax();
    initScrollReveal();
    initDepthDescent();
  });
})();
