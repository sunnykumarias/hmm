import requests
import time

def fetch_otp(email, digits=6, timeout=180, interval=5):
    email = email.lower().strip()
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get("https://mailapi.secretvibe.us/api/otp.php", params={"email": email, "digits": digits}, timeout=10).json()
            if r.get("success") and r.get("data") and r["data"].get("otp"):
                return str(r["data"]["otp"])
        except Exception:
            pass
        time.sleep(interval)
    return None

def run_requests(email):
    url_encoded_email = email.replace("@", "%40")

    # Common headers for all requests
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "priority": "u=1, i",
        "x-asbd-id": "359341",
        "x-fb-lsd": "AdT-wyjZ0oZR7N05-EHVUK7jOJ8",
        "cookie": "datr=5YzAahJ6GwN8R59hBRVtMY_m; meta_csrf=5xP5YU4OGbE6EMHPN4hs7H",
        "Referer": "https://auth.meta.com/?rcs=ATooipCBts37EGowHx9bC7l2fVGyX0Ik0b8Tk026X882N82oQvwWvAAVp6vqg8SY3rgSG6UljbdyEFRwAKb9jSrWLlXyc6W3GEpfEUVf9Jz8369lPc5VHs4fWZ0dcNalN5WvafAP2f7rladKBkf7P1bWvH2pn1jZTFFavyjwbip-Y3aUS1LUSUkj3_4"
    }

    print("Sending Request 1: send-nonce...")
    body1 = f"contact_point={url_encoded_email}&qpl_join_id=fbbbd19c3ca9412fd&waterfall_id=1dfb44b9-61f0-4a9a-a725-7ddc518915a1&use_fb_cp_nonce=false&use_ig_cp_nonce=false&__user=0&__a=1&__req=k&__hs=20729.HYP%3Afrl_comet_auth_fbg.2.1...0&dpr=1&__ccg=GOOD&__rev=1049199548&__s=ym0w4k%3Abai2xc%3A2jjsnq&__hsi=7692303117470959823&__dyn=7xe6E5q5U5ObwKBAg5S1Dxu13w8CewSwMwNw9G2S0lW4o0B-q1ew2io2awpUO0n24o5-0Bo7O2l0Fwqo31w9O0H8-U2zxe2GewbS361qw8Xwn82Lw6OyES1Tw8W0Lo6-1FwCwe-1Iwqo5u1qwUw8S1Tw8q0JU0Vy3mew&__csr=gkBujABh-IaMx2-nWhKd8FEkCuUjCyF9qZu5V8iz9rDXiw10W0EO0eC02mK04jEObw81a0WouFGK4pWmbx6368UWbK2G4EkF09Rwddw05EZw3yE1mFqwyIS2a0G8094E0W-07nqc1ZgAwhU5izU0Wa05bE0iAxaew&__hsdp=gjg8kyf9144UG0gh2-gx83WG680HW3O0iqE023Zw1CW&__hblp=09O5F83WwACG482AwgqBxa0a-wYjwem3W3S09Gw0Gww0Bew0zVw5Gw1CW0ty2-3W2bwuo0n0wf604d8dU4q&__sjsp=gjg8kyf9d92MjyE&__comet_req=33&lsd=AdT-wyjZ0oZR7N05-EHVUK7jOJ8&jazoest=22097&__spin_r=1049199548&__spin_b=trunk&__spin_t=1791003886&__jssesw=1"
    res1 = requests.post("https://auth.meta.com/api/login-email-otp/send-nonce/", headers=headers, data=body1)
    print("Status:", res1.status_code)
    print("Response:", res1.text[:200]) # Print first 200 chars

    print("\nSending Request 2: check-contact-point-availability...")
    body2 = f"account_reg_info[birthday]=2026-10-03&account_reg_info[device_id]&account_reg_info[email]={url_encoded_email}&account_reg_info[first_name]&account_reg_info[has_youth_consent]=false&account_reg_info[is_bootstrap_flow]=false&account_reg_info[last_name]&account_reg_info[pc_rendering_data]&account_reg_info[phone_number]&account_reg_info[registration_flow_id]&allow_unconfirmed_email=false&check_for_pre_registration_restrictions=true&check_mma_account=true&contact_point={url_encoded_email}&contact_point_type=EMAIL_ADDRESS&reg_integrity&check_ntm_qe=true&skip_xapp_checks=false&caa_event_flow&csi=P2yDEiAk-0OvV3Y3inrhQnf5&event_client_time=1791003900.503&waterfall_id=1dfb44b9-61f0-4a9a-a725-7ddc518915a1&qpl_join_id=f7ae28f13d4c22158&__user=0&__a=1&__req=i&__hs=20729.HYP%3Afrl_comet_auth_fbg.2.1...0&dpr=1&__ccg=GOOD&__rev=1049199548&__s=ym0w4k%3Abai2xc%3A2jjsnq&__hsi=7692303117470959823&__dyn=7xe6E5q5U5ObwKBAg5S1Dxu13w8CewSwMwNw9G2S0lW4o0B-q1ew2io2awpUO0n24o5-0Bo7O2l0Fwqo31w9O0H8-U2zxe2GewbS361qw8Xwn82Lw6OyES1Tw8W0Lo6-1FwCwe-1Iwqo5u1qwUw8S1Tw8q0JU0Vy3mew&__csr=gkBujABh-IaMx2-nWhKd8FEkCuUjCyF9qZu5V8iz9rDXiw10W0EO0eC02mK04jEObw81a0WouFGK4pWmbx6368UWbK2G4EkF09Rwddw05EZw3yE1mFqwyIS2a0G8094E0W-07nqc1ZgAwhU5izU0Wa05bE0iAxaew&__hsdp=gjg8kyf9144UG0gh2-gx83WG680HW3O0iqE023Zw1CW&__hblp=09O5F83WwACG482AwgqBxa0a-wYjwem3W3S09Gw0Gww0Bew0zVw5Gw1CW0ty2-3W2bwuo0n0wf604d8dU4q&__sjsp=gjg8kyf9d92MjyE&__comet_req=33&lsd=AdT-wyjZ0oZR7N05-EHVUK7jOJ8&jazoest=22097&__spin_r=1049199548&__spin_b=trunk&__spin_t=1791003886&__jssesw=1"
    res2 = requests.post("https://auth.meta.com/api/check-contact-point-availability/", headers=headers, data=body2)
    print("Status:", res2.status_code)
    print("Response:", res2.text[:200])

    print(f"\nWaiting for 6-digit OTP for email {email}...")
    otp = fetch_otp(email, digits=6, timeout=60, interval=3)
    
    if not otp:
        print("Failed to fetch OTP within timeout!")
        return
        
    print(f"Success! Caught 6-digit OTP: {otp}")

    print("\nSending Request 3: otp-login...")
    body3 = f"contact_point={url_encoded_email}&otp={otp}&client_session_id=P2yDEiAk-0OvV3Y3inrhQnf5&di&gk_enable&native_sso_etoken&redirect_uri&utm_source&waterfall_id=1dfb44b9-61f0-4a9a-a725-7ddc518915a1&caa_event_flow=login_manual&csi=P2yDEiAk-0OvV3Y3inrhQnf5&event_client_time=1791003957.36&event_step_login=otp&qpl_join_id=fbf3198b5462dbccf&__user=0&__a=1&__req=s&__hs=20729.HYP%3Afrl_comet_auth_fbg.2.1...0&dpr=1&__ccg=GOOD&__rev=1049199548&__s=ym0w4k%3Abai2xc%3A2jjsnq&__hsi=7692303117470959823&__dyn=7xe6E5q5U5ObwKBAg5S1Dxu13w8CewSwMwNw9G2S0lW4o0B-q1ew2io2awpUO0n24o5-0Bo7O2l0Fwqo31w9O0H8-U2zxe2GewbS361qw8Xwn82Lw6OyES1Tw8W0Lo6-1FwCwe-1Iwqo5u1qwUw8S1Tw8q0JU0Vy3mew&__csr=gkBujABh-IaMx2-nWhKd8FEkCuUjCyF9qZu5V8iz9rDXiw10W0EO0eC02mK04jEObw81a0WouFGK4pWmbx6368UWbK2G4EkF09Rwddw05EZw3yE1mFqwyIS2a0G8094E0W-07nqc1ZgAwhU5izU0Wa05bE0iAxaew&__hsdp=gjg8kyf9144UG0gh2-gx83WG680HW3O0iqE023Zw1CW&__hblp=09O5F83WwACG482AwgqBxa0a-wYjwem3W3S09Gw0Gww0Bew0zVw5Gw1CW0ty2-3W2bwuo0n0wf604d8dU4q&__sjsp=gjg8kyf9d92MjyE&__comet_req=33&lsd=AdT-wyjZ0oZR7N05-EHVUK7jOJ8&jazoest=22097&__spin_r=1049199548&__spin_b=trunk&__spin_t=1791003886&__jssesw=1"
    res3 = requests.post("https://auth.meta.com/api/otp-login/", headers=headers, data=body3)
    print("Status:", res3.status_code)
    print("Response:", res3.text[:200])

import os

if __name__ == "__main__":
    if not os.path.exists("accounts.txt"):
        print("Error: accounts.txt file not found!")
    else:
        with open("accounts.txt", "r") as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split("|")
            email = parts[0].strip()
            
            print(f"\n=============================================")
            print(f"Processing Account: {email}")
            print(f"=============================================")
            run_requests(email)
            time.sleep(2)
