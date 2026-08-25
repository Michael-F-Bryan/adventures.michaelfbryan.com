(() => {
  const navigationToggle = document.getElementById("navigation-toggle");
  const navigation = document.getElementById("primary-navigation");

  if (navigationToggle && navigation) {
    const closeNavigation = () => {
      const icon = navigationToggle.querySelector("i");
      navigation.classList.remove("is-open");
      navigationToggle.setAttribute("aria-expanded", "false");
      icon?.classList.add("fa-bars");
      icon?.classList.remove("fa-xmark");
    };

    navigationToggle.addEventListener("click", () => {
      const open = navigation.classList.toggle("is-open");
      const icon = navigationToggle.querySelector("i");
      navigationToggle.setAttribute("aria-expanded", String(open));
      icon?.classList.toggle("fa-bars", !open);
      icon?.classList.toggle("fa-xmark", open);
    });

    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a")) {
        closeNavigation();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeNavigation();
        navigationToggle.focus();
      }
    });
  }

  const colourSchemeToggle = document.getElementById("dark-mode-toggle");
  if (colourSchemeToggle) {
    const updateColourSchemeLabel = () => {
      const dark = document.body.classList.contains("colorscheme-dark");
      colourSchemeToggle.setAttribute("aria-pressed", String(dark));
      colourSchemeToggle.setAttribute(
        "aria-label",
        dark ? "Use light colour scheme" : "Use dark colour scheme",
      );
    };

    document.addEventListener("themeChanged", updateColourSchemeLabel);
    updateColourSchemeLabel();
  }
})();
