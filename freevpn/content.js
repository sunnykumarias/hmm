const autoClickCookies = () => {
    const buttons = document.querySelectorAll('button, div[role="button"]');
    for (const btn of buttons) {
        const text = btn.innerText || btn.textContent || "";
        if (/Allow all cookies|Accept All/i.test(text)) {
            const rect = btn.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                btn.click();
                console.log("[AutoProxy] Clicked GDPR cookie button.");
            }
        }
    }
};

// Run initially
autoClickCookies();

// Run when the DOM changes
const observer = new MutationObserver(() => {
    autoClickCookies();
});

// Wait for body to be available before observing
const initObserver = setInterval(() => {
    if (document.body) {
        observer.observe(document.body, { childList: true, subtree: true });
        clearInterval(initObserver);
    }
}, 100);
