/* Public information pages do not initialize the analysis service. */
(() => {
    let theme = "light";
    try { if (localStorage.getItem("statementiq-theme") === "dark") theme = "dark"; } catch (_) { /* Optional storage. */ }
    const apply = () => {
        document.documentElement.setAttribute("data-theme", theme);
        const toggle = document.querySelector("[data-public-theme]");
        if (toggle) toggle.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} mode`);
    };
    apply();
    document.addEventListener("DOMContentLoaded", () => {
        apply();
        document.querySelector("[data-public-theme]")?.addEventListener("click", () => {
            theme = theme === "dark" ? "light" : "dark";
            try { localStorage.setItem("statementiq-theme", theme); } catch (_) { /* Optional storage. */ }
            if (document.startViewTransition && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
                document.startViewTransition(apply);
            } else {
                apply();
            }
        });
        document.querySelectorAll('.public-sidebar a').forEach(link => {
            if (link.getAttribute("href") === window.location.pathname) link.setAttribute("aria-current", "page");
        });
    });
})();
