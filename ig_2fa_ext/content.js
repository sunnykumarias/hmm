// Inject the logic into the main page context to intercept fetch requests
const script = document.createElement('script');
script.src = chrome.runtime.getURL('inject.js');
(document.head || document.documentElement).appendChild(script);
script.onload = function() {
    script.remove();
};

// Bridge between injected script and extension storage/popup
window.addEventListener('message', function(event) {
    if (event.source !== window) return;

    if (event.data.type && event.data.type === 'IG_2FA_STATUS') {
        chrome.storage.local.set({
            ig2faStatus: event.data.status,
            ig2faSecret: event.data.secret || null,
            ig2faReady: event.data.ready || false
        });
    }
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'START_SETUP') {
        window.postMessage({ type: 'IG_2FA_ACTION', action: 'START_SETUP' }, '*');
        sendResponse({ success: true });
    }
});
