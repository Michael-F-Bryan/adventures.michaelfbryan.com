/**
 * Schedules a function to be called after the DOM is loaded.
 */
function onLoaded(cb) {
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(cb, 1);
    } else {
        document.addEventListener("DOMContentLoaded", cb);
    }
}

function initializeMermaid() {
    var config = {
        startOnLoad: true,
        flowchart: {
            useMaxWidth: false,
            htmlLabels: true
        }
    };
    mermaid.initialize(config);
}

/**
 * The current theme doesn't let you get a link to a header by just clicking on
 * it.
 */
function addPermalinks() {
    document.querySelectorAll("h2, h3, h4, h5, h6")
        .forEach(applyPermalink);
}

function applyPermalink(element) {
    if (element.id) {
        const link = document.createElement("a");
        link.href = "#" + element.id;

        while (element.firstChild) {
            const child = element.firstChild;
            element.removeChild(child);
            link.appendChild(child);
        }

        element.appendChild(link);
    }
}

function initializeMathJax() {
    console.log("Initializing MathJax", MathJax);

    MathJax.Hub.Config({
        tex2jax: {
            inlineMath: [['$', '$'], ['\\(', '\\)']],
            displayMath: [['$$', '$$']],
            processEscapes: true,
            processEnvironments: true,
            skipTags: ['script', 'noscript', 'style', 'textarea', 'pre'],
            TeX: {
                equationNumbers: { autoNumber: "AMS" },
                extensions: ["AMSmath.js", "AMSsymbols.js"]
            }
        }
    });
    MathJax.Hub.Queue(function () {
        // Fix <code> tags after MathJax finishes running. This is a
        // hack to overcome a shortcoming of Markdown. Discussion at
        // https://github.com/mojombo/jekyll/issues/199
        var all = MathJax.Hub.getAllJax(), i;
        for (i = 0; i < all.length; i += 1) {
            all[i].SourceElement().parentNode.className += ' has-jax';
        }
    });

    MathJax.Hub.Config({
        // Autonumbering by mathjax
        TeX: { equationNumbers: { autoNumber: "AMS" } }
    });
}

onLoaded(initializeMermaid);
onLoaded(addPermalinks);
