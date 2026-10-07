document.addEventListener('DOMContentLoaded', () => {
    const statusText = document.getElementById('status-text');
    const startBtn = document.getElementById('start-btn');
    const secretContainer = document.getElementById('secret-container');
    const secretInput = document.getElementById('secret-input');

    // Update UI based on storage state
    function updateUI(data) {
        if (data.ig2faStatus) {
            statusText.innerText = data.ig2faStatus;
            
            if (data.ig2faStatus.includes("Error") || data.ig2faStatus.includes("❌")) {
                statusText.style.color = "red";
            } else if (data.ig2faStatus.includes("Success") || data.ig2faStatus.includes("✅")) {
                statusText.style.color = "green";
            } else if (data.ig2faReady) {
                statusText.style.color = "green";
            } else {
                statusText.style.color = "#333";
            }
        }

        if (data.ig2faReady) {
            startBtn.disabled = false;
        } else {
            startBtn.disabled = true;
        }

        if (data.ig2faSecret) {
            secretContainer.style.display = "block";
            secretInput.value = data.ig2faSecret;
            startBtn.style.display = "none";
        }
    }

    // Initialize from storage
    chrome.storage.local.get(['ig2faStatus', 'ig2faSecret', 'ig2faReady'], (data) => {
        updateUI(data);
    });

    // Listen for changes
    chrome.storage.onChanged.addListener((changes, namespace) => {
        if (namespace === 'local') {
            const newData = {};
            if (changes.ig2faStatus) newData.ig2faStatus = changes.ig2faStatus.newValue;
            if (changes.ig2faSecret) newData.ig2faSecret = changes.ig2faSecret.newValue;
            if (changes.ig2faReady !== undefined) newData.ig2faReady = changes.ig2faReady.newValue;
            
            chrome.storage.local.get(['ig2faStatus', 'ig2faSecret', 'ig2faReady'], (data) => {
                updateUI({ ...data, ...newData });
            });
        }
    });

    // Handle button click
    startBtn.addEventListener('click', () => {
        startBtn.disabled = true;
        startBtn.innerText = "Processing...";
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { action: 'START_SETUP' });
            }
        });
    });

    // Handle copy
    secretInput.addEventListener('click', () => {
        secretInput.select();
        document.execCommand('copy');
        
        const originalVal = secretInput.value;
        secretInput.value = "COPIED!";
        setTimeout(() => {
            secretInput.value = originalVal;
        }, 1000);
    });
});
