# import os
# import time

# # Use logger to write fake anomalous events
# def simulate_auth_failures():
#     for i in range(3):
#         os.system('logger -p auth.err "pam_unix(sudo:auth): authentication failure; user=testuser"')
#         print("⚠️  Simulated auth failure")
#         time.sleep(1)

# def simulate_ssh_failures():
#     for i in range(3):
#         os.system('logger -p auth.err "sshd[1234]: Failed password for invalid user hacker from 192.168.0.50 port 2222 ssh2"')
#         print("⚠️  Simulated ssh failure")
#         time.sleep(1)

# def simulate_kernel_warnings():
#     for i in range(3):
#         os.system('logger -p kern.warn "kernel: possible memory corruption detected"')
#         print("⚠️  Simulated kernel warning")
#         time.sleep(1)

# if __name__ == "__main__":
#     simulate_auth_failures()
#     simulate_ssh_failures()
#     simulate_kernel_warnings()
#     print("✅ Done simulating anomalies!")



# import random
# import time
# import datetime

# # Where to write simulated logs (you can pick any monitored file)
# LOG_FILE = "/var/log/pacman.log"  # must be one of the LOG_FILES you monitor

# # Some example anomalous patterns
# ANOMALY_PATTERNS = [
#     "CRITICAL: Unexpected root shell opened",
#     "ALERT: Unauthorized access attempt detected",
#     "FATAL: Kernel panic - not syncing: VFS",
#     "SECURITY BREACH: User root logged in from suspicious IP",
#     "Exploit attempt detected: Buffer overflow in sshd",
#     "!!! SYSTEM COMPROMISED !!!",
#     "Data corruption detected on disk /dev/sda1",
#     "Segmentation fault in process 12345",
#     "Unusual network activity from IP 192.168.0.66",
#     "High CPU usage detected: possible cryptojacking"
# ]

# def generate_anomaly_line():
#     timestamp = datetime.datetime.now().strftime("%b %d %H:%M:%S")
#     host = "testhost"
#     process = random.choice(["kernel", "sshd", "systemd", "cron", "sudo"])
#     message = random.choice(ANOMALY_PATTERNS)
#     return f"{timestamp} {host} {process}[{random.randint(1000,9999)}]: {message}"

# if __name__ == "__main__":
#     print("🚀 Starting anomaly simulation...")
#     try:
#         while True:
#             anomaly_line = generate_anomaly_line()
#             print(f"✏️ Writing anomaly: {anomaly_line}")
#             with open(LOG_FILE, "a") as f:
#                 f.write(anomaly_line + "\n")
#             time.sleep(random.uniform(2, 5))  # write every few seconds
#     except KeyboardInterrupt:
#         print("\n🛑 Stopped anomaly simulation.")











import random
import datetime
import time
# import pandas as pd
# import os

def random_ip():
    return ".".join(str(random.randint(1, 255)) for _ in range(4))

def random_port():
    return random.randint(1024, 65535)

def random_user():
    return random.choice(['fztu', 'root', 'ubuntu', 'admin', 'test', 'guest', 'oracle', 'backup', 'webmaster', 'chen', 'pgadmin', 'matlab', '123'])

def random_pid():
    return random.randint(1000, 30000)

def random_hostname():
    return random.choice(['LabSZ', 'server', 'prod1', 'testvm'])

def random_number():
    return random.randint(11, 99)

def generate_normal_log():
    templates = [
        "pam_unix(sshd:session): session closed for user {user}",
        "pam_unix(sshd:session): session opened for user {user} by (uid={try1})",
        "Connection closed by {ip} [preauth]",
        "Received disconnect from {ip}: {num}: Bye Bye [preauth]",
        "Received disconnect from {ip}: {num}: Closed due to user request [preauth]",
        "Received disconnect from {ip}: {num}: disconnected by user",
        "Did not receive identification string from {ip}",
        "PAM service(sshd) ignoring max retries; {try2} > {try1}",
        "Accepted password for {user} from {ip} port {port} ssh{try0}"
    ]
    tpl = random.choice(templates)

    return [
        datetime.datetime.now().strftime("%b %d %H:%M:%S"),
        random_hostname(),
        random_pid(),
        tpl.format(
            user=random_user(),
            ip=random_ip(),
            port=random_port(),
            num=random_number(),
            try0=random.randint(1, 9),
            try1=random.randint(1, 4),
            try2=random.randint(5, 9)
        )
    ]

def generate_anomaly_log():
    templates = [
        "reverse mapping checking getaddrinfo for ns.randomdomain.com [{ip}] failed - POSSIBLE BREAK-IN ATTEMPT!",
        "Invalid user {user} from {ip}",
        "input_userauth_request: invalid user {user} [preauth]",
        "pam_unix(sshd:auth): authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost={ip}",
        "pam_unix(sshd:auth): authentication failure; logname= uid={try2} euid={try1} tty=ssh ruser= rhost={ip}",
        "Failed password for invalid user {user} from {ip} port {port} ssh{try0}",
        "message repeated {count} times: [ Failed password for root from {ip} port {port} ssh{try0}]",
        "Disconnecting: Too many authentication failures for {user} [preauth]",
        "PAM {count} more authentication failures; logname= uid={try1} euid={try2} tty=ssh ruser= rhost={ip}  user={user}",
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
    ]
    tpl = random.choice(templates)
    return [
        datetime.datetime.now().strftime("%b %d %H:%M:%S"),
        random_hostname(),
        random_pid(),
        tpl.format(
            user=random_user(),
            ip=random_ip(),
            port=random_port(),
            count=random.randint(1, 10),
            num=random_number(),
            try0=random.randint(1, 9),
            try1=random.randint(1, 4),
            try2=random.randint(5, 9),
            rand=random.randint(123450, 987650)
        )
    ]

def generate_logs():
    # make anomalies rarer
    if random.random() < 0.2:
        return generate_anomaly_log()
    else:
        return generate_normal_log()

if __name__ == "__main__":
    LOG_FILE = "/var/log/pacman.log"
    print("🚀 Starting anomaly simulation...")
    try:
        while True:
            new_logs = generate_logs()
            print(f"✏️ Writing Log: {' | '.join(map(str, new_logs))}")
            with open(LOG_FILE, "a") as f:
                f.write("\t".join(map(str, new_logs)) + "\n")
            time.sleep(random.uniform(2, 5))  # write every few seconds
    except KeyboardInterrupt:
        print("\n🛑 Stopped anomaly simulation.")
