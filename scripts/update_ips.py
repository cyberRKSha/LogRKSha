# scripts/update_ips.py
import requests
import os
import random

# --- Configuration ---
IPSUM_URL = "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt"
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ATT_SIM_PATH = os.path.join(PROJECT_ROOT, "scripts", "att_sim.py")
IP_COUNT = 100 # How many of the new IPs to use

def fetch_ips():
    """Fetches the list of malicious IPs from the IPsum repository."""
    print(f"[*] Fetching malicious IPs from {IPSUM_URL}...")
    try:
        response = requests.get(IPSUM_URL, timeout=10)
        response.raise_for_status()

        # The ipsum.txt file has comments starting with '#'. We'll ignore those.
        lines = [line.strip() for line in response.text.splitlines() if not line.strip().startswith("#") and line.strip()]
        ips = [line.split()[0] for line in lines]
        print(f"[+] Successfully fetched {len(ips)} IPs.")
        return ips
    except requests.exceptions.RequestException as e:
        print(f"[!] ERROR: Could not fetch IP list: {e}")
        return None

def update_att_sim_script(new_ips):
    """Rewrites the att_sim.py script with the new list of IPs."""
    if not new_ips:
        print("[!] No new IPs to update. Exiting.")
        return

    print(f"[*] Updating {ATT_SIM_PATH}...")

    try:
        with open(ATT_SIM_PATH, 'r') as f:
            lines = f.readlines()

        # Find the start and end of the ATTACKER_IPS list
        start_index = -1
        end_index = -1
        for i, line in enumerate(lines):
            if "ATTACKER_IPS = [" in line:
                start_index = i
            elif start_index != -1 and "]" in line:
                end_index = i
                break

        if start_index == -1 or end_index == -1:
            print("[!] ERROR: Could not find the ATTACKER_IPS list in the script.")
            return

        # Keep some of the original, known-bad IPs for consistency
        original_ips_to_keep = [
            "113.160.235.150",  # Known bad
            "87.120.191.13",
            "45.146.165.111",
            "118.175.93.155",
            "193.42.109.42",   # Russia
            "129.215.17.15",   # Germany
            "103.197.144.1",   # Vietnam
            "45.33.32.156",    # USA
            "131.103.24.238",  # Brazil
            "197.210.64.133"   # Nigeria
        ]

        # Create the new list of IPs
        # final_ips = original_ips_to_keep + random.sample(new_ips, min(IP_COUNT, len(new_ips)))
        final_ips = original_ips_to_keep + new_ips[:IP_COUNT]

        # Format the new list into Python code
        new_list_lines = ["ATTACKER_IPS = [\n"]
        for ip in final_ips:
            new_list_lines.append(f'    "{ip}",\n')
        new_list_lines.append("]\n")

        # Reconstruct the file content
        new_content = lines[:start_index] + new_list_lines + lines[end_index+1:]

        with open(ATT_SIM_PATH, 'w') as f:
            f.writelines(new_content)

        print(f"[+] Successfully updated the ATTACKER_IPS list with {len(final_ips)} IPs.")

    except FileNotFoundError:
        print(f"[!] ERROR: Could not find the script at {ATT_SIM_PATH}")
    except Exception as e:
        print(f"[!] ERROR: An unexpected error occurred: {e}")


if __name__ == "__main__":
    latest_ips = fetch_ips()
    update_att_sim_script(latest_ips)
    