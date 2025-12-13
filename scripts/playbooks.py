# scripts/playbooks.py
import subprocess
import requests
import re
from app.config import settings
# You can expand this file with more actions

def block_ip_ufw(ip_address: str):
    """
    Blocks an IP address using UFW (Uncomplicated Firewall).
    NOTE: This requires the script to be run with sudo privileges.
    """
    if not ip_address:
        print("PLAYBOOK ERROR: No IP address provided to block_ip_ufw.")
        return

    print(f"PLAYBOOK ACTION: Blocking IP {ip_address} with UFW...")
    try:
        # Using 'insert 1' prepends the rule to the top
        subprocess.run(['sudo', 'ufw', 'insert', '1', 'deny', 'from', ip_address, 'to', 'any'], check=True)
        print(f"PLAYBOOK SUCCESS: IP {ip_address} blocked successfully.")
    except subprocess.CalledProcessError as e:
        print(f"PLAYBOOK FAILED: Could not block IP {ip_address}. Error: {e}")
    except FileNotFoundError:
        print("PLAYBOOK FAILED: 'sudo' or 'ufw' command not found. Is UFW installed?")

def send_slack_alert(message: str):
    """
    Sends a message to a Slack webhook.
    """
    # You would get this URL from your Slack App configuration
    webhook_url = settings.SLACK_WEBHOOK_URL
    if not webhook_url:
        print("PLAYBOOK WARNING: SLACK_WEBHOOK_URL is not set in the .env file. Cannot send alert.")
        return
    
    print(f"PLAYBOOK ACTION: Sending Slack alert: {message}")
    try:
        response = requests.post(webhook_url, json={'text': message}, headers={'Content-Type': 'application/json'})
        if response.status_code == 200:
            print("PLAYBOOK SUCCESS: Slack alert sent.")
        else:
            print(f"PLAYBOOK FAILED: Slack returned status code {response.status_code}.")
    except Exception as e:
        print(f"PLAYBOOK FAILED: Could not send Slack alert. Error: {e}")

# Add more actions like "disable_user_ad", "isolate_host_edr", etc.