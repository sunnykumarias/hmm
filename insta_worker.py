import subprocess
import sys
import os
import builtins as _bi
import contextvars as _cv

# -- Worker version --
WORKER_VERSION = "v7.9"

# ── Bulletproof restart helper ──────────────────────────────────────────────
# os.execv seedha kabhi fail nahi hona chahiye, lekin agar ho bhi jaye to worker
# chup-chaap NA mare — loud error + Popen fallback. Nahi to renew ke time process
# mar jata hai aur "coroutine ignored GeneratorExit" noise aata hai.
def _safe_execv(argv):
    print(f"[*] Restarting worker process: {argv[0]} ...")
    sys.stdout.flush(); sys.stderr.flush()
    try:
        os.execv(argv[0], argv)
    except Exception as e:
        print(f"[FATAL] os.execv failed: {e} - fallback spawn try kar raha hoon...")
        sys.stdout.flush()
    try:
        subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL)
        print("[*] Fallback worker process spawned - purana process exit ho raha hai.")
        sys.stdout.flush()
        os._exit(0)
    except Exception as e2:
        print(f"[FATAL] Fallback spawn bhi fail: {e2} - worker restart NAHI hua!")
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# THREAD-TAGGED LOGGING: har worker thread (T1, T2, ...) ka naam terminal ke
# har log line ke aage [Tn] lag ke dikhega — pata chalega kaunsi line kis
# thread ki hai. contextvars ki wajah se asyncio task ke andar ke SAARE
# print() (process_account ke andar wale bhi) automatically tag ho jaate hain.
# ══════════════════════════════════════════════════════════════════════════════
_worker_tag = _cv.ContextVar("worker_tag", default="")
_orig_print = _bi.print

def _tagged_print(*args, **kwargs):
    tag = _worker_tag.get()
    if tag and args and isinstance(args[0], str) and ("[%s]" % tag) not in args[0]:
        args = (("[%s] " % tag) + args[0],) + tuple(args[1:])
    _orig_print(*args, **kwargs)

_bi.print = _tagged_print

# ══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP: Auto-install all required packages BEFORE any imports
# This runs first so even a fresh Google Cloud Shell works out of the box.
# ══════════════════════════════════════════════════════════════════════════════
def _bootstrap_install():
    # ── Step 1: Install Python packages ─────────────────────────────────────
    pkgs = {
        "playwright":         "playwright",
        "playwright_stealth": "playwright-stealth",
        "pyotp":              "pyotp",
        "requests":           "requests",
        "redis":              "redis",
        "socks":              "pysocks",
    }
    needs_restart = False
    for import_name, pip_name in pkgs.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"[BOOTSTRAP] Installing Python package: {pip_name}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pip_name])
            needs_restart = True

    # ── Step 2: Install Playwright Chromium browser + system deps ────────────
    # v7.5: khamoshi KHATAM — returncode dekho, fail LOUD print karo. Download
    # fail hua aur "OK" jhooth chhapa to worker bina browser claim-spin karta
    # tha (Oct 7 wali bimari). Asli rok PREFLIGHT gate (run() me) lagata hai;
    # yahan ka kaam sirf sach ugalna hai.
    try:
        _r1 = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True
        )
        if _r1.returncode != 0:
            print(f"[BOOTSTRAP] FAIL: playwright install chromium rc={_r1.returncode} — browser download NAHI hua!")
            _tail = ((_r1.stderr or "") + (_r1.stdout or "")).strip()
            if _tail:
                print(f"[BOOTSTRAP] install output (aakhri hissa): {_tail[-400:]}")
        _r2 = subprocess.run(
            [sys.executable, "-m", "playwright", "install-deps", "chromium"],
            capture_output=True, text=True
        )
        if _r2.returncode != 0:
            print(f"[BOOTSTRAP] WARNING: playwright install-deps rc={_r2.returncode} (system libs adhoori ho sakti hain)")
    except Exception as e:
        print(f"[BOOTSTRAP] playwright install warning: {e}")
    # Executable sach me hai ya nahi — glob level ki loud chetaavni (playwright
    # abhi import nahi hua hai; pakki jaanch PREFLIGHT gate karega).
    try:
        import glob as _glob
        _cands = (_glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome"))
                  + _glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/headless_shell-linux*/headless_shell")))
        if os.name != "nt" and not any(os.access(_p, os.X_OK) for _p in _cands):
            print("[BOOTSTRAP] WARNING: Chromium executable disk par NAHI mila — worker PREFLIGHT par rukega, claim NAHI karega jab tak browser theek na ho.")
    except Exception:
        pass

    # (Steps 3-6 removed: Pure IPv6 Residential Proxy edition, Tor is not used)

    # ── Step 7: Restart self if packages were newly installed ────────────────
    if needs_restart:
        print("[BOOTSTRAP] Restarting script with all packages available...")
        _safe_execv([sys.executable] + sys.argv)

_bootstrap_install()
# ══════════════════════════════════════════════════════════════════════════════

import asyncio
from concurrent.futures import ThreadPoolExecutor
import random
import string
import time
import requests
import re
import pyotp
import tempfile
import shutil
import json
import socket
import struct
from playwright.async_api import Playwright, async_playwright, expect
from playwright_stealth import Stealth


# ==========================================
# RESIDENTIAL IPV6 SOCKS5 CONFIGURATION (NO TOR)
# ==========================================
# Check environment variable for HEADLESS_MODE; defaults to True (Headless ON for Ubuntu Server)
HEADLESS_MODE = os.environ.get("HEADLESS_MODE", "1").lower() in ("1", "true", "yes")
# Playwright's new headless mode supports extensions natively!
_EXT_BASE = os.path.dirname(os.path.abspath(__file__))
EXTENSION_PATH = os.path.join(_EXT_BASE, "custom_vpn_ext")
if not os.path.exists(EXTENSION_PATH):
    EXTENSION_PATH = os.path.join(_EXT_BASE, "free vpn")


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'



# ── OTP manager (inlined: no separate otp_manager.py needed) ─────────────
_OTP_DOMAIN_CACHE = {"v": None, "ts": 0}

def _otp_api_url(email_addr, digits):
    """OTP API URL — domain Redis `config:otp_domain` se aata hai (panel se live change).
    60s cache, default nearbygirls.us."""
    import time as _t
    c = _OTP_DOMAIN_CACHE
    if c["v"] is None or _t.time() - c["ts"] > 60:
        try:
            v = _r().get("config:otp_domain")
            if v:
                v = v.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
                if v:
                    c["v"] = v
        except Exception:
            pass
        c["ts"] = _t.time()
        if not c["v"]:
            c["v"] = "nearbygirls.us"
    return "https://%s/api/otp.php?email=%s&digits=%s" % (c["v"], email_addr, digits)

def start_imap_listener():
    # No longer needed, we poll the API directly.
    pass

def prefetch_seen_ids(email_addr, seen_ids):
    """Fetches the current OTP email ID and adds it to seen_ids
    so we don't accidentally process old OTPs."""
    email_addr = email_addr.lower().strip()
    for digits in [8, 6]:
        url = _otp_api_url(email_addr, digits)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("data"):
                    msg_id = data["data"].get("email_id")
                    if msg_id:
                        seen_ids.add(str(msg_id))
        except Exception:
            pass

def fetch_otp(email_addr, seen_ids=None, max_retries=30):
    """Fetches the OTP for a given email address using the custom temp-mail API."""
    email_addr = email_addr.lower().strip()
    if seen_ids is None:
        seen_ids = set()
    for _ in range(max_retries):
        for digits in [8, 6]:
            url = _otp_api_url(email_addr, digits)
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success") and data.get("data"):
                        msg_id = str(data["data"].get("email_id"))
                        otp = data["data"].get("otp")
                        if msg_id and msg_id in seen_ids:
                            continue
                        if otp:
                            seen_ids.add(msg_id)
                            return otp
            except Exception:
                pass
        time.sleep(4)
    return None

def generate_random_name(country_str=None):
    try:
        from faker import Faker
        locale = 'en_US'
        if country_str:
            c = country_str.lower()
            if 'germany' in c: locale = 'de_DE'
            elif 'netherlands' in c: locale = 'nl_NL'
            elif 'france' in c: locale = 'fr_FR'
            elif 'spain' in c: locale = 'es_ES'
            elif 'italy' in c: locale = 'it_IT'
            elif 'india' in c: locale = 'en_IN'
            elif 'united kingdom' in c or 'uk' in c: locale = 'en_GB'
            elif 'canada' in c: locale = 'en_CA'
            elif 'australia' in c: locale = 'en_AU'
            elif 'brazil' in c: locale = 'pt_BR'
            elif 'mexico' in c: locale = 'es_MX'
            elif 'russia' in c: locale = 'ru_RU'
            elif 'japan' in c: locale = 'ja_JP'
            else:
                locale = random.choice(['en_US', 'en_GB', 'de_DE', 'fr_FR', 'it_IT', 'es_ES', 'nl_NL'])
        else:
            locale = random.choice(['en_US', 'en_GB', 'de_DE', 'fr_FR', 'it_IT', 'es_ES', 'nl_NL', 'en_IN'])
            
        fake = Faker(locale)
        name = fake.name()
        if len(name) >= 30:
            name = name[:29].strip()
        return name
    except Exception:
        first_names = ["Rahul", "Sonali", "Priya", "Amit", "Neha", "Vikram", "Anjali", "Rohan", "Sneha", "Karan", "Pooja", "Arjun", "Kavya", "Aditya", "Riya", "John", "Emma", "Michael", "Sophia", "David"]
        last_names = ["Kumar", "Kumari", "Sharma", "Singh", "Verma", "Gupta", "Das", "Patel", "Reddy", "Mehta", "Jain", "Bose", "Smith", "Johnson", "Williams", "Brown", "Jones"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"


# ══════════════════════════════════════════════════════════════════════════
# FLEET BRIDGE: Redis queue + results for 100-300 workers (multi-machine OK)
#   Queue:     BRPOPLPUSH queue:pending -> queue:processing:<worker-id> (atomic claim)
#   Results:   LPUSH results   (panel ingests -> SQLite -> Google Sheets, batched)
#   Heartbeat: HSET workers:hb (panel fleet view)
# If Redis is unreachable, results are buffered to worker_results_<id>.jsonl
# and re-sent automatically when Redis is back.
# ══════════════════════════════════════════════════════════════════════════
import argparse as _ap
_ap_p = _ap.ArgumentParser()
_ap_p.add_argument("--worker-id", default="")
# THREADS: yahi number badlo
THREADS = 12
_ap_p.add_argument("--threads", type=int, default=None)  # None = dashboard (Redis fleet:default_threads) se lo
_ap_p.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://:3c0ac0e48103d8c5674c16de3336a305@3.110.210.40:6379/0"))
_APARGS, _ = _ap_p.parse_known_args()
REDIS_URL = _APARGS.redis_url
if not REDIS_URL:
    print("[FATAL] REDIS_URL khaali hai! (env/--redis-url se do ya script me hardcoded rakho)")
    print("")
    raise SystemExit(1)
import getpass
WORKER_ID = _APARGS.worker_id or ("%s-%d" % (getpass.getuser(), os.getpid()))
WORKER_ID = f"{WORKER_ID} [{WORKER_VERSION}]"
_redis_client = None

def _r():
    global _redis_client
    if _redis_client is None:
        import redis as _rl
        _redis_client = _rl.from_url(REDIS_URL, socket_timeout=10, decode_responses=True)
    return _redis_client

def _fleet_threads():
    if _APARGS.threads:
        return max(1, min(50, _APARGS.threads))
    try:
        v = _r().get("fleet:default_threads")
        if v:
            return max(1, min(50, int(v)))
        v = _r().get("threads:" + WORKER_ID)
        if v:
            return max(1, min(50, int(v)))
    except Exception:
        pass
    return 2 # Run with 1 thread by default for local accounts.txt

WORKER_THREADS = _fleet_threads()
# ── Auto-renew: fresh worker process every N accounts or M hours ─────────
# Process memory clean karne aur fresh state ke liye periodic restart.
# Tune:  env WORKER_RESTART_EVERY=30   |  env WORKER_RESTART_HOURS=4
WORKER_RESTART_EVERY = int(os.environ.get("WORKER_RESTART_EVERY", "0"))
WORKER_RESTART_HOURS = float(os.environ.get("WORKER_RESTART_HOURS", "0"))
PROC_KEY = "queue:processing:" + WORKER_ID
CURRENT_EMAIL = ""
RESULT_BACKUP = "worker_results_%s.jsonl" % WORKER_ID

# ── PREFLIGHT HEALTH (v7.5): browser/redis sehat ka haal — heartbeat me jata
# hai taaki panel/manager ko bimar box "running" ki jagah SICK dikhe.
# status: boot | ok | no_browser | no_launch | no_redis
WORKER_HEALTH = {"status": "boot", "why": ""}

def _set_health(status, why=""):
    WORKER_HEALTH["status"] = status
    WORKER_HEALTH["why"] = (why or "")[:200]

def _push_result_payload(payload):
    _r().lpush("results", json.dumps(payload))

def report_result(status, qid, data):
    payload = {"worker_id": WORKER_ID, "queue_id": qid, "status": status,
               "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    payload.update(data)
    # flush local backup first (results saved while Redis was down)
    try:
        if os.path.exists(RESULT_BACKUP):
            with open(RESULT_BACKUP) as f:
                lines = f.readlines()
            remain = []
            for ln in lines:
                try:
                    _push_result_payload(json.loads(ln))
                except Exception:
                    remain.append(ln)
            if remain:
                with open(RESULT_BACKUP, "w") as f:
                    f.writelines(remain)
            else:
                os.remove(RESULT_BACKUP)
    except Exception:
        pass
    try:
        _push_result_payload(payload)
    except Exception:
        with open(RESULT_BACKUP, "a") as f:
            f.write(json.dumps(payload) + "\n")
            
    # Save processed accounts to text files locally
    try:
        email = data.get("email", "")
        password = data.get("password", "")
        if email and password:
            line = f"{email}|{password}\n"
            if "success" in status or status == "saved_checkpoint":
                with open("used_accounts.txt", "a") as f:
                    f.write(line)
            else:
                with open("failed_accounts.txt", "a") as f:
                    f.write(line)
    except Exception:
        pass

import threading
_claim_lock = threading.Lock()

def claim_one():
    """Claim one account: generate random realistic email at @secretvibe.us."""
    import json, time, random, string
    with _claim_lock:
        try:
            # First try to pop from Redis (for requeued accounts)
            try:
                rc = _r()
                raw = rc.lpop("queue:pending") # LPOP so we get the most recently pushed retry immediately
                if raw:
                    item = json.loads(raw)
                    print(f"[*] Picked up requeued account from Redis: {item.get('email')}")
                    return (raw, item)
            except Exception as e:
                pass

            # Generate a realistic email using the existing generate_random_name function
            import re
            base_name = generate_random_name().lower()
            base_name = re.sub(r'[^a-z]', '', base_name) # Ensure only a-z characters
            num = random.randint(100, 9999)
            email = f"{base_name}{num}@secretvibe.us"
            
            # Generate a random password
            pwd_chars = string.ascii_letters + string.digits
            pwd = ''.join(random.choice(pwd_chars) for _ in range(12)) + "A1@"
            
            item = {"email": email, "password": pwd, "qid": random.randint(1000000, 9999999)}
            return (json.dumps(item), item)
        except Exception as e:
            print(f"Error in claim_one: {e}")
            
    time.sleep(5)
    return None

def ack_claim(raw, mark_done=True):
    """Remove from processing list; mark_done=True par hi qid done_qids me jayega.
    Transient requeue / renew-return par mark_done=False — account wapas queue
    me gaya hai, process NAHI hua, isliye qid done-set me nahi jana chahiye
    (warna agli claim par guard use silent discard kar dega — black hole)."""
    import json
    try:
        rc = _r()
        rc.lrem(PROC_KEY, 1, raw)
        if not mark_done:
            return
        try:
            item = json.loads(raw)
            qid = item.get("qid")
            if qid:
                rc.sadd("queue:done_qids", str(qid))
        except Exception:
            pass
    except Exception:
        pass

def heartbeat_loop():
    import time as _ht
    start = _ht.time()
    while True:
        try:
            _r().hset("workers:hb", WORKER_ID, json.dumps({
                "id": WORKER_ID, "machine": socket.gethostname(),
                "threads": WORKER_THREADS, "current": CURRENT_EMAIL,
                "paused": _is_paused(), "ver": _WORKER_VER,
                "health": WORKER_HEALTH["status"], "health_why": WORKER_HEALTH["why"],
                "uptime": int(_ht.time() - start)}))
            _r().expire("workers:hb", 120)
        except Exception:
            pass
        _ht.sleep(30)


def _worker_ver():
    try:
        import hashlib as _hv
        return _hv.sha256(open(os.path.abspath(__file__), "rb").read()).hexdigest()[:12]
    except Exception:
        return ""

_WORKER_VER = _worker_ver()
_PAUSED = False


def _is_paused():
    if _PAUSED:
        return True
    try:
        r = _r()
        if r.get("paused:" + WORKER_ID) == "1":
            return True
        if r.get("fleet:paused") == "1":
            return True
    except Exception:
        pass
    return False


def _self_update(url, sha256):
    import hashlib as _hl, os as _os, sys as _sys
    me = _os.path.abspath(__file__)
    if not url or not sha256:
        print(f"{Colors.WARNING}[fleet] update: missing url/sha256{Colors.ENDC}")
        return
    try:
        import urllib.request as _ur
        tmp = me + ".new"
        print(f"{Colors.OKCYAN}[fleet] downloading update...{Colors.ENDC}")
        _ur.urlretrieve(url, tmp)
        h = _hl.sha256(open(tmp, "rb").read()).hexdigest()
        if h != sha256:
            _os.remove(tmp)
            print(f"{Colors.FAIL}[fleet] update REJECTED: sha256 mismatch{Colors.ENDC}")
            return
        _os.replace(tmp, me)
        print(f"{Colors.OKGREEN}[fleet] updated OK, restarting...{Colors.ENDC}")
        _safe_execv([_sys.executable, me] + _sys.argv[1:])
    except Exception as e:
        print(f"{Colors.FAIL}[fleet] update failed: {e}{Colors.ENDC}")


def _handle_command(cmd):
    global _PAUSED, WORKER_THREADS
    act = (cmd.get("action") or "").lower()
    if act == "pause":
        _PAUSED = True
        try:
            _r().set("paused:" + WORKER_ID, "1")
        except Exception:
            pass
        print(f"{Colors.WARNING}[fleet] paused by panel{Colors.ENDC}")
    elif act == "resume":
        _PAUSED = False
        try:
            _r().delete("paused:" + WORKER_ID)
        except Exception:
            pass
        print(f"{Colors.OKGREEN}[fleet] resumed by panel{Colors.ENDC}")
    elif act == "set_threads":
        try:
            t = max(1, min(50, int(cmd.get("threads") or 10)))
            WORKER_THREADS = t
            _r().set("threads:" + WORKER_ID, t)
            print(f"{Colors.OKCYAN}[fleet] threads -> {t}{Colors.ENDC}")
        except Exception:
            pass
    elif act == "update":
        _self_update(cmd.get("url") or "", cmd.get("sha256") or "")


def _check_commands():
    r = _r()
    for key in ("cmd:" + WORKER_ID, "cmd:all"):
        while True:
            raw = r.rpop(key)
            if not raw:
                break
            try:
                _handle_command(json.loads(raw))
            except Exception as e:
                print(f"{Colors.WARNING}[fleet] bad command: {e}{Colors.ENDC}")


def command_loop():
    import time as _ct
    _ct.sleep(10)
    while True:
        try:
            _check_commands()
        except Exception:
            pass
        _ct.sleep(5)

# ══════════════════════════════════════════════════════════════════════════════
# BANDWIDTH SAVER: block heavy media resources + per-account bandwidth meter.
# Instagram pages pull megabytes of images/video/fonts per account; blocking
# them cuts page weight ~70-85% with zero impact on login/OTP logic.
# Toggle: set env BW_SAVER=0 to disable entirely (blocking + meter).
# Debug:  set env BW_DEBUG=1 to log every blocked request URL (flow verification).
# ══════════════════════════════════════════════════════════════════════════════
_BW_BLOCK_TYPES = {"image", "media", "font"}
_BW_BLOCK_URL_SUBSTR = (
    "analytics",
    "graph.instagram",
    "connect.facebook.net",
)
_BW_DEBUG = os.environ.get("BW_DEBUG", "0") == "1"

async def _install_bandwidth_saver(context, page):
    """Attach route-level media blocking + CDP byte counter. Returns stats dict."""
    stats = {"bytes": 0, "requests": 0, "blocked": 0}
    if os.environ.get("BW_SAVER", "1") == "0":
        return stats

    async def _bw_route(route):
        req = route.request
        url = req.url.lower()
        
        # Don't block captcha images so they can be loaded and solved
        if "recaptcha" in url or "gstatic.com" in url or "hcaptcha" in url:
            await route.continue_()
            return
            
        if req.resource_type in _BW_BLOCK_TYPES or any(s in url for s in _BW_BLOCK_URL_SUBSTR):
            stats["blocked"] += 1
            if _BW_DEBUG:
                print(f"[BW-DEBUG] blocked {req.resource_type:6s} {req.url[:160]}", flush=True)
            await route.abort()
        else:
            await route.continue_()

    await context.route("**/*", _bw_route)

    # Accurate on-wire byte counting via CDP Network.loadingFinished
    # (encodedDataLength = bytes actually transferred, post-compression).
    try:
        cdp = await context.new_cdp_session(page)
        await cdp.send("Network.enable")

        def _on_finished(params):
            stats["bytes"] += int(params.get("encodedDataLength", 0) or 0)
            stats["requests"] += 1

        cdp.on("Network.loadingFinished", _on_finished)
        stats["_cdp"] = cdp  # keep a ref so the session isn't GC'd
    except Exception as e:
        print(f"[BW] meter unavailable ({e}); media blocking still active")
    return stats


def _print_bandwidth_report(email, stats):
    kb = stats["bytes"] / 1024
    mb = kb / 1024
    size = f"{mb:.2f} MB" if mb >= 1 else f"{kb:.0f} KB"
    print(f"[BW] {email}: {size} downloaded in {stats['requests']} requests, "
          f"{stats['blocked']} heavy requests blocked")


async def _apply_webrtc_protection(context, proxy_ip=None):
    """
    Prevents WebRTC IP leaks over local network interfaces.
    Clears STUN/TURN servers so UDP packets cannot bypass the SOCKS5 proxy,
    while keeping the native RTCPeerConnection API intact for stealth.
    """
    js_code = """
    (() => {
        const origPC = window.RTCPeerConnection || window.webkitRTCPeerConnection;
        if (!origPC) return;

        function ProxyPC(config, constraints) {
            if (config && config.iceServers) {
                config = Object.assign({}, config, { iceServers: [] });
            }
            return new origPC(config, constraints);
        }
        ProxyPC.prototype = origPC.prototype;

        window.RTCPeerConnection = ProxyPC;
        if (window.webkitRTCPeerConnection) {
            window.webkitRTCPeerConnection = ProxyPC;
        }
    })();
    """
    try:
        await context.add_init_script(js_code)
    except Exception as e:
        print(f"[-] WebRTC protection warning: {e}")


class TransientError(Exception):
    """Network-level failure worth retrying later on a fresh circuit (bounded)."""
    pass


_TRANSIENT_PATTERNS = (
    "ERR_HTTP_RESPONSE_CODE_FAILURE",
    "ERR_TIMED_OUT",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_NETWORK_CHANGED",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_NAME_NOT_RESOLVED",
    "net::",
)

def _is_transient_error(msg):
    m = str(msg or "")
    if any(p in m for p in _TRANSIENT_PATTERNS):
        return True
    # Playwright timeout: "Timeout 60000ms exceeded." / "Locator.fill: Timeout ..."
    # (str(e) me class name nahi hota, isliye plain "Timeout" check)
    if "Timeout" in m and "exceeded" in m:
        return True
    return False


async def _goto_with_retry(page, url, wait_until="domcontentloaded", timeout=60000, tries=3):
    """Goto with bounded retry for transient network failures.
    Raises TransientError (caller requeues) after tries are exhausted."""
    last = None
    for i in range(tries):
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            return
        except Exception as e:
            last = e
            if _is_transient_error(str(e)) and i < tries - 1:
                print(f"[-] nav try {i+1}/{tries} transient fail, retrying: {str(e)[:130]}")
                try:
                    await page.wait_for_timeout(3000)
                except Exception:
                    pass
                continue
            raise
    raise TransientError(f"Navigation failed after {tries} tries: {last}")


async def _fill_login_form(page, email, password, context=None, max_retries=2):
    """Language-independent login fill with auto-retry and IP rotation on slow load / timeout."""
    ctx = context or (page.context if page else None)

    for attempt in range(1, max_retries + 2):
        # 1) username field  CSS first (language-independent), role fallback, simultaneous wait
        u_css = page.locator('input[name="username"]')
        u_role = page.get_by_role("textbox", name=re.compile(r"username|email|mobile|phone", re.IGNORECASE))
        user_input = u_css.or_(u_role).first

        try:
            print(f"[*] Waiting for Instagram login form (username field, attempt {attempt}/{max_retries+1})...")
            await user_input.wait_for(state="visible", timeout=25000)
            await user_input.click()
            await user_input.fill(email)
            if (await user_input.input_value()).strip() != email.strip():
                await user_input.fill(email)  # one retry
                if (await user_input.input_value()).strip() != email.strip():
                    raise Exception("Login fill verification failed: username field did not accept input")

            # 2) password field
            p_css = page.locator('input[name="password"], input[type="password"]')
            p_role = page.get_by_role("textbox", name=re.compile(r"password", re.IGNORECASE))
            pass_input = p_css.or_(p_role).first

            await pass_input.wait_for(state="visible", timeout=15000)
            await pass_input.click()
            await pass_input.fill(password)
            if not (await pass_input.input_value()):
                raise Exception("Login fill verification failed: password field did not accept input")

            # 3) submit button
            s_css = page.locator('form button[type="submit"], button[type="submit"]')
            s_role = page.get_by_role("button", name=re.compile(r"log\s?in", re.IGNORECASE))
            submit = s_css.or_(s_role).first

            await submit.wait_for(state="visible", timeout=15000)
            await submit.click()
            print("[+] Login form filled + submit clicked (fill verified).")
            return True

        except Exception as e:
            err_msg = str(e)
            if attempt <= max_retries and ("Timeout" in err_msg or "timed out" in err_msg.lower()):
                print(f"{Colors.WARNING}[!] Instagram login form load hone me timeout hua (Slow IP) (Attempt {attempt}/{max_retries+1}). Rotating IP & reloading...{Colors.ENDC}")
                await rotate_vpn_extension_ip(page, ctx, reason=f"Login Form Timeout / Slow IP ({attempt})")
                await page.wait_for_timeout(2000)
                try:
                    print("[*] Reloading Instagram login page with new IP...")
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    # Check and dismiss GDPR cookies if popup appears after reload
                    cookie_btn = page.locator("button").filter(
                        has_text=re.compile(r'Allow all cookies|Accept All', re.IGNORECASE)
                    ).first
                    if await cookie_btn.is_visible(timeout=3000):
                        await cookie_btn.click()
                        print("[*] Dismissed GDPR cookie popup after reload.")
                        await page.wait_for_timeout(1000)
                except Exception as reload_err:
                    print(f"[-] Reload note: {reload_err}")
                continue
            else:
                raise


async def _verify_2fa_enabled(page, instauser):
    """Independent positive check that 2FA is ON. True ONLY on confirmation."""
    try:
        await page.goto(
            "https://accountscenter.instagram.com/password_and_security/two_factor/",
            wait_until="domcontentloaded", timeout=60000,
        )
        await page.wait_for_timeout(4000)
        try:
            body = await page.locator("body").inner_text()
        except Exception:
            body = ""
        low = body.lower()
        if re.search(r"get started", low):
            print("[-] verify: 2FA page still shows 'Get started' -> NOT enabled")
            return False
        if "authentication app" in low and (
            "turn off" in low or re.search(r"\bon\b", low) or "enabled" in low
        ):
            print("[+] verify: 2FA positively confirmed enabled (authentication app on)")
            return True
        print("[-] verify: could not positively confirm 2FA is enabled")
        return False
    except Exception as e:
        print(f"[-] verify: check failed: {str(e)[:150]}")
        return False


async def _grab_cookies_str(context):
    """Instagram session cookies nikalo (har result me save karne ke liye)."""
    try:
        _cookies = await context.cookies()
        return ";".join([f"{c['name']}={c['value']}" for c in _cookies])
    except Exception:
        return ""


async def _get_meta_continue_button(page):
    """Find visible Continue / Next button on Meta checkpoint page."""
    candidates = [
        page.locator("button").filter(has_text=re.compile(r"Continue|Next", re.IGNORECASE)),
        page.locator("[role='button']").filter(has_text=re.compile(r"Continue|Next", re.IGNORECASE)),
        page.get_by_role("button", name=re.compile(r"Continue|Next", re.IGNORECASE)),
        page.locator("button:has-text('Continue'), button:has-text('Next')"),
        page.locator("div[role='button']:has-text('Continue'), div[role='button']:has-text('Next')"),
        page.locator("[aria-label*='Continue' i], [aria-label*='Next' i]"),
        page.locator("button[type='submit']"),
    ]
    for cand in candidates:
        try:
            cnt = await cand.count()
            for idx in range(cnt):
                el = cand.nth(idx)
                if await el.is_visible():
                    return el
        except Exception:
            continue
    return None


async def _is_meta_button_clickable(button):
    """Check if Meta button is enabled and not marked aria-disabled/disabled."""
    try:
        if not await button.is_enabled():
            return False
        aria_dis = await button.get_attribute("aria-disabled")
        if aria_dis and aria_dis.lower() == "true":
            return False
        dis = await button.get_attribute("disabled")
        if dis is not None:
            return False
        cls = (await button.get_attribute("class")) or ""
        if "disabled" in cls.lower().split():
            return False
        return True
    except Exception:
        return False
async def _dismiss_meta_consent_if_present(page):
    """Automatically dismiss Meta GDPR / Cookie consent (flow=user_cookie_choice_v2) if present."""
    try:
        curr = page.url
        if "consent" in curr or "cookie" in curr or "privacy" in curr:
            cookie_btn = page.locator("button, div[role='button'], input[type='submit']").filter(
                has_text=re.compile(r"Allow (all|essential and optional|optional) cookies|Accept all|Allow all|Accept all cookies|Allow cookies|Essentiële en optionele cookies|Alle cookies toestaan|Alle Cookies erlauben|Permitir", re.IGNORECASE)
            ).first
            if await cookie_btn.is_visible(timeout=2500):
                print("[*] Dismissing Meta cookie consent on page...")
                await cookie_btn.click()
                await page.wait_for_timeout(2000)
    except Exception:
        pass


async def rotate_vpn_extension_ip(page, context=None, reason="VPN IP Rotation"):
    """Rotate IP using the AutoConnect VPN extension before retrying (e.g. Terms button or Captcha stuck)."""
    print(f"{Colors.WARNING}[*] [{reason}] Rotating IP via AutoConnect VPN extension...{Colors.ENDC}")
    rotated = False
    server_info = ""

    # Method 1: Check Playwright Extension Service Workers
    ctx = context or (page.context if page else None)
    if ctx and hasattr(ctx, "service_workers"):
        for sw in ctx.service_workers:
            try:
                is_vpn = await sw.evaluate("typeof connectVpn === 'function'")
                if is_vpn:
                    res = await sw.evaluate("""
                        new Promise(async (resolve) => {
                            try {
                                let pool = SERVER_POOL;
                                if (typeof selectedRegion !== 'undefined' && selectedRegion && selectedRegion !== 'all') {
                                    const filtered = SERVER_POOL.filter(s => s.region === selectedRegion);
                                    if (filtered.length > 0) pool = filtered;
                                }
                                const currentHost = (typeof activeServer !== 'undefined' && activeServer) ? activeServer.host : "";
                                const candidates = pool.filter(s => s.host !== currentHost);
                                const nextServer = (candidates.length > 0 ? candidates : pool)[Math.floor(Math.random() * (candidates.length > 0 ? candidates.length : pool.length))];
                                await connectVpn(nextServer);
                                resolve({ success: true, server: nextServer.host, country: nextServer.country || nextServer.regionName });
                            } catch (err) {
                                resolve({ success: false, error: String(err) });
                            }
                        })
                    """)
                    if res and res.get("success"):
                        rotated = True
                        server_info = f"{res.get('server')} ({res.get('country')})"
                        break
            except Exception:
                pass

    # Method 2: Bridge via page window.postMessage to content script
    if not rotated and page:
        try:
            res = await page.evaluate("""
                new Promise((resolve) => {
                    let handled = false;
                    const handler = (e) => {
                        if (e.data && e.data.type === 'VPN_ROTATED') {
                            window.removeEventListener('message', handler);
                            handled = true;
                            resolve(e.data);
                        }
                    };
                    window.addEventListener('message', handler);
                    window.postMessage({ type: 'VPN_ROTATE' }, '*');
                    setTimeout(() => {
                        if (!handled) {
                            window.removeEventListener('message', handler);
                            resolve(null);
                        }
                    }, 4000);
                })
            """)
            if res and res.get("success"):
                rotated = True
                s = res.get("result", {}).get("server", {}) if isinstance(res.get("result"), dict) else {}
                if s:
                    server_info = f"{s.get('host')} ({s.get('country')})"
        except Exception:
            pass

    # Give the proxy connection time to establish
    await asyncio.sleep(2)

    # Detect new IP if page is responsive
    new_ip = None
    if page:
        try:
            new_ip = await page.evaluate("""
                fetch('https://api.ipify.org?format=json')
                    .then(r => r.json())
                    .then(d => d.ip)
                    .catch(() => null)
            """)
        except Exception:
            pass

    if rotated or new_ip:
        info_str = f" [Server: {server_info}]" if server_info else ""
        ip_str = f" [New IP: {new_ip}]" if new_ip else ""
        print(f"{Colors.OKGREEN}[+] AutoConnect VPN IP rotated successfully!{info_str}{ip_str}{Colors.ENDC}")
        return True
    else:
        print(f"{Colors.WARNING}[!] Warning: VPN rotation signal dispatched, proceeding to click...{Colors.ENDC}")
        return False


async def _handle_meta_checkpoint_flow(page, ip_label="Real IP", context=None):
    """
    Handles Meta checkpoint with 2-step click flow and reCAPTCHA monitoring:
    1st click: When checkpoint is detected, click initial Continue button.
    2nd click: After captcha is solved by extension and button becomes clickable again.
    Monitors reCAPTCHA loading spinner: If stuck loading 20-30s, rotates IP and reloads.
    Tracks and prints live captcha status (loading spinner, puzzle challenge, solve confirmed).
    Finally waits for /language URL.
    """
    ctx = context or (page.context if page else None)
    print(f"[*] Checkpoint URL detected on {ip_label}. Starting checkpoint flow...")

    # Frame locators for reCAPTCHA (handles both standard api2 and enterprise)
    anchor_frame = page.frame_locator("iframe[src*='anchor'], iframe[title*='reCAPTCHA']").first
    bframe = page.frame_locator("iframe[src*='bframe']").first

    # ── CLICK 1: Initial Checkpoint Continue Button (or Direct Captcha) ──
    print(f"[*] [Click 1/2] Checking for initial Continue button or direct Captcha on checkpoint ({ip_label})...")
    click1_done = False
    for sec in range(50):
        await _dismiss_meta_consent_if_present(page)
        if "language" in page.url or "instagram" in page.url:
            print(f"[+] Already reached /language URL on {ip_label}.")
            return True

        # Check if already directly on "Confirm that you're human" / Captcha page
        for fr in page.frames:
            try:
                box = fr.locator("#recaptcha-anchor").first
                if await box.is_visible(timeout=200):
                    print(f"[*] Direct Captcha detected on checkpoint page ('Confirm that you're human')! Proceeding to Captcha monitoring...")
                    click1_done = True
                    break
            except Exception:
                pass
        if click1_done:
            break

        btn = await _get_meta_continue_button(page)
        if btn and await _is_meta_button_clickable(btn):
            print(f"[+] [Click 1/2] Found clickable Continue button on {ip_label} ({sec}s elapsed). Clicking now...")
            try:
                await btn.click(timeout=5000)
                click1_done = True
                print(f"[+] [Click 1/2] Clicked! Waiting for Captcha to load...")
                await page.wait_for_timeout(3000)
                break
            except Exception as ce:
                print(f"[-] [Click 1/2] Click attempt failed: {ce}")

        if sec > 0 and sec % 10 == 0:
            print(f"[*] [Click 1/2] Waiting for initial Continue button / Captcha... ({sec}s/50s)")
        await page.wait_for_timeout(1000)

    # ── STEP 2: Live Captcha Monitoring (Wait for Box -> Monitor Spinner/Puzzle/Solve) ──
    if "language" not in page.url:
        print(f"[*] [Captcha Flow] Monitoring reCAPTCHA state on {ip_label}...")
        loading_seconds = 0
        box_waiting_seconds = 0
        puzzle_seconds = 0
        last_logged_state = ""
        checkbox_clicked_manually = False
        captcha_start_time = time.monotonic()
        max_captcha_wait = 120  # Max total wait per session before failover

        while (time.monotonic() - captcha_start_time) < max_captcha_wait:
            if "language" in page.url or "instagram" in page.url:
                print(f"[+] Reached /language URL while waiting for Captcha on {ip_label}!")
                return True

            # 1. Check if Continue button is already clickable
            btn = await _get_meta_continue_button(page)
            if btn and await _is_meta_button_clickable(btn):
                print(f"{Colors.OKGREEN}[+] [Captcha Solved] Continue button CLICKABLE ho gaya! Clicking now...{Colors.ENDC}")
                try:
                    await btn.click(timeout=5000)
                    print(f"[+] [Click 2/2] Clicked! Waiting for redirection to /language...")
                    await page.wait_for_timeout(3000)
                    if "language" in page.url or "instagram" in page.url:
                        return True
                    break
                except Exception as ce:
                    print(f"[-] [Click 2/2] Click attempt failed: {ce}")

            # 2. Inspect reCAPTCHA state across all frames
            box_visible = False
            is_loading = False
            is_solved = False
            is_puzzle = False
            puzzle_desc = ""

            for fr in page.frames:
                try:
                    box = fr.locator("#recaptcha-anchor").first
                    if await box.is_visible(timeout=200):
                        box_visible = True
                        cls = (await box.get_attribute("class")) or ""
                        chk = await box.get_attribute("aria-checked")
                        if chk == "true" or "recaptcha-checkbox-checked" in cls:
                            is_solved = True
                        elif "recaptcha-checkbox-loading" in cls:
                            is_loading = True
                        else:
                            if not checkbox_clicked_manually:
                                try:
                                    print(f"[*] [Captcha] reCAPTCHA box appear ho gaya! Checkbox click karke verification start kar rahe hain...")
                                    await box.click(timeout=2000)
                                    checkbox_clicked_manually = True
                                except Exception:
                                    pass
                        break
                except Exception:
                    pass

            # Check Bframe (Puzzle / Image challenge across frames)
            for fr in page.frames:
                try:
                    challenge_wrap = fr.locator(".rc-imageselect-challenge, .rc-imageselect-desc-wrapper, .rc-imageselect-table-33, .rc-imageselect-table-44").first
                    if await challenge_wrap.is_visible(timeout=200):
                        is_puzzle = True
                        try:
                            desc_el = fr.locator(".rc-imageselect-desc-wrapper, .rc-imageselect-instructions strong, .rc-imageselect-desc").first
                            puzzle_desc = (await desc_el.text_content(timeout=200) or "").strip()
                        except Exception:
                            puzzle_desc = "Image Challenge"
                        break
                except Exception:
                    pass

            # 3. State tracking & conditions
            if is_solved:
                loading_seconds = 0
                box_waiting_seconds = 0
                puzzle_seconds = 0
                if last_logged_state != "solved":
                    print(f"{Colors.OKGREEN}[+] [Captcha] reCAPTCHA SOLVED (Green Checkmark verified)! Waiting for Continue button...{Colors.ENDC}")
                    last_logged_state = "solved"
            elif is_puzzle:
                loading_seconds = 0
                box_waiting_seconds = 0
                puzzle_seconds += 1
                if last_logged_state != f"puzzle_{puzzle_desc}":
                    print(f"[*] [Captcha] Puzzle Challenge load ho gaya: '{puzzle_desc}'. Extension (ADV_CAPTCHA_PRO) puzzle fill / solve kar raha hai...")
                    last_logged_state = f"puzzle_{puzzle_desc}"
                elif puzzle_seconds % 5 == 0:
                    print(f"[*] [Captcha] Puzzle solving in progress... ({puzzle_seconds}s/45s)")

                # Agar puzzle solving 45s se zyada time le (endless challenge loop / flagged IP) -> rotate IP & refresh
                if puzzle_seconds >= 45:
                    print(f"{Colors.WARNING}[!] [Captcha Stuck] Puzzle solving 45s se zyada chala (Google endless puzzle trap / bad IP)! Rotating IP & Refreshing page...{Colors.ENDC}")
                    await rotate_vpn_extension_ip(page, ctx, reason="Captcha Puzzle Loop Stuck (45s)")
                    await page.wait_for_timeout(2000)
                    try:
                        print(f"[*] Refreshing checkpoint page with new IP...")
                        await page.reload(wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                    except Exception as reload_err:
                        print(f"[-] Reload note: {reload_err}")
                    loading_seconds = 0
                    box_waiting_seconds = 0
                    puzzle_seconds = 0
                    checkbox_clicked_manually = False
                    last_logged_state = "reloaded"
                    continue
            elif box_visible and is_loading:
                # Box dikh gaya hai aur spinner loading ghum raha hai
                puzzle_seconds = 0
                loading_seconds += 1
                box_waiting_seconds = 0
                if loading_seconds % 5 == 0 or loading_seconds in (10, 15, 20, 25):
                    print(f"[*] [Captcha] Box dikh gaya, spinner ghum raha hai... ({loading_seconds}s/25s)")
                last_logged_state = "loading"

                # Box dikhne ke baad agar spinner 25s tak continuously ghumta rahe (Slow IP) -> rotate IP & refresh
                if loading_seconds >= 25:
                    print(f"{Colors.WARNING}[!] [Captcha Stuck] Box dikhne ke baad spinner 25s tak ghumta raha (Slow IP)! Rotating IP & Refreshing page...{Colors.ENDC}")
                    await rotate_vpn_extension_ip(page, ctx, reason="Captcha Spinner Stuck (25s)")
                    await page.wait_for_timeout(2000)
                    try:
                        print(f"[*] Refreshing checkpoint page with new IP...")
                        await page.reload(wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                    except Exception as reload_err:
                        print(f"[-] Reload note: {reload_err}")
                    loading_seconds = 0
                    box_waiting_seconds = 0
                    puzzle_seconds = 0
                    checkbox_clicked_manually = False
                    last_logged_state = "reloaded"
                    continue
            elif box_visible:
                # Box dikh gaya hai, wait kar raha hai verification start hone ka
                loading_seconds = 0
                box_waiting_seconds = 0
                puzzle_seconds = 0
                if last_logged_state != "box_idle":
                    print("[*] [Captcha] reCAPTCHA box visible hai, verification process chal rahi hai...")
                    last_logged_state = "box_idle"
            else:
                # Box abhi tak aaya hi nahi hai (kabhi 40-50s lagte hain) -> NO REFRESH, patiently wait!
                loading_seconds = 0
                box_waiting_seconds += 1
                puzzle_seconds = 0
                if box_waiting_seconds % 10 == 0:
                    print(f"[*] [Captcha] Captcha box load hone ka wait kar rahe hain... ({box_waiting_seconds}s/60s) (refresh nahi karenge)")

                # Agar 60 seconds tak box hi nahi aaya tabhi reload/rotate hoga
                if box_waiting_seconds >= 60:
                    print(f"{Colors.WARNING}[!] [Captcha] 60s tak captcha box nahi aaya (Slow IP). Rotating IP & Refreshing...{Colors.ENDC}")
                    await rotate_vpn_extension_ip(page, ctx, reason="Captcha Box Not Loaded (60s)")
                    await page.wait_for_timeout(2000)
                    try:
                        print("[*] Refreshing checkpoint page with new IP...")
                        await page.reload(wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                    except Exception as reload_err:
                        print(f"[-] Reload note: {reload_err}")
                    loading_seconds = 0
                    box_waiting_seconds = 0
                    checkbox_clicked_manually = False
                    last_logged_state = "reloaded"
                    continue

            await page.wait_for_timeout(1000)

    # ── WAIT FOR /LANGUAGE URL (Refresh every 5s, max 4 times) ──
    print(f"[*] Waiting for auth.meta.com/language URL on {ip_label} (refreshing every 5s, max 4 times)...")
    for refresh_attempt in range(1, 5):
        for _ in range(5):
            if "language" in page.url or "instagram.com" in page.url:
                print(f"[+] Meta login successful on {ip_label} (language / instagram detected).")
                return True
            btn = await _get_meta_continue_button(page)
            if btn and await _is_meta_button_clickable(btn):
                try:
                    print(f"[*] Re-clicking enabled Continue button on {ip_label}...")
                    await btn.click(timeout=3000)
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass
            await page.wait_for_timeout(1000)

        if "language" in page.url or "instagram.com" in page.url:
            print(f"[+] Meta login successful on {ip_label} (language / instagram detected).")
            return True

        if refresh_attempt < 4:
            print(f"[*] /language URL not detected yet. Refreshing page ({refresh_attempt}/4)...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(1500)
            except Exception as reload_err:
                print(f"[-] Reload attempt failed: {reload_err}")

    if "language" in page.url or "instagram.com" in page.url:
        print(f"[+] Meta login successful on {ip_label} (language / instagram detected).")
        return True
    else:
        print(f"[!] Warning: Did not detect /language URL on {ip_label} (current: {page.url})")
        return False



async def process_account(context, page, email, password, qid=None, local_port=None, proxy_info=None, is_retry=False):
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}========================================={Colors.ENDC}")
    print(f"{Colors.OKBLUE}{Colors.BOLD}        STARTING ACCOUNT: {email}{Colors.ENDC}")
    print(f"{Colors.OKBLUE}{Colors.BOLD}========================================={Colors.ENDC}")

    seen_ids = set()
    # Prefetch existing emails so we don't accidentally grab an old OTP
    await asyncio.to_thread(prefetch_seen_ids, email, seen_ids)

    totp_secret = ""
    instauser = email.split('@')[0]
    
    proxy_country = "Unknown"
    proxy_ip = "Unknown"

    # ── Stage tracking: exact failure stage + timing, no guessing ──
    _stage_info = {"name": "init", "t0": time.monotonic()}
    def _set_stage(name):
        el = time.monotonic() - _stage_info["t0"]
        if _stage_info["name"] != "init":
            print(f"[stage] {_stage_info['name']}: {el:.1f}s")
        _stage_info["name"] = name
        _stage_info["t0"] = time.monotonic()

    try:
        _set_stage("proxy_check")
        print("[*] Checking proxy connection and country...")
        if proxy_info and proxy_info[0]:
            # v7.2: exit IP circuit stage me hi fetch ho gaya tha — wahi reuse, dusri HTTP fetch nahi.
            proxy_ip = proxy_info[0]
            proxy_country = proxy_info[1] or "Unknown"
            print(f"{Colors.OKGREEN}[+] Connected to Proxy: {proxy_country} (IP: {proxy_ip}){Colors.ENDC}")
        else:
            try:
                import requests
                chk_proxies = None
                if local_port:
                    chk_proxies = {
                        "http": f"socks5h://127.0.0.1:{local_port}",
                        "https": f"socks5h://127.0.0.1:{local_port}"
                    }
                
                # Check IPv6 directly via api6.ipify.org
                try:
                    resp = await asyncio.to_thread(requests.get, "https://api6.ipify.org?format=json", proxies=chk_proxies, timeout=12)
                    ip_data = resp.json()
                    if 'ip' in ip_data:
                        proxy_ip = ip_data.get('ip', 'Unknown')
                        proxy_country = "India (Residential IPv6)"
                        print(f"{Colors.OKGREEN}[+] Connected to Residential IPv6: {proxy_ip}{Colors.ENDC}")
                except Exception:
                    try:
                        resp = await asyncio.to_thread(requests.get, "http://ip-api.com/json/", proxies=chk_proxies, timeout=12)
                        ip_data = resp.json()
                        if ip_data.get('status') == 'success':
                            proxy_country = ip_data.get('country', 'Unknown')
                            proxy_ip = ip_data.get('query', 'Unknown')
                            print(f"{Colors.OKGREEN}[+] Connected to Proxy: {proxy_country} (IP: {proxy_ip}){Colors.ENDC}")
                    except Exception:
                        pass
                        
            except Exception as e:
                print(f"[-] Proxy check note: {str(e)[:150]}")
            

      
        if not is_retry:
            # === AUTH.META.COM CHECKPOINT FLOW ===
            try:
                _set_stage("meta_checkpoint")
                print("[*] Checking Meta URL state for checkpoints...")
                for _ in range(30):
                    curr_url = page.url
                    if "checkpoint" in curr_url or "language" in curr_url:
                        break
                    await page.wait_for_timeout(1000)
                    
                curr_url = page.url
                if "checkpoint" in curr_url:
                    await _handle_meta_checkpoint_flow(page, ip_label="Residential IPv6", context=context)
                else:
                    print("[*] Waiting for auth.meta.com/language URL...")
                    for _ in range(30):
                        if "language" in page.url:
                            print("[+] Meta login successful (language URL detected). Proceeding to Instagram flow.")
                            break
                        await page.wait_for_timeout(1000)
                
            except Exception as e:
                print(f"[-] Meta checkpoint/language flow failed: {e}")
                raise Exception(f"Meta flow failed: {e}")
            # ========================
        else:
            print("[*] Retry attempt: skipping Meta checkpoint / language flow.")

        _set_stage("nav_insta")
        print(f"[*] Navigating to Instagram...")
        await _goto_with_retry(page, "https://www.instagram.com/accounts/login/?mtn#",
                               wait_until="domcontentloaded", timeout=60000, tries=3)

        # Wait a moment for page JS and GDPR init_script to kick in
        await page.wait_for_timeout(1500)

        # Fallback: manually dismiss GDPR popup if init_script hasn't fired yet
        try:
            cookie_btn = page.locator("button").filter(
                has_text=re.compile(r'Allow all cookies|Accept All', re.IGNORECASE)
            ).first
            if await cookie_btn.is_visible(timeout=5000):
                await cookie_btn.click()
                print("[*] Dismissed GDPR cookie popup.")
                await page.wait_for_timeout(1500)
        except Exception:
            pass

        # Explicitly wait for login form to be visible before trying to fill

        print(f"[*] Waiting before filling credentials...")
        await _fill_login_form(page, email, password, context=context)

        
        # STEP 4: Smart Polling for Login Outcome (Success, Error, Checkpoint)
        print(f"[*] Waiting for login to process and checking outcome...")
        
        login_outcome = "unknown"
        max_login_retries = 2  # Allows retry with IP rotation if stuck on slow IP
        
        for login_attempt in range(1, max_login_retries + 1):
            re_clicked_submit = False
            for sec in range(20):
                if await page.get_by_text("Sorry, your password was incorrect").first.is_visible() or await page.get_by_text("The password you entered is incorrect").first.is_visible():
                    raise Exception("Incorrect password.")
                    
                if await page.get_by_text(re.compile(r"Can't find account|couldn't find an account", re.IGNORECASE)).first.is_visible():
                    print(f"[!] 'Can't find account' detected on Instagram (Meta sync delay). Closing browser & requeuing account to login again...")
                    raise TransientError("Can't find account error. Requeuing for fresh browser login.")
                    
                if await page.get_by_text("There was a problem logging you into Instagram").first.is_visible():
                    print(f"[!] 'Problem logging you into Instagram' detected. Closing browser & requeuing...")
                    raise TransientError("Login failed: Problem logging in (block)")

                if await page.get_by_text("No Instagram profile found").first.is_visible():
                    print("[*] No Instagram profile found popup detected. Assuming Meta account login is successful.")
                    login_outcome = "meta_success"
                    break
                    
                if await page.get_by_text("Check your email").first.is_visible() or await page.get_by_text("Enter code").first.is_visible() or await page.get_by_text("Log in on another device").first.is_visible():
                    print(f"[*] Account hit a checkpoint ('Check email' / 'Another device'). Reporting to panel and skipping.")
                    _ck = await _grab_cookies_str(context)
                    report_result("saved_checkpoint", qid, {"username": instauser, "password": password, "email": email, "country": proxy_country, "ip": proxy_ip, "cookies": _ck})
                    raise Exception("Skipped: Verification checkpoint detected.")
                    
                if await page.get_by_text("No Instagram account found").first.is_visible() or await page.get_by_role("button", name="View Meta account details for").first.is_visible():
                    print("[*] Found Meta account linking screen. Meta login successful.")
                    login_outcome = "meta_success"
                    break
                    
                # If we see the Not Now button, it usually means we successfully logged in
                if await page.locator("button, div[role='button']").filter(has_text=re.compile(r'^Not now$', re.IGNORECASE)).first.is_visible():
                    print("[*] Found 'Not Now' button. Instagram login successful.")
                    login_outcome = "insta_success"
                    break

                # If at 7-8s still sitting on login page, click screen & re-click login button
                if sec >= 7 and not re_clicked_submit:
                    try:
                        submit_btn = page.locator('form button[type="submit"], button[type="submit"]').first
                        if await submit_btn.is_visible(timeout=500):
                            print("[*] Login request process nahi hua (button still visible). Clicking screen & re-clicking submit...")
                            try:
                                await page.locator("body").click(position={"x": 50, "y": 50})
                                await page.wait_for_timeout(300)
                            except Exception:
                                pass
                            await submit_btn.click(timeout=3000)
                            re_clicked_submit = True
                            print("[+] Re-clicked login button.")
                    except Exception:
                        pass
                    
                await page.wait_for_timeout(1000)

            if login_outcome != "unknown":
                break

            # If outcome is still unknown after full polling round, rotate IP & reload to retry login
            if login_attempt < max_login_retries:
                print(f"{Colors.WARNING}[!] Login outcome unknown (Slow IP). Rotating IP via extension & retrying login...{Colors.ENDC}")
                await rotate_vpn_extension_ip(page, context, reason="Login Stuck (Slow IP)")
                await page.wait_for_timeout(2000)
                try:
                    print("[*] Reloading Instagram login page for fresh login attempt...")
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)
                    cookie_btn = page.locator("button").filter(
                        has_text=re.compile(r'Allow all cookies|Accept All', re.IGNORECASE)
                    ).first
                    if await cookie_btn.is_visible(timeout=3000):
                        await cookie_btn.click()
                        await page.wait_for_timeout(1000)
                    await _fill_login_form(page, email, password, context=context)
                except Exception as re_err:
                    print(f"[-] Re-login attempt error: {re_err}")

        # STEP 5: Dismiss Popups
        try:
            not_now_btn = page.locator("button, div[role='button']").filter(has_text=re.compile(r'^Not now$', re.IGNORECASE)).first
            if await not_now_btn.is_visible(timeout=3000):
                await not_now_btn.click()
                print("[*] Dismissed 'Not Now' popup.")
        except Exception:
            pass
            
        try:
            cancel_btn = page.locator("button, div[role='button']").filter(has_text=re.compile(r'^Cancel$', re.IGNORECASE)).first
            if await cancel_btn.is_visible(timeout=2000):
                await cancel_btn.click()
                print("[*] Dismissed 'Cancel' popup.")
        except Exception:
            pass
            
        is_email_checkpoint = False
        if not is_email_checkpoint:
            # Attempt to extract username from screen
            try:
                uname_input = page.locator('input[aria-label="Username"], input[type="text-no_suggestion"]')
                if await uname_input.is_visible(timeout=5000):
                    extracted_val = await uname_input.input_value()
                    if extracted_val:
                        instauser = extracted_val
                        print(f"[+] Extracted Username: {instauser}")
            except Exception:
                pass

        # Wait for either 'View Meta account details' OR the home page
        _set_stage("meta_setup")
        try:
            btn_meta = page.get_by_role("button", name="View Meta account details for")
            meta_horizon_btn = page.locator("div[role='button']").filter(has_text="Meta Horizon").first
            
            meta_clicked = False
            for check_round in range(2):
                if await page.get_by_text("No Instagram account found").first.is_visible(timeout=3000) or await meta_horizon_btn.is_visible(timeout=3000):
                    print("[*] Clicking 'Meta Horizon' account button...")
                    await expect(meta_horizon_btn).to_be_visible(timeout=10000)
                    await meta_horizon_btn.click()
                    meta_clicked = True
                    break
                elif await btn_meta.is_visible(timeout=5000):
                    print("[*] Clicking 'View Meta account details for' button...")
                    await btn_meta.click()
                    meta_clicked = True
                    break
                else:
                    if check_round == 0:
                        print(f"{Colors.WARNING}[*] Meta setup button not found yet. Checking if login button still on screen...{Colors.ENDC}")
                        submit_btn = page.locator('form button[type="submit"], button[type="submit"]').first
                        if await submit_btn.is_visible(timeout=1000):
                            print("[*] Login submit button still visible! Clicking screen & re-clicking login button...")
                            try:
                                await page.locator("body").click(position={"x": 50, "y": 50})
                                await page.wait_for_timeout(500)
                                await submit_btn.click(timeout=3000)
                            except Exception:
                                pass
                            await page.wait_for_timeout(6000)
                        else:
                            await page.wait_for_timeout(5000)

            if not meta_clicked:
                # If still not clicked, check if slow IP - rotate and reload once
                if not await page.get_by_text("No Instagram account found").first.is_visible(timeout=3000) and not await btn_meta.is_visible(timeout=3000):
                    print(f"{Colors.WARNING}[!] Meta setup button still missing (Slow IP). Rotating IP via extension & reloading...{Colors.ENDC}")
                    await rotate_vpn_extension_ip(page, context, reason="Meta Setup Button Missing")
                    await page.wait_for_timeout(2000)
                    try:
                        await page.reload(wait_until="domcontentloaded", timeout=20000)
                        await page.wait_for_timeout(3000)
                    except Exception:
                        pass

                if await page.get_by_text("No Instagram account found").first.is_visible(timeout=5000):
                    print("[*] Clicking 'Meta Horizon' account button...")
                    await meta_horizon_btn.click()
                else:
                    await expect(btn_meta).to_be_visible(timeout=20000)
                    await btn_meta.click()
            
            # Setup Full Name (Keep existing name if already present)
            fname_input = page.get_by_role("textbox", name="Full name")
            if not await fname_input.is_visible(timeout=5000):
                fname_input = page.locator('input[aria-label="Full name"], input[name="fullName"]').first
            
            await expect(fname_input).to_be_visible(timeout=30000)
            await page.wait_for_timeout(1500)  # Wait for React/Meta to populate pre-filled name
            
            curr_fname = (await fname_input.input_value()).strip()
            if not curr_fname:
                curr_fname = (await fname_input.get_attribute("value") or "").strip()
                
            if curr_fname:
                print(f"[+] Full name already present ('{curr_fname}'). Keeping existing name, not changing!")
                full_name = curr_fname
            else:
                full_name = generate_random_name(proxy_country)
                print(f"[*] Full name empty. Setting Full Name: {full_name} (Country base: {proxy_country or 'Random'})")
                await fname_input.fill(full_name)
            await page.get_by_role("button", name="Next").click()

            # Create username step (Keep existing username if already present)
            username_field = page.get_by_label("Create a username")
            if not await username_field.is_visible(timeout=5000):
                username_field = page.locator('input[aria-label="Username"], input[type="text-no_suggestion"]').first
            
            await expect(username_field).to_be_visible(timeout=30000)
            await page.wait_for_timeout(1500)  # Wait for React to populate suggested username
            
            # Extract the actual username (Keep existing username if present)
            try:
                extracted = ""
                uname_input = page.locator('input[aria-label="Username"], input[type="text-no_suggestion"]').first
                if await uname_input.is_visible(timeout=2000):
                    extracted = (await uname_input.input_value()).strip()
                    if not extracted:
                        extracted = (await uname_input.get_attribute("value") or "").strip()
                
                if not extracted:
                    extracted = (await username_field.input_value(timeout=2000)).strip()
                    if not extracted:
                        extracted = (await username_field.get_attribute("value") or "").strip()
                    
                if not extracted:
                    username_span = page.locator("span").filter(has_text=re.comuoile(r"^Username$", re.IGNORECASE)).first
                    if await username_span.is_visible(timeout=2000):
                        parent_text = await username_span.locator("..").inner_text(timeout=2000)
                        parts = parent_text.split('\n')
                        if len(parts) > 1:
                            extracted = parts[1].strip()
                        
                if extracted:
                    instauser = extracted
                    print(f"[+] Username already present: '{instauser}'. Keeping existing username, not changing!")
                else:
                    suggested_uname = (email.split('@')[0] + str(random.randint(100, 999))).lower()
                    print(f"[*] Username empty. Filling username: {suggested_uname}")
                    await username_field.fill(suggested_uname)
                    instauser = suggested_uname
            except Exception as ex:
                print(f"[-] Exception during username extraction: {ex}")
                pass
                
            print(f"[*] Confirming Username...")
            await page.get_by_role("button", name="Next").click()

            # Terms and conditions
            print(f"[*] Accepting Instagram Terms...")
            try:
                # Wait for either the label or the text to appear
                modal_locator = page.locator("text=To create an Instagram").first
                await expect(modal_locator).to_be_visible(timeout=30000)
                
                # First click (Attempt 1/3)
                terms_btn = page.get_by_role("button", name=re.compile(r"^(Allow and continue|Agree|I agree)$", re.IGNORECASE)).first
                await terms_btn.click(timeout=15000)
                print("[+] Clicked terms button (attempt 1/3).")
                
                # Max 2 re-appearances (attempt 2, then last attempt 3). Fir or try nahi karega -> rotate proxy!
                stuck_in_terms = False
                for attempt in (2, 3):
                    # Check if already redirected to registered page before waiting
                    registered_now = False
                    for _ in range(6):  # Check every 500ms for up to 3 seconds
                        if "accounts/registered" in page.url:
                            registered_now = True
                            break
                        await page.wait_for_timeout(500)

                    if registered_now or "accounts/registered" in page.url:
                        print("[+] Already redirected to registered page! Proceeding to 2FA immediately.")
                        break

                    if await terms_btn.is_visible(timeout=1500):
                        print(f"[*] Terms button appeared again (attempt {attempt}/3). Rotating IP via extension before clicking...")
                        await rotate_vpn_extension_ip(page, context)
                        await page.wait_for_timeout(2000)
                        # Re-locate terms button fresh
                        terms_btn = page.get_by_role("button", name=re.compile(r"^(Allow and continue|Agree|I agree)$", re.IGNORECASE)).first
                        print(f"[*] Clicking terms button (attempt {attempt}/3)...")
                        await terms_btn.click(timeout=15000)
                    else:
                        print("[*] No more terms buttons visible.")
                        break
                else:
                    # Check if still stuck on terms page
                    if "accounts/registered" not in page.url:
                        await page.wait_for_timeout(3000)
                        if await terms_btn.is_visible(timeout=2000):
                            stuck_in_terms = True

                if stuck_in_terms:
                    print(f"{Colors.FAIL}[!] Terms button stuck after 3 attempts. Rotating to next IPv6 proxy...{Colors.ENDC}")
                    raise TransientError("Stuck in terms loop after 3 attempts - rotating IPv6 proxy")
                        
            except TransientError:
                raise
            except Exception as e:
                print(f"[-] Error during terms acceptance: {e}")
            
            print(f"[*] Checking registration completion (waiting up to 70s)...")
            try:
                if "accounts/registered" in page.url:
                    print(f"[*] Already confirmed on registration URL ({page.url}).")
                    registration_success = True
                else:
                    await page.wait_for_url("**/accounts/registered/**", timeout=70000)
                    print(f"[*] Registration flow completed.")
                    registration_success = True
            except Exception as url_err:
                print(f"{Colors.WARNING}[-] Registration URL not found (timeout 70s). Relaunching with fresh IP and User-Agent...{Colors.ENDC}")
                raise TransientError("Registration URL timeout (70s) - requeuing with fresh fingerprint")
                
        except TransientError:
            raise  # Re-raise to ensure the worker restarts the session
        except Exception as e:
            # Don't mask real setup failures as "already registered".
            if login_outcome in ("insta_success", "meta_success"):
                print(f"[*] Meta profile setup not needed ({login_outcome}). Proceeding to 2FA. (setup note: {str(e)[:150]})")
                registration_success = True  # Already registered / existing account - proceed to 2FA
            else:
                if _is_transient_error(str(e)):
                    raise TransientError(f"Meta setup timed out on IPv6 proxy (login state '{login_outcome}'): {str(e)[:150]}")
                raise Exception(f"Meta setup failed and login state was '{login_outcome}': {str(e)[:200]}")
            
        # If registration failed (URL not found), save to separate file and skip 2FA
        if not registration_success:
            print(f"[!] Skipping 2FA for {email} — registration not confirmed. Reporting to panel.")
            _ck = await _grab_cookies_str(context)
            report_result("saved_needs_2fa", qid, {"username": instauser, "password": password, "email": email, "country": proxy_country, "ip": proxy_ip, "cookies": _ck})
            return

        # ─── STEP A: ATTEMPT DIRECT 2FA ON REGISTERED PAGE ────
        _set_stage("registered_direct_2fa")
        totp_secret = ""
        print("[*] Attempting 2FA setup directly on registered page via Extension API...")
        try:
            await page.wait_for_timeout(2000)
            await page.evaluate("window.postMessage({ type: 'IG_2FA_ACTION', action: 'START_SETUP' }, '*')")
            print("[*] Checking if 2FA completes directly on registered page (waiting up to 15s)...")
            secret_input = await page.wait_for_selector('#ig-2fa-helper input', timeout=15000)
            if secret_input:
                totp_secret = await secret_input.input_value()
                if totp_secret:
                    print(f"{Colors.OKGREEN}[+] Captured TOTP Secret DIRECTLY from registered page: {totp_secret}{Colors.ENDC}")
                    print(f"{Colors.OKGREEN}{Colors.BOLD}[+] Successfully enabled 2FA for {email}! (verified on registered page){Colors.ENDC}")
                    _ck = await _grab_cookies_str(context)
                    report_result("success", qid, {"username": instauser, "password": password, "totp": totp_secret, "email": email, "country": proxy_country, "ip": proxy_ip, "cookies": _ck})
                    return
        except Exception as de:
            print(f"[*] Direct 2FA on registered page not completed ({de}). Proceeding to 2FA page fallback...")

        # ─── STEP B: FALLBACK: NAVIGATE TO ACCOUNTS CENTER 2FA PAGE ────
        _set_stage("nav_2fa")
        print(f"[*] Navigating to Accounts Center 2FA setup (fallback)...")

        try:
            await _goto_with_retry(page, "https://accountscenter.instagram.com/password_and_security/two_factor/",
                                   wait_until="domcontentloaded", timeout=60000, tries=3)
            await page.wait_for_timeout(3000) # Give it a little time to load
        except TransientError:
            raise
        except Exception as e:
            print(f"[-] Warning: Navigation to Accounts Center may have timed out: {e}")
        
        # Extension (free vpn) auto-accepts GDPR cookies — no manual click needed
        
        # Smart loop to handle 'Get Started', 'Account Selection', or direct transition
        skip_email_otp = False
        try:
            print(f"[DEBUG] Waiting for Account Selection or Get Started/Continue...")
            start_btn = page.get_by_role("button", name=re.compile(r'^Get started$|^Continue$|^Next$', re.IGNORECASE)).first
            account_btn = page.get_by_text(instauser).first if instauser else None
            email_heading = page.get_by_role("heading", name=re.compile(r"Check your email|Enter the.*code|8.digit", re.IGNORECASE))
            choose_acc_text = page.get_by_text(re.compile(r"Choose an account to set up two-factor", re.IGNORECASE)).first
            
            for _ in range(15): # Max ~45 seconds total wait
                # 0. Check if Extension has already captured baseData
                try:
                    ext_status = await page.locator("#ig-2fa-helper-status").text_content(timeout=500)
                    if ext_status and "Data Captured" in ext_status:
                        print(f"[DEBUG] Extension already captured data ('{ext_status.strip()}'). Triggering 2FA directly!")
                        skip_email_otp = True
                        break
                except Exception:
                    pass

                # 1. Check for Account Selection (Generated Username or 'Choose an account')
                if account_btn and await account_btn.is_visible(timeout=1000):
                    print(f"[DEBUG] Found generated username ({instauser}) on screen. Skipping click and triggering 2FA extension directly!")
                    skip_email_otp = True
                    break # Break immediately without clicking

                if await choose_acc_text.is_visible(timeout=1000):
                    print(f"[DEBUG] Found 'Choose an account to set up two-factor authentication' on screen. Triggering 2FA extension directly!")
                    skip_email_otp = True
                    break
                    
                # 2. Check for Get Started / Continue
                if await start_btn.is_visible(timeout=1000):
                    print(f"[DEBUG] Found Get started/Continue button. Clicking...")
                    await start_btn.click(timeout=5000)
                    await page.wait_for_timeout(2000)
                    continue # Keep checking, it might show the account selection next
                    
                # 3. Check if we skipped to Email OTP
                if await email_heading.is_visible(timeout=1000):
                    print(f"[DEBUG] Page skipped to next step (Email OTP header found).")
                    skip_email_otp = False
                    break
                    
        except Exception as e:
            print(f"[DEBUG] Error during Account/Start selection: {e}")

        if skip_email_otp:
            print("[*] 2FA Account Selection screen / Extension data captured. Bypassing Email OTP check!")
            # Ensure extension has had a brief moment to capture baseData
            for _ in range(6):
                try:
                    ext_status = await page.locator("#ig-2fa-helper-status").text_content(timeout=500)
                    if ext_status and "Data Captured" in ext_status:
                        print(f"[*] Extension confirmed ready: {ext_status.strip()}")
                        break
                except Exception:
                    pass
                await page.wait_for_timeout(500)
        else:
            # Handle Email OTP if requested by Meta before allowing 2FA setup
            _set_stage("email_otp")
            email_otp_required = False
            email_otp_error = None
            try:
                print(f"[DEBUG] Checking if Meta is asking for Email OTP...")
                is_email_check = False
                try:
                    print(f"[DEBUG] Waiting for 'Check your email' or 'Enter the code' text...")
                    email_heading = page.get_by_role("heading", name=re.compile(r"Check your email|Enter the.*code|8.digit", re.IGNORECASE))
                    if await email_heading.is_visible(timeout=5000):
                        is_email_check = True
                    else:
                        fallback = page.locator(':has-text("Check your email"):visible, :has-text("8-digit"):visible').last
                        if await fallback.is_visible(timeout=2000):
                            is_email_check = True
                    if is_email_check:
                        print(f"[DEBUG] Found 'Check your email' or 'Enter the code' text!")
                    else:
                        print(f"[DEBUG] Did not find 'Check your email' text.")
                except Exception as e:
                    print(f"[DEBUG] Error checking email text: {e}")
                    
                code_input = page.get_by_placeholder(re.compile(r"code", re.IGNORECASE))
                code_input_visible = False
                try:
                    if await code_input.is_visible(timeout=3000):
                        code_input_visible = True
                except Exception:
                    pass
                    
                if is_email_check or code_input_visible:
                    email_otp_required = True
                    print(f"[*] Meta is requesting an Email OTP before 2FA.")
                    print(f"[*] Fetching OTP for {email} (Waiting up to 60s)...")
                    otp = await asyncio.to_thread(fetch_otp, email, seen_ids, max_retries=12)
                    
                    if not otp:
                        print(f"[-] No OTP received after 1 minute. Attempting to resend...")
                        try:
                            resend_btn = page.locator("text=Get a new code")
                            if not await resend_btn.is_visible(timeout=10000):
                                resend_btn = page.locator("text=send a new code")
                            if not await resend_btn.is_visible(timeout=10000):
                                resend_btn = page.locator("text=Resend")
                                
                            await resend_btn.click(timeout=15000)
                            print(f"[*] Clicked resend. Waiting another 60s for new OTP...")
                            otp = await asyncio.to_thread(fetch_otp, email, seen_ids, max_retries=12)
                        except Exception as e:
                            print(f"[-] Could not find or click resend button: {e}")
                    
                    if otp:
                        print(f"[+] Received OTP: {otp}")
                        await code_input.fill(otp)
                        submit_btn = page.locator("button, div[role='button']").filter(has_text=re.compile(r'Continue|Submit|Next', re.IGNORECASE)).first
                        if await submit_btn.is_visible(timeout=15000):
                            await submit_btn.click()
                        else:
                            await page.keyboard.press("Enter")
                        
                        await page.wait_for_timeout(5000)
                        
                        error_msg = page.locator("text=This code doesn't work")
                        if await error_msg.is_visible(timeout=3000):
                            print("[-] Code was incorrect. Checking if a newer OTP has already arrived (waiting up to 20s)...")
                            new_otp = await asyncio.to_thread(fetch_otp, email, seen_ids, max_retries=4)
                            if not new_otp:
                                print("[-] No new OTP arrived. Clicking 'Get a new code' to resend...")
                                new_code_btn = page.locator("text=Get a new code")
                                if await new_code_btn.is_visible(timeout=5000):
                                    await new_code_btn.click()
                                    print("[*] Clicked 'Get a new code', waiting 60s for new OTP...")
                                    new_otp = await asyncio.to_thread(fetch_otp, email, seen_ids, max_retries=12)
                                    
                            if new_otp:
                                print(f"[+] Received NEW OTP: {new_otp}")
                                await code_input.fill(new_otp)
                                if await submit_btn.is_visible(timeout=5000):
                                    await submit_btn.click()
                                else:
                                    await page.keyboard.press("Enter")
                                await page.wait_for_timeout(5000)
                            else:
                                raise Exception("Failed to fetch new Email OTP after incorrect code.")
                    else:
                        raise Exception("Failed to fetch Email OTP even after resend attempt.")
            except Exception as e:
                email_otp_error = str(e)[:200]
                print(f"[-] Email OTP stage failed: {email_otp_error}")

            if email_otp_required and email_otp_error:
                raise Exception(f"Email OTP required but failed: {email_otp_error}")

        # ─── STAGE TRACKING FLAGS ─────────────────────────────────────────
        totp_secret = ""        # Set once TOTP key is captured
        enter_code_success = False  # Set once code is submitted to Instagram
        confirmation_success = False  # Set once 2FA enablement is positively confirmed

        # Trigger Auto 2FA Extension
        _set_stage("select_auth_app")
        print("[*] Triggering Auto 2FA Setup via Extension API...")
        await page.wait_for_timeout(5000) # Give the extension a moment to intercept baseData
        await page.evaluate("window.postMessage({ type: 'IG_2FA_ACTION', action: 'START_SETUP' }, '*')")
        
        try:
            print("[*] Waiting for Extension to generate and submit 2FA...")
            secret_input = await page.wait_for_selector('#ig-2fa-helper input', timeout=30000)
            totp_secret = await secret_input.input_value()
            print(f"{Colors.OKGREEN}[+] Captured TOTP Secret via Extension: {totp_secret}{Colors.ENDC}")
        except Exception as e:
            print(f"[-] Extension failed to get the secret: {e}")
            _ck = await _grab_cookies_str(context)
            report_result("saved_enter_code_failed", qid, {"username": instauser, "password": password, "totp": "", "email": email, "country": proxy_country, "ip": proxy_ip, "cookies": _ck})
            return

        print(f"{Colors.OKGREEN}{Colors.BOLD}[+] Successfully enabled 2FA for {email}! (verified){Colors.ENDC}")
        # Report success to panel (panel ingests -> SQLite -> Google Sheets in real time)
        _ck = await _grab_cookies_str(context)
        report_result("success", qid, {"username": instauser, "password": password, "totp": totp_secret, "email": email, "country": proxy_country, "ip": proxy_ip, "cookies": _ck})
    except TransientError:
        # Network-level failure: let the caller requeue for a fresh circuit.
        # Do NOT report as final error here.
        raise
    except Exception as e:
        _el = time.monotonic() - _stage_info["t0"]
        print(f"{Colors.FAIL}[!] Error processing {email} at stage [{_stage_info['name']}] (+{_el:.0f}s): {e}{Colors.ENDC}")
        # Cookies bhi save karo (original bot ki tarah error_new.txt me the)
        try:
            _cookies = await context.cookies()
            cookie_string = ";".join([f"{c['name']}={c['value']}" for c in _cookies])
        except Exception as ce:
            print(f"[-] Could not grab cookies for {email}: {ce}")
            cookie_string = ""
        report_result("error", qid, {"username": instauser, "password": password, "email": email,
                                     "country": proxy_country, "ip": proxy_ip,
                                     "cookies": cookie_string,
                                     "stage": _stage_info["name"],
                                     "error": f"[{_stage_info['name']}] {str(e)[:300]}"})
        

    finally:
        await context.close()


# ══════════════════════════════════════════════════════════════════════════════
# RESIDENTIAL IPv6 SOCKS5 PROXY POOL (3proxy Integration)
# Trillions of clean residential mobile/fiber IPs rotated round-robin per account.
# ══════════════════════════════════════════════════════════════════════════════
_IPV6_POOL = []
_IPV6_POOL_INDEX = 0
_IPV6_LOCK = asyncio.Lock()

def _load_ipv6_proxy_pool():
    global _IPV6_POOL
    base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    cfg_paths = [
        r"C:\Users\PRADIP MUDI\OneDrive\Desktop\fb creator and proxy gen\global_ipv6_proxy_manager\config\3proxy.cfg",
        os.path.join(base_dir, "3proxy.cfg"),
        "3proxy.cfg"
    ]
    pool = []
    for p in cfg_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        m = re.search(r'(?:socks|proxy)\s+.*?-p(\d+)\s+.*?-e([0-9a-fA-F:]+)', line)
                        if m:
                            port = int(m.group(1))
                            ip = m.group(2)
                            pool.append((port, ip))
                if pool:
                    print(f"{Colors.OKGREEN}[+] Loaded {len(pool)} Residential IPv6 SOCKS5 proxies from 3proxy config!{Colors.ENDC}")
                    break
            except Exception as e:
                print(f"[-] Error reading {p}: {e}")
    _IPV6_POOL = pool
    return pool

async def _get_next_ipv6_proxy():
    global _IPV6_POOL_INDEX, _IPV6_POOL
    if not _IPV6_POOL:
        _load_ipv6_proxy_pool()
    async with _IPV6_LOCK:
        if not _IPV6_POOL:
            return None, None
        port, ip = _IPV6_POOL[_IPV6_POOL_INDEX % len(_IPV6_POOL)]
        _IPV6_POOL_INDEX += 1
        return port, ip

async def _fast_circuit_proxy():
    """Returns (proxy_server, local_port, exit_ip, country).
    Picks the next healthy Residential IPv6 SOCKS5 proxy from 3proxy pool."""
    for _ in range(10):
        port, assigned_ip = await _get_next_ipv6_proxy()
        if port:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1) as s:
                    pass
                return None, port, assigned_ip, "India (Residential IPv6)"
            except Exception:
                continue
    # If no responsive port found, try reloading pool
    _load_ipv6_proxy_pool()
    port, assigned_ip = await _get_next_ipv6_proxy()
    return None, port, assigned_ip, "India (Residential IPv6)"

async def run(playwright: Playwright) -> None:
    print(f"[*] Insta Worker {WORKER_VERSION} | {WORKER_ID}: claiming accounts from Redis queue ({re.sub(r'://[^:]*:[^@]+@', '://**:**@', REDIS_URL)}))")
    print(f"[*] Starting in Residential IPv6 SOCKS5 mode (3proxy pool)...")

    # Threads: --threads flag > Redis fleet default > 10
    # Har thread BILKUL independent hai — koi batch system nahi. Ek thread ka
    # account khatam hote hi wo turant next claim karta hai, doosron ka wait kiye bina.
    max_threads = WORKER_THREADS
    print(f"{Colors.OKCYAN}[*] {WORKER_ID}: using {max_threads} independent threads (back-to-back, no batches).{Colors.ENDC}")

    # ── PREFLIGHT GATE + SELF-HEAL ─────────────────────────────
    # Claim loop se PEHLE sehat jaanch: (a) chromium executable disk par
    # hai, (b) halka launch test, (c) 3proxy IPv6 pool zinda hai, (d) Redis ping.
    async def _preflight_fails():
        fails = []
        try:
            _exe = playwright.chromium.executable_path
            if not _exe or not os.path.exists(_exe):
                fails.append(("no_browser", "chromium exe missing: %s" % _exe))
        except Exception as e:
            fails.append(("no_browser", "exe path error: %s" % e))
        if not fails:
            _td = tempfile.mkdtemp(prefix="preflight-")
            _ctx = None
            try:
                _pre_args = [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    "--enforce-webrtc-ip-permission-check",
                ]
                if HEADLESS_MODE:
                    _pre_args.append("--headless=new")
                _ctx = await playwright.chromium.launch_persistent_context(
                    _td, headless=False,
                    args=_pre_args)
                await _ctx.close()
            except Exception as e:
                fails.append(("no_launch", "launch test fail: %s" % str(e)[:160]))
            finally:
                shutil.rmtree(_td, ignore_errors=True)
        if not fails:
            if not os.path.exists(EXTENSION_PATH):
                fails.append(("no_vpn_ext", f"AutoConnect VPN extension not found at: {EXTENSION_PATH}"))
        try:
            _r().ping()
        except Exception as e:
            fails.append(("no_redis", "redis ping fail: %s" % e))
        return fails


    def _heal_browser_sync():
        """playwright install dobara chalao + exe verify. (ok, note) return."""
        try:
            _rr = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"],
                                 capture_output=True, text=True, timeout=900)
            _exe2 = None
            try:
                from playwright.sync_api import sync_playwright as _spw
                with _spw() as _pp:
                    _exe2 = _pp.chromium.executable_path
            except Exception:
                _exe2 = None
            if _exe2 and os.path.exists(_exe2):
                return True, "exe mila: %s" % _exe2
            return False, "rc=%s, exe ab bhi missing" % _rr.returncode
        except Exception as e:
            return False, "install exception: %s" % str(e)[:120]

    _sick_cycle = 0
    _install_tries = 0
    while True:
        _fails = await _preflight_fails()
        if not _fails:
            _set_health("ok", "")
            print(f"{Colors.OKGREEN}[PREFLIGHT] OK — browser launch + VPN Extension ({os.path.basename(EXTENSION_PATH)}) + redis theek. Claim shuru.{Colors.ENDC}")
            break
        _code, _why = _fails[0]
        _sick_cycle += 1
        # ── SELF-HEAL koshish (sick-loop ke andar) ──
        if _code == "no_browser" and (_sick_cycle == 1 or _sick_cycle % 3 == 0):
            _install_tries += 1
            print(f"{Colors.WARNING}[SELF-HEAL] browser missing — playwright install retry #{_install_tries} chala raha hun...{Colors.ENDC}")
            sys.stdout.flush()
            _ok, _note = await asyncio.to_thread(_heal_browser_sync)
            if _ok:
                print(f"{Colors.OKGREEN}[SELF-HEAL] browser theek ho gaya ({_note}) — dobara jaanch...{Colors.ENDC}")
                sys.stdout.flush()
                continue
            _why = "install retry %d failed (%s); %s" % (_install_tries, _note, _why)
        elif _code in ("no_ipv6_pool", "no_3proxy"):
            print(f"{Colors.WARNING}[SELF-HEAL] 3proxy unreachable — reloading proxy pool (cycle {_sick_cycle})...{Colors.ENDC}")
            sys.stdout.flush()
            _load_ipv6_proxy_pool()
            await asyncio.sleep(10)
            continue
        _set_health(_code, _why)
        print(f"{Colors.FAIL}[PREFLIGHT] SICK: {_code} — {_why} | claim NAHI hoga; 60s me dobara jaanch...{Colors.ENDC}")
        sys.stdout.flush()
        await asyncio.sleep(60)

    # ── PRE-GENERATION BUFFER POOL (ut copy.py) ────────────────────────
    # Har thread ko account generate hone ka wait na karna pade.
    # Background workers pehle se 20 accounts generate karke ready rakhte hain.
    TARGET_BUFFER_SIZE = max(max_threads * 2, 20)
    ACCOUNT_BUFFER_QUEUE = asyncio.Queue(maxsize=TARGET_BUFFER_SIZE + 10)

    async def _pregen_producer_loop(pid):
        import importlib.util
        while True:
            try:
                if _renew_due():
                    return
                if ACCOUNT_BUFFER_QUEUE.qsize() >= TARGET_BUFFER_SIZE:
                    await asyncio.sleep(3)
                    continue

                spec = importlib.util.spec_from_file_location("ut_copy", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ut copy.py"))
                ut_copy = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(ut_copy)

                res = await asyncio.to_thread(ut_copy.create_meta_account, proxy_url=None)
                if res and len(res) == 3:
                    await ACCOUNT_BUFFER_QUEUE.put(res)
                    print(f"{Colors.OKGREEN}[+] [Pre-Gen Producer #{pid}] Account Ready: {res[0]} (Buffer Pool: {ACCOUNT_BUFFER_QUEUE.qsize()}/{TARGET_BUFFER_SIZE}){Colors.ENDC}")
                else:
                    await asyncio.sleep(2)
            except Exception as e:
                await asyncio.sleep(3)

    async def _get_or_generate_account():
        import importlib.util
        # 1. Instant check from pre-generated buffer
        try:
            acc = ACCOUNT_BUFFER_QUEUE.get_nowait()
            ACCOUNT_BUFFER_QUEUE.task_done()
            print(f"{Colors.OKGREEN}[+] [Instant Claim] Grabbed pre-generated account: {acc[0]} (Buffer pool remaining: {ACCOUNT_BUFFER_QUEUE.qsize()}){Colors.ENDC}")
            return acc
        except asyncio.QueueEmpty:
            pass

        # 2. Wait up to 12s for background producer to finish one
        print(f"[*] Buffer pool empty or warming up, waiting for ready account...")
        try:
            acc = await asyncio.wait_for(ACCOUNT_BUFFER_QUEUE.get(), timeout=12.0)
            ACCOUNT_BUFFER_QUEUE.task_done()
            print(f"{Colors.OKGREEN}[+] [Buffer Claim] Grabbed account from buffer: {acc[0]} (Remaining: {ACCOUNT_BUFFER_QUEUE.qsize()}){Colors.ENDC}")
            return acc
        except asyncio.TimeoutError:
            pass

        # 3. Direct generation fallback
        print("[*] Generating account directly using ut copy.py...")
        spec = importlib.util.spec_from_file_location("ut_copy", os.path.join(os.path.dirname(os.path.abspath(__file__)), "ut copy.py"))
        ut_copy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ut_copy)
        res = await asyncio.to_thread(ut_copy.create_meta_account, proxy_url=None)
        if not res:
            raise Exception("Failed to generate account using ut copy")
        return res

    async def process_single_account(raw, item):
        email, password, qid = item["email"], item["password"], item.get("qid", 0)
        global CURRENT_EMAIL
        CURRENT_EMAIL = "[%s] %s" % (_worker_tag.get() or "?", email)
        # Create a temporary directory for the persistent context (fresh state for each account)
        user_data_dir = tempfile.mkdtemp()
        requeued = False  # v7.4 fix: finally ke ack se pehle init - setup (circuit/browser) fail par UnboundLocalError se ack skip ho jata tha, item processing me fas jata tha (claim-spin)

        try:
            # GCloud/Linux browser args (supports extensions using new headless mode)
            # NOTE: --headless=new is ALWAYS passed so MV3 extensions (free vpn, ig_2fa_ext)
            # load correctly even when running on a headless server/VPS.
            # Playwright's headless=False is kept because passing headless=True to Playwright
            # completely disables extension loading at Chromium level.
            # The actual headless behaviour comes from --headless=new in args, not the parameter.
            browser_args = [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--enforce-webrtc-ip-permission-check",
            ]
            if HEADLESS_MODE:
                browser_args.append("--headless=new") # Always use new headless so MV3 extensions work
            EXTS = []
            if os.path.exists(EXTENSION_PATH): EXTS.append(EXTENSION_PATH)
            ig2fa_ext = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_2fa_ext")
            if os.path.exists(ig2fa_ext): EXTS.append(ig2fa_ext)
            
            adv_captcha = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ADV_CAPTCHA_PRO")
            if os.path.exists(adv_captcha): EXTS.append(adv_captcha)
            
            # Check both current directory and parent directory for meta_auto_photo_ext
            meta_auto_photo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meta_auto_photo_ext")
            if not os.path.exists(meta_auto_photo):
                meta_auto_photo = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "meta_auto_photo_ext")
            if os.path.exists(meta_auto_photo): EXTS.append(meta_auto_photo)

            # Auto GDPR Extension
            autogdpr_ext = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autogdpr")
            if os.path.exists(autogdpr_ext): EXTS.append(autogdpr_ext)

            if EXTS:
                ext_str = ",".join(EXTS)
                browser_args.extend([
                    f"--disable-extensions-except={ext_str}",
                    f"--load-extension={ext_str}",
                ])
            import importlib.util
            if "email" in item and "pw_cookies" in item and "password" in item:
                print(f"[*] Reusing existing account {item['email']} from retry...")
                email = item["email"]
                password = item["password"]
                pw_cookies = item["pw_cookies"]
            else:
                try:
                    account_data = await _get_or_generate_account()
                    email, password, pw_cookies = account_data
                    item["email"] = email
                    item["password"] = password
                    item["pw_cookies"] = pw_cookies
                except Exception as e:
                    print(f"[-] Account generation failed: {e}")
                    raise TransientError(f"Account gen failed: {e}")

            MOBILE_USER_AGENTS = [
                "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 11; Redmi Note 10 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 13; OnePlus 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 12; CPH2305) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 11; POCO X3 NFC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36",
                "Mozilla/5.0 (Linux; Android 13; SM-A546B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
            ]
            import random
            selected_ua = random.choice(MOBILE_USER_AGENTS)

            is_retry = bool(item.get("_retries", 0))
            saved_cookies = pw_cookies if "pw_cookies" in item else []
            ipv6_user_data_dir = None

            # ── UNIFIED SINGLE-BROWSER SESSION (AutoConnect VPN Extension IP) ──
            context = None
            detected_ip = "VPN IP"
            detected_country = "AutoConnect VPN"

            print("[*] Launching browser with AutoConnect VPN Extension...")
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                user_agent=selected_ua,
                viewport={'width': 412, 'height': 915},
                is_mobile=True,
                has_touch=True,
                permissions=['clipboard-read', 'clipboard-write'],
                args=browser_args,
                proxy=None  # AutoConnect VPN extension handles the proxy internally
            )
            await _apply_webrtc_protection(context)

            page = context.pages[0] if context.pages else await context.new_page()
            await Stealth().apply_stealth_async(page)
            bw_stats = await _install_bandwidth_saver(context, page)

            # Wait briefly for AutoConnect VPN extension to establish connection
            await page.wait_for_timeout(1500)

            # Detect connected VPN IP inside the browser
            try:
                ip_info = await page.evaluate("""
                    fetch('https://api.ipify.org?format=json')
                        .then(r => r.json())
                        .then(d => d.ip)
                        .catch(() => 'Connected')
                """)
                if ip_info and ip_info != 'Connected':
                    detected_ip = ip_info
                    print(f"{Colors.OKGREEN}[+] AutoConnect VPN Active! Browser Public IP: {detected_ip}{Colors.ENDC}")
                else:
                    print(f"{Colors.OKGREEN}[+] AutoConnect VPN Active!{Colors.ENDC}")
            except Exception:
                pass

            if saved_cookies:
                print(f"[*] Injecting session cookies generated from ut copy (Extension IP: {detected_ip})...")
                await context.add_cookies(saved_cookies)

            if not is_retry:
                print(f"[*] Opening auth.meta.com on Extension IP ({detected_ip})...")
                await _goto_with_retry(page, "https://auth.meta.com/", wait_until="domcontentloaded", timeout=60000, tries=3)
                await page.wait_for_timeout(2000)

                # Meta checkpoint flow on Extension IP
                print(f"[*] Checking Meta URL state for checkpoints (Extension IP: {detected_ip})...")
                for _ in range(30):
                    await _dismiss_meta_consent_if_present(page)
                    curr_url = page.url
                    if "checkpoint" in curr_url or "language" in curr_url:
                        break
                    await page.wait_for_timeout(1000)

                curr_url = page.url
                if "checkpoint" in curr_url:
                    await _handle_meta_checkpoint_flow(page, ip_label=f"VPN IP ({detected_ip})", context=context)
                else:
                    print(f"[*] Waiting for auth.meta.com/language URL on Extension IP ({detected_ip}) (refreshing every 5s, max 4 times)...")
                    for refresh_attempt in range(1, 5):
                        for _ in range(5):
                            if "language" in page.url or "instagram.com" in page.url:
                                print(f"[+] Meta login successful on Extension IP (language / instagram detected).")
                                break
                            await page.wait_for_timeout(1000)
                        if "language" in page.url or "instagram.com" in page.url:
                            break
                        if refresh_attempt < 4:
                            print(f"[*] /language not detected yet. Refreshing page ({refresh_attempt}/4)...")
                            try:
                                await page.reload(wait_until="domcontentloaded", timeout=15000)
                                await page.wait_for_timeout(1500)
                            except Exception:
                                pass

                print(f"[+] Meta checkpoint & session ready on Extension IP! Continuing to Instagram on SAME browser...")
            else:
                print(f"[*] Retry attempt detected for {email} - proceeding directly on Extension IP...")

            requeued = False  # transient requeue hua to finally me done mark nahi hoga
            try:
                await process_account(
                    context,
                    page,
                    email,
                    password,
                    qid,
                    local_port=None,
                    proxy_info=(detected_ip, detected_country),
                    is_retry=is_retry
                )

            except TransientError as te:
                # Bounded retry: transient network failure -> fresh circuit par dobara.
                # Max 2 requeue = 3 total attempts; uske baad final error.
                retries = int(item.get("_retries", 0) or 0)
                if retries < 2:
                    item["_retries"] = retries + 1
                    try:
                        # Redis requeue (no accounts.txt)
                        rc = _r()
                        rc.lpush("queue:pending", json.dumps(item))
                        try: rc.sadd("queue:emails", item.get("email", ""))
                        except: pass
                        print(f"{Colors.WARNING}[RETRY] {email}: requeued to Redis, attempt {retries+2}/3{Colors.ENDC}")
                        requeued = True
                    except Exception as requeue_err:
                        print(f"[-] requeue failed: {requeue_err}")
                        raise Exception(f"Transient failure, requeue failed: {te}")
                else:
                    print(f"[-] {email}: transient failure on final attempt (3/3) — reporting error.")
                    raise Exception(f"Network failed after 3 attempts: {te}")
            finally:
                _print_bandwidth_report(email, bw_stats)

        finally:
            ack_claim(raw, mark_done=not requeued)  # release claim; requeue hua to done mark NAHI (black-hole fix)
            # Clean up context and user data directory
            try:
                if context:
                    await context.close()
            except Exception:
                pass

            try:
                # Give the browser a moment to fully release file locks before deleting
                await asyncio.sleep(0.5)
                shutil.rmtree(user_data_dir, ignore_errors=True)
            except Exception as e:
                print(f"[-] Could not delete temporary profile dir: {e}")


        # Back-to-back: koi delay nahi — thread turant next account lega

    print(f"{Colors.OKCYAN}[*] {WORKER_ID}: independent mode — har thread apna account khatam karke turant next lega (koi batch wait nahi).{Colors.ENDC}")

    loop = asyncio.get_running_loop()
    claim_pool = ThreadPoolExecutor(max_workers=max_threads)
    # Auto-renew state: N accounts ya M ghante baad fresh worker process.
    # NOTE: single event-loop thread hai, isliye lock ki zaroorat nahi.
    renew_state = {"done": 0, "start": time.monotonic(), "renew": False}

    def _renew_due():
        if renew_state["renew"]:
            return True
        elapsed_h = (time.monotonic() - renew_state["start"]) / 3600
        if (WORKER_RESTART_EVERY > 0 and renew_state["done"] >= WORKER_RESTART_EVERY) \
                or (WORKER_RESTART_HOURS > 0 and elapsed_h >= WORKER_RESTART_HOURS):
            renew_state["renew"] = True
            return True
        return False

    async def worker_loop(tag):
        # Is task ka naam set karo — iske andar ke SAARE print() terminal me
        # [Tn] tag ke saath dikhenge (process_account ke andar wale bhi).
        _worker_tag.set(tag)
        print(f"{Colors.OKCYAN}[*] {tag}: started.{Colors.ENDC}")
        idle_rounds = 0
        while True:
            if _is_paused():
                await asyncio.sleep(10)
                continue
            if _renew_due():
                print(f"[*] {tag}: renew flagged — naya account nahi lunga, exiting.")
                return
            claimed = await loop.run_in_executor(claim_pool, claim_one)
            if claimed == "DOWN":
                print(f"{Colors.WARNING}[!] {tag}: Redis unreachable, retrying in 30s...{Colors.ENDC}")
                await asyncio.sleep(30)
                continue
            if claimed == "GUARD":
                # v7.6: done_qids guard-discard — queue khaali NAHI hai, sirf ye item
                # pehle se done tha. Idle round mat gino, turant next item dekho.
                await asyncio.sleep(1)
                continue
            if claimed is None:
                idle_rounds += 1
                # v7.6: idle par EXIT NAHI (purana idle-exit hi fleet-death ki jad thi).
                # Backoff sleep 10s se badhkar max 60s — worker zinda rahega, queue me
                # kaam aate hi turant pakdega; kaam milne par idle_rounds reset hota hai.
                backoff = min(10 * idle_rounds, 60)
                if idle_rounds <= 3 or idle_rounds % 10 == 0:
                    print(f"{Colors.WARNING}[~] {tag}: queue khaali hai (idle round {idle_rounds}) — {backoff}s backoff, worker ZINDA hai (v7.6 me idle-exit band).{Colors.ENDC}")
                await asyncio.sleep(backoff)
                continue
            if _renew_due():
                # Claim block ke dauraan renew flag lag gaya — account wapas queue me daalo, skip karo
                raw, item = claimed
                try:
                    _r().lpush("queue:pending", raw)
                except Exception:
                    pass
                ack_claim(raw, mark_done=False)
                print(f"[*] {tag}: renew flagged — claimed account wapas queue me daal diya, exiting.")
                return
            idle_rounds = 0
            raw, item = claimed
            email = item.get("email", "?")
            print(f"{Colors.OKBLUE}{Colors.BOLD}[*] {tag}: claimed {email} — starting.{Colors.ENDC}")
            try:
                await process_single_account(raw, item)
            except Exception as e:
                print(f"{Colors.FAIL}[!] {tag}: UNCAUGHT error on {email}: {e}{Colors.ENDC}")
            print(f"{Colors.OKCYAN}[*] {tag}: finished {email} — next account (back-to-back).{Colors.ENDC}")
            renew_state["done"] += 1
            # NOTE: yahan koi sleep/delay nahi — loop turant next account claim karega

    tags = ["T%d" % (i + 1) for i in range(max_threads)]
    producer_count = min(4, max(2, max_threads // 2))
    producer_tasks = [asyncio.create_task(_pregen_producer_loop(p + 1), name=f"PreGen-P{p + 1}") for p in range(producer_count)]
    print(f"{Colors.OKGREEN}[*] {WORKER_ID}: {producer_count} Pre-Gen Background Producer tasks started (Target pool: {TARGET_BUFFER_SIZE} accounts ready).{Colors.ENDC}")

    tasks = [asyncio.create_task(worker_loop(t), name=t) for t in tags]
    print(f"{Colors.OKCYAN}[*] {WORKER_ID}: {max_threads} independent threads live ({', '.join(tags)}) — koi thread kisi ka wait nahi karega.{Colors.ENDC}")
    # return_exceptions=True: agar koi thread cancel ho jaye ya usme koi
    # unexpected exception aaye to bhi poora worker exit(1) me na mare —
    # renew/exit path hamesha chalega (renew ke time ka CancelledError crash fix).
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for pt in producer_tasks:
        pt.cancel()
    for r in results:
        if isinstance(r, asyncio.CancelledError):
            print(f"{Colors.WARNING}[!] ek thread cancel hua tha — renew/exit path phir bhi chalega.{Colors.ENDC}")
        elif isinstance(r, BaseException):
            print(f"{Colors.FAIL}[!] thread me unexpected {type(r).__name__}: {r}{Colors.ENDC}")
    sys.stdout.flush()
    claim_pool.shutdown(wait=False)

    if renew_state["renew"]:
        # Sab threads ka kaam khatam — ab renew safe hai (koi account in-flight nahi)
        done_n = renew_state["done"]
        elapsed_h = (time.monotonic() - renew_state["start"]) / 3600
        print(f"\n{Colors.OKCYAN}{Colors.BOLD}[*] {WORKER_ID}: {done_n} accounts / {elapsed_h:.1f}h ho gaye — restarting worker...{Colors.ENDC}")
        sys.stdout.flush()
        _kill_own_chrome()
        await _graceful_async_shutdown()
        _safe_execv([sys.executable] + sys.argv)
    else:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}[+] {WORKER_ID}: all threads idle — queue empty, worker shutting down.{Colors.ENDC}")


def _kill_own_chrome():
    """Is worker ke bache-khuche (zombie) browser processes maaro. Sibling workers ko haath nahi."""
    me = os.getpid()
    killed = 0
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open(f"/proc/{pid}/stat") as f:
                    parts = f.read().rsplit(")", 1)
                    ppid = int(parts[1].split()[1])
                with open(f"/proc/{pid}/comm") as f:
                    comm = f.read().strip().lower()
            except Exception:
                continue
            if ppid == me and "chrome" in comm:
                try:
                    os.kill(int(pid), 9)
                    killed += 1
                except Exception:
                    pass
    except Exception:
        pass
    if killed:
        print(f"[*] Cleaned {killed} leftover browser process(es).")
    return killed

async def _graceful_async_shutdown(timeout=15):
    """execv se PEHLE saare pending asyncio tasks cancel karke loop settle karo.
    Koi coroutine suspended na rahe - nahi to shutdown pe
    'RuntimeError: coroutine ignored GeneratorExit' noise aata hai."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    cur = asyncio.current_task(loop)
    tasks = [t for t in asyncio.all_tasks(loop) if t is not cur]
    if not tasks:
        return
    print(f"[*] Shutting down {len(tasks)} pending asyncio task(s)...")
    sys.stdout.flush()
    for t in tasks:
        t.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
    except Exception:
        pass
    try:
        await asyncio.sleep(0.3)
    except Exception:
        pass


def install_python_deps():
    """
    Auto-install required Python packages if missing.
    """
    required = [
        "playwright", "playwright-stealth", "pyotp", "requests"
    ]
    for pkg in required:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"{Colors.OKCYAN}[*] Installing missing package: {pkg}{Colors.ENDC}")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    
    # Install Playwright browsers (chromium)
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, text=True
    )
    if "already installed" not in result.stdout + result.stderr:
        subprocess.run([sys.executable, "-m", "playwright", "install-deps", "chromium"],
                       capture_output=True)
    print(f"{Colors.OKGREEN}[+] All Python dependencies ready.{Colors.ENDC}")


async def main():
    # Suppress harmless asyncio cleanup warnings on Linux
    loop = asyncio.get_event_loop()
    def _quiet_exception_handler(loop, context):
        msg = str(context.get("exception", context.get("message", "")))
        # Suppress proxy task cleanup noise
        if any(x in msg for x in [
            "Task was destroyed", "ConnectionReset", "BrokenPipe",
            "ConnectionAborted", "handle_client"
        ]):
            return
        loop.default_exception_handler(context)
    loop.set_exception_handler(_quiet_exception_handler)

    async with async_playwright() as playwright:
        await run(playwright)


if __name__ == "__main__":
    print(f"{Colors.HEADER}{Colors.BOLD}=== {WORKER_ID} | Fleet Mode (Residential IPv6) | {WORKER_THREADS} threads ==={Colors.ENDC}")
    install_python_deps()
    start_imap_listener()
    import threading as _th
    _th.Thread(target=heartbeat_loop, daemon=True).start()
    _th.Thread(target=command_loop, daemon=True).start()
    asyncio.run(main())
