// Base32 Decoder and TOTP Generator (Zero dependencies, pure JS)
function base32ToUint8Array(base32) {
    const base32chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
    let bits = '';
    for (let i = 0; i < base32.length; i++) {
        const val = base32chars.indexOf(base32.charAt(i).toUpperCase());
        if (val !== -1) {
            bits += val.toString(2).padStart(5, '0');
        }
    }
    const bytes = [];
    for (let i = 0; i + 8 <= bits.length; i += 8) {
        bytes.push(parseInt(bits.substring(i, i + 8), 2));
    }
    return new Uint8Array(bytes);
}

async function generateTOTP(secret) {
    const keyBytes = base32ToUint8Array(secret);
    const key = await crypto.subtle.importKey(
        'raw', keyBytes, { name: 'HMAC', hash: 'SHA-1' }, false, ['sign']
    );
    const buffer = new ArrayBuffer(8);
    const view = new DataView(buffer);
    view.setUint32(4, Math.floor(Date.now() / 30000), false);
    const signature = await crypto.subtle.sign('HMAC', key, buffer);
    const hmac = new Uint8Array(signature);
    const offset = hmac[hmac.length - 1] & 0x0f;
    const code = ((hmac[offset] & 0x7f) << 24) |
                 ((hmac[offset + 1] & 0xff) << 16) |
                 ((hmac[offset + 2] & 0xff) << 8) |
                 ((hmac[offset + 3] & 0xff));
    return (code % 1000000).toString().padStart(6, '0');
}

// UI Elements
function getOrCreateUIContainer() {
    let div = document.getElementById('ig-2fa-helper');
    if (!div) {
        div = document.createElement('div');
        div.id = 'ig-2fa-helper';
        div.style.cssText = 'position:fixed;top:20px;right:20px;z-index:999999;background:#fff;padding:15px;border:2px solid #e1306c;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-family:sans-serif;min-width:250px;text-align:center;';
        document.body.appendChild(div);
    }
    return div;
}

function updateStatus(statusMsg, isReady=false, secret=null) {
    window.postMessage({ type: 'IG_2FA_STATUS', status: statusMsg, ready: isReady, secret: secret }, '*');
    const div = document.getElementById('ig-2fa-helper-status');
    if (div) {
        div.innerText = statusMsg;
        if(isReady) div.style.color = "green";
        else div.style.color = "blue";
    }
}

function showInitialUI() {
    const div = getOrCreateUIContainer();
    div.innerHTML = `
        <h3 style="margin:0 0 10px 0;color:#e1306c;font-size:16px;">🚀 Auto 2FA Setup</h3>
        <p id="ig-2fa-helper-status" style="margin:10px 0 0 0;font-size:13px;color:#333;font-weight:bold;">Waiting for page data...</p>
    `;
}

function showKeyUI(secret) {
    const div = getOrCreateUIContainer();
    div.innerHTML = `
        <h3 style="margin:0 0 10px 0;color:#e1306c;font-size:16px;">✅ 2FA Auto Setup Success!</h3>
        <p style="margin:0 0 5px 0;font-size:14px;color:#333;"><strong>TOTP Secret:</strong></p>
        <input type="text" value="${secret}" readonly style="width:100%;padding:8px;margin-bottom:10px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;font-family:monospace;font-size:16px;font-weight:bold;text-align:center;background:#f8f8f8;" onclick="this.select();document.execCommand('copy');alert('Copied to clipboard!');">
        <p style="margin:0;font-size:12px;color:#666;">Click the secret to copy. The verification was automatically submitted.</p>
        <button onclick="this.parentElement.remove()" style="margin-top:10px;background:#e1306c;color:#fff;border:none;padding:8px 10px;border-radius:4px;cursor:pointer;width:100%;font-weight:bold;">Close</button>
    `;
}

let baseData = null;
let reqHeaders = {};
let lastDetectedSecret = null;
let isSendingEnable = false;
let isSendingOutro = false;
let hasAutoTriggered = false;

function extractBaseData(bodyStr, headersObj) {
    try {
        const params = new URLSearchParams(bodyStr);
        if (params.has('av') && !baseData) {
            baseData = {};
            for (let [k, v] of params.entries()) {
                if (!['variables', 'doc_id', 'fb_api_req_friendly_name'].includes(k)) {
                    baseData[k] = v;
                }
            }
            if (headersObj) {
                for (let k in headersObj) {
                    if (!['content-length', 'cookie', 'host'].includes(k.toLowerCase())) {
                        reqHeaders[k] = headersObj[k];
                    }
                }
            }
            console.log("[IG-2FA] Captured base request data");
            updateStatus("Data Captured. Waiting for you to verify email...", true);
        }
    } catch (e) {}
}

window.addEventListener('message', function(event) {
    if (event.source !== window) return;
    if (event.data.type === 'IG_2FA_ACTION' && event.data.action === 'START_SETUP') {
        if (!baseData) {
            updateStatus("❌ Error: Missing base data. Try clicking around.", false);
            return;
        }
        
        updateStatus("Generating TOTP Key...");
        const generateData = { ...baseData };
        generateData.fb_api_req_friendly_name = "useFXSettingsTwoFactorGenerateTOTPKeyMutation";
        generateData.doc_id = "9837172312995248";
        generateData.variables = JSON.stringify({
            input: {
                actor_id: baseData.av,
                client_mutation_id: crypto.randomUUID(),
                account_id: baseData.av,
                account_type: "INSTAGRAM",
                device_id: "device_id_fetch_ig_did",
                fdid: "device_id_fetch_ig_did"
            }
        });
        
        const generateHeaders = { ...reqHeaders, 'x-fb-friendly-name': generateData.fb_api_req_friendly_name, 'content-type': 'application/x-www-form-urlencoded' };
        
        window.fetch('https://accountscenter.instagram.com/api/graphql/', {
            method: 'POST',
            headers: generateHeaders,
            body: new URLSearchParams(generateData).toString()
        });
    }
});

async function processResponse(bodyText, url) {
    let cleanBody = bodyText.startsWith("for (;;);") ? bodyText.substring(9) : bodyText;
    const jsonStrings = cleanBody.split('\\n');
    
    for (let str of jsonStrings) {
        if (!str.trim()) continue;
        try {
            const json = JSON.parse(str);
            
            // EVENT A: Secret Generated
            if (json.data && json.data.xfb_two_factor_generate_totp_key && json.data.xfb_two_factor_generate_totp_key.totp_key) {
                const keyObj = json.data.xfb_two_factor_generate_totp_key.totp_key;
                if (keyObj.key_text && !isSendingEnable) {
                    lastDetectedSecret = keyObj.key_text.replace(/\\s/g, "");
                    console.log("[IG-2FA] Auto-detected Secret:", lastDetectedSecret);
                    updateStatus("Submitting Code...");
                    
                    if (baseData) {
                        isSendingEnable = true;
                        const code = await generateTOTP(lastDetectedSecret);
                        
                        const enableData = { ...baseData };
                        enableData.fb_api_req_friendly_name = "useFXSettingsTwoFactorEnableTOTPMutation";
                        enableData.doc_id = "29164158613231327";
                        enableData.variables = JSON.stringify({
                            input: {
                                actor_id: baseData.av,
                                client_mutation_id: crypto.randomUUID(),
                                account_id: baseData.av,
                                account_type: "INSTAGRAM",
                                verification_code: code,
                                device_id: "device_id_fetch_ig_did",
                                fdid: "device_id_fetch_ig_did"
                            }
                        });
                        
                        const enableHeaders = { ...reqHeaders, 'x-fb-friendly-name': enableData.fb_api_req_friendly_name, 'content-type': 'application/x-www-form-urlencoded' };
                        
                        window.fetch('https://accountscenter.instagram.com/api/graphql/', {
                            method: 'POST',
                            headers: enableHeaders,
                            body: new URLSearchParams(enableData).toString()
                        });
                        isSendingEnable = false;
                    }
                }
            }
            
            // EVENT B: Enable Success
            if (json.data && json.data.xfb_two_factor_enable_totp && json.data.xfb_two_factor_enable_totp.success === true) {
                if (!isSendingOutro) {
                    updateStatus("✅ Success!", true, lastDetectedSecret);
                    isSendingOutro = true;
                    
                    if (baseData) {
                        const outroData = { ...baseData };
                        outroData.fb_api_req_friendly_name = "FXAccountsCenterTwoFactorOutroDialogQuery";
                        outroData.doc_id = "26121190650823858";
                        outroData.variables = JSON.stringify({
                            account_id: baseData.av,
                            account_type: "INSTAGRAM",
                            interface: "IG_WEB"
                        });
                        
                        const outroHeaders = { ...reqHeaders, 'x-fb-friendly-name': outroData.fb_api_req_friendly_name, 'content-type': 'application/x-www-form-urlencoded' };
                        
                        window.fetch('https://accountscenter.instagram.com/api/graphql/', {
                            method: 'POST',
                            headers: outroHeaders,
                            body: new URLSearchParams(outroData).toString()
                        });
                    }
                    
                    if (lastDetectedSecret) {
                        showKeyUI(lastDetectedSecret);
                    }
                    isSendingOutro = false;
                }
            }
        } catch (e) {}
    }
}

// -----------------------------------------
// 1. Intercept fetch
// -----------------------------------------
const originalFetch = window.fetch;
window.fetch = async function(...args) {
    const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url);
    const options = args[1] || {};

    if (url && url.includes('api/graphql') && options.body && typeof options.body === 'string') {
        let headersObj = {};
        if (options.headers) {
            headersObj = options.headers instanceof Headers ? Object.fromEntries(options.headers.entries()) : options.headers;
        }
        extractBaseData(options.body, headersObj);
    }

    const response = await originalFetch.apply(this, args);

    if (url && url.includes('api/graphql')) {
        const clone = response.clone();
        clone.text().then(body => {
            processResponse(body, url);
        }).catch(() => {});
    }
    
    return response;
};

// -----------------------------------------
// 2. Intercept XMLHttpRequest
// -----------------------------------------
const XHR = XMLHttpRequest.prototype;
const open = XHR.open;
const send = XHR.send;
const setRequestHeader = XHR.setRequestHeader;

XHR.open = function(method, url) {
    this._url = url;
    this._requestHeaders = {};
    return open.apply(this, arguments);
};

XHR.setRequestHeader = function(header, value) {
    this._requestHeaders[header] = value;
    return setRequestHeader.apply(this, arguments);
};

XHR.send = function(postData) {
    this.addEventListener('load', function() {
        if (this._url && this._url.includes('api/graphql')) {
            if (this.responseText) {
                processResponse(this.responseText, this._url);
            }
        }
    });

    if (this._url && this._url.includes('api/graphql') && postData && typeof postData === 'string') {
        extractBaseData(postData, this._requestHeaders);
    }

    return send.apply(this, arguments);
};

console.log("[IG-2FA] Extension Interceptor Injected (Fully Auto)");

// Show status UI on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', showInitialUI);
} else {
    showInitialUI();
}
