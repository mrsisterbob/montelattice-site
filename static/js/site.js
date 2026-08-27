/* Shared site behavior: parallax on the skyline backdrop, and scroll-reveal animation on
   panels/tiles. Respects prefers-reduced-motion throughout - no motion at all for users who've
   asked for it, not just "less". */
(function () {
  const REDUCE_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- Parallax: the skyline drifts slower than the page scrolls, so it reads as sitting
  // behind/below the content rather than pasted flat onto it. Skipped on the home page's
  // interactive backdrop - there, initInfiniteAscent() below drives a much larger, UNBOUNDED
  // upward pan instead, and the two effects would otherwise fight over the same transform. ---
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

  // --- Fog descent (home page only): --descent (0-1, capped at full page scroll) drives the
  // fog-layer growing/strengthening in rapture.css - the ONLY depth effect now, no separate
  // tint. ---
  function initFogDescent() {
    const backdrop = document.querySelector(".rapture-backdrop--interactive");
    if (!backdrop) return;

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

  // --- Infinite ascent (home page only): the skyline pans UPWARD, unbounded, as you scroll -
  // building tops scroll off the top of the screen and never return, continuously replaced by
  // the extended lower floors already drawn in the SVG (see _backdrop_home.html, height=2400
  // rects) and by the "deep buildings" group positioned further down still. Deliberately NOT
  // clamped to a max offset (unlike the old parallax) - the buildings are meant to look like
  // they never end, not just drift a little. ---
  function initInfiniteAscent() {
    const backdrop = document.querySelector(".rapture-backdrop--interactive");
    const svg = backdrop && backdrop.querySelector("svg");
    const fog = backdrop && backdrop.querySelector(".fog-layer");
    if (!backdrop || !svg || REDUCE_MOTION) return;

    const ASCENT_FACTOR = 0.25; // pixels the skyline pans upward per pixel scrolled
    let ticking = false;

    function update() {
      const offset = window.scrollY * ASCENT_FACTOR;
      svg.style.transform = `translateX(-50%) translateY(-${offset}px)`;
      // The fog must pan WITH the buildings (not stay pinned to the viewport) so it reads as
      // wrapping around the skyline as it rises, rather than sitting still while buildings
      // slide past underneath it. Only the vertical component matters here - the fog layer
      // isn't horizontally centered/offset the way the SVG is.
      if (fog) fog.style.transform = `translateY(-${offset}px)`;
      ticking = false;
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        window.requestAnimationFrame(update);
        ticking = true;
      }
    }, { passive: true });
  }

  // --- Establishing shot (home page only): a brief "curtain rises" moment on first load -
  // the scene starts fully dark/fogged-in and the vignette eases open over ~1.8s as a few
  // windows light up in sequence, like a city waking. Runs once per page load, never on
  // scroll. Skipped entirely under prefers-reduced-motion - the scene just renders in its
  // final state immediately. ---
  function initEstablishingShot() {
    const backdrop = document.querySelector(".rapture-backdrop--interactive");
    if (!backdrop || REDUCE_MOTION) return;

    backdrop.classList.add("establishing-shot");
    // Force a reflow so the browser registers the starting state before the transition class
    // is added - otherwise both classes could land in the same frame and the transition
    // never visibly plays.
    void backdrop.offsetWidth;
    requestAnimationFrame(function () {
      backdrop.classList.add("establishing-shot--revealed");
    });
    window.setTimeout(function () {
      backdrop.classList.remove("establishing-shot", "establishing-shot--revealed");
    }, 2200);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initParallax();
    initScrollReveal();
    initFogDescent();
    initInfiniteAscent();
    initEstablishingShot();
  });
})();
