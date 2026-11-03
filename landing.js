'use strict';
(() => {
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const animations = new Set();
  const orbits = [...document.querySelectorAll('[data-parallax]')];
  let frame;

  // Native scrolling stays in charge. Only the decorative illustrations move.
  function moveArtwork() {
    frame = undefined;
    if (reducedMotion.matches) return;
    for (const orbit of orbits) {
      const section = orbit.closest('section').getBoundingClientRect();
      if (section.bottom < 0 || section.top > innerHeight) continue;
      const distance = innerHeight / 2 - (section.top + section.height / 2);
      const shift = Math.max(-18, Math.min(18, distance * Number(orbit.dataset.parallax)));
      orbit.style.transform = 'translate3d(0,' + shift.toFixed(2) + 'px,0)';
    }
  }
  function requestMove() {
    if (!reducedMotion.matches && frame === undefined) frame = requestAnimationFrame(moveArtwork);
  }
  function resetMotion() {
    if (frame !== undefined) cancelAnimationFrame(frame);
    frame = undefined;
    for (const animation of animations) animation.cancel();
    animations.clear();
    for (const orbit of orbits) orbit.style.removeProperty('transform');
    requestMove();
  }

  // Content stays visible when JavaScript or observers are unavailable.
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        if (reducedMotion.matches || typeof entry.target.animate !== 'function') continue;
        const kind = entry.target.dataset.reveal;
        const travel = kind === 'heading' ? 24 : kind === 'row' ? 12 : 16;
        const animation = entry.target.animate([
          {opacity: 0, transform: 'translateY(' + travel + 'px)'},
          {opacity: 1, transform: 'translateY(0)'}
        ], {
          duration: kind === 'heading' ? 900 : 750,
          delay: kind === 'copy' ? 70 : kind === 'action' ? 130 : 0,
          easing: 'cubic-bezier(.16,1,.3,1)'
        });
        animations.add(animation);
        animation.onfinish = () => animations.delete(animation);
      }
    }, {threshold: .16});
    document.querySelectorAll('[data-reveal]').forEach(element => observer.observe(element));
  }

  addEventListener('scroll', requestMove, {passive: true});
  addEventListener('resize', requestMove, {passive: true});
  reducedMotion.addEventListener('change', resetMotion);
  requestMove();
})();
