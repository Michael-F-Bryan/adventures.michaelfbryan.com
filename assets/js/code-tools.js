(() => {
  for (const highlight of document.querySelectorAll(".post-content .highlight")) {
    const code = highlight.querySelector("pre code");
    if (!code || highlight.querySelector(".code-toolbar")) {
      continue;
    }

    highlight.classList.add("code-block");

    const toolbar = document.createElement("div");
    toolbar.className = "code-toolbar";

    const language = document.createElement("span");
    language.className = "code-toolbar__language";
    language.textContent = code.dataset.lang || "code";

    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "code-toolbar__copy";
    copy.textContent = "Copy";
    copy.setAttribute("aria-label", "Copy code to clipboard");

    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.innerText);
        copy.textContent = "Copied";
        window.setTimeout(() => {
          copy.textContent = "Copy";
        }, 1600);
      } catch {
        copy.textContent = "Copy failed";
      }
    });

    toolbar.append(language, copy);
    highlight.prepend(toolbar);
  }
})();
