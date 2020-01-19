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

onLoaded(initializeMermaid);
onLoaded(addPermalinks);