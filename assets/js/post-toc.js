(() => {
  const toc = document.querySelector(".post-toc--desktop");
  if (!toc) {
    return;
  }

  const sections = Array.from(toc.querySelectorAll('a[href^="#"]'))
    .map((link) => {
      const id = decodeURIComponent(link.hash.slice(1));
      const heading = document.getElementById(id);
      return heading ? { heading, link } : null;
    })
    .filter(Boolean);

  if (sections.length === 0) {
    return;
  }

  let scheduled = false;

  const updateActiveSection = () => {
    scheduled = false;
    const readingLine = window.innerHeight * 0.25;
    let active = sections[0];

    for (const section of sections) {
      if (section.heading.getBoundingClientRect().top > readingLine) {
        break;
      }
      active = section;
    }

    for (const section of sections) {
      if (section === active) {
        section.link.setAttribute("aria-current", "location");
      } else {
        section.link.removeAttribute("aria-current");
      }
    }
  };

  const scheduleUpdate = () => {
    if (scheduled) {
      return;
    }
    scheduled = true;
    window.requestAnimationFrame(updateActiveSection);
  };

  window.addEventListener("scroll", scheduleUpdate, { passive: true });
  window.addEventListener("resize", scheduleUpdate);
  updateActiveSection();
})();
