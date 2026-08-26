/* Shared site behavior: parallax on the skyline backdrop, and scroll-reveal animation on
   panels/tiles. Respects prefers-reduced-motion throughout - no motion at all for users who've
   asked for it, not just "less". */
(function () {
  const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- Parallax: the skyline drifts slower than the page scrolls, so it reads as sitting
  // behind/below the content rather than pasted flat onto it. ---
  function initParallax() {
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

  // --- Depth descent (home page only): as you scroll toward the project cards, the fog
  // thickens, ambient light dims, and distant city lights fade - "sinking deeper into
  // Rapture" on the way to the destination, driven by a single --descent (0-1) CSS variable
  // read by rapture.css. ---
  function initDepthDescent() {
    const backdrop = document.querySelector(".rapture-backdrop--interactive");
    if (!backdrop || REDUCE_MOTION) return;

    let ticking = false;

    function update() {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      const progress = scrollable > 0 ? Math.min(1, window.scrollY / scrollable) : 0;
      backdrop.style.setProperty("--descent", progress.toFixed(3));
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
