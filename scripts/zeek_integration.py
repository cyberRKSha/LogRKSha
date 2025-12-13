#!/usr/bin/env python3
"""
Zeek Integration for Log Anomaly Detector
Manages Zeek process and log monitoring
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings

logger = logging.getLogger(__name__)

class ZeekManager:
    def __init__(self):
        self.zeek_bin = "/usr/local/zeek/bin/zeek"
        self.zeekctl_bin = "/usr/local/zeek/bin/zeekctl" 
        self.zeek_config_dir = "/opt/zeek/etc"
        self.zeek_log_dir = "/opt/zeek/logs"
        self.interface = "wlp0s20f3"  # Your network interface
        
    def setup_zeek_directories(self):
        """Create necessary Zeek directories"""
        dirs = [
            "/opt/zeek/etc",
            "/opt/zeek/logs", 
            "/opt/zeek/spool",
            "/opt/zeek/logs/current"
        ]
        
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
            
    def create_zeek_config(self):
        """Create Zeek configuration files"""
        
        # Node configuration
        node_config = f"""[zeek]
                    type=standalone
                    host=localhost
                    interface={self.interface}
                    """
        
        with open(f"{self.zeek_config_dir}/node.cfg", "w") as f:
            f.write(node_config)
            
        # Networks configuration
        networks_config = """# Local networks
                    192.168.1.0/24      Private IP space
                    10.0.0.0/8          Private IP space  
                    172.16.0.0/12       Private IP space
                    127.0.0.0/8         Loopback
                    """
        
        with open(f"{self.zeek_config_dir}/networks.cfg", "w") as f:
            f.write(networks_config)
            
        # ZeekControl configuration  
        zeekctl_config = f"""ZeekVersion = 8.1.0-dev.612
                    ZeekPort = 47761
                    ZeekUser = root
                    ZeekGroup = root
                    SpoolDir = /opt/zeek/spool
                    LogDir = /opt/zeek/logs
                    """
        
        with open(f"{self.zeek_config_dir}/zeekctl.cfg", "w") as f:
            f.write(zeekctl_config)
            
        logger.info("Created Zeek configuration files")
        
    def start_zeek_live_capture(self):
        """Start Zeek in live capture mode"""
        try:
            # Start Zeek with your network interface
            cmd = [
                "sudo", self.zeek_bin,
                "-i", self.interface,
                "-C",  # Ignore checksum errors
                f"LogAscii::output_to_stdout=F",
                f"Log::default_logdir={self.zeek_log_dir}/current"
            ]
            
            logger.info(f"Starting Zeek with command: {' '.join(cmd)}")
            
            # Start Zeek as background process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            
            # Wait a bit and check if process started successfully
            time.sleep(3)
            if process.poll() is None:
                logger.info(f"✅ Zeek started successfully with PID: {process.pid}")
                
                # Save PID for later management
                with open("/tmp/zeek_capture.pid", "w") as f:
                    f.write(str(process.pid))
                    
                return True
            else:
                stdout, stderr = process.communicate()
                logger.error(f"❌ Failed to start Zeek: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting Zeek: {e}")
            return False
            
    def stop_zeek(self):
        """Stop Zeek process"""
        try:
            if os.path.exists("/tmp/zeek_capture.pid"):
                with open("/tmp/zeek_capture.pid", "r") as f:
                    pid = int(f.read().strip())
                    
                os.system(f"sudo kill -TERM {pid}")
                os.remove("/tmp/zeek_capture.pid")
                logger.info("✅ Zeek stopped successfully")
                return True
        except Exception as e:
            logger.error(f"Error stopping Zeek: {e}")
            return False
            
    def is_zeek_running(self):
        """Check if Zeek is running"""
        try:
            if os.path.exists("/tmp/zeek_capture.pid"):
                with open("/tmp/zeek_capture.pid", "r") as f:
                    pid = int(f.read().strip())
                    
                # Check if process exists
                return os.path.exists(f"/proc/{pid}")
        except:
            pass
        return False
        
    def get_zeek_log_files(self):
        """Get list of current Zeek log files"""
        current_dir = f"{self.zeek_log_dir}/current"
        if not os.path.exists(current_dir):
            return []
            
        log_files = []
        for file in os.listdir(current_dir):
            if file.endswith('.log'):
                log_files.append(os.path.join(current_dir, file))
                
        return log_files

def main():
    """Main function to manage Zeek"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Zeek Integration Manager")
    parser.add_argument("action", choices=["start", "stop", "status", "setup"], 
                       help="Action to perform")
    
    args = parser.parse_args()
    
    manager = ZeekManager()
    
    if args.action == "setup":
        print("🔧 Setting up Zeek directories and configuration...")
        manager.setup_zeek_directories()
        manager.create_zeek_config()
        print("✅ Zeek setup completed!")
        
    elif args.action == "start":
        print("🚀 Starting Zeek live capture...")
        if manager.start_zeek_live_capture():
            print("✅ Zeek started successfully!")
            print(f"📁 Logs will be written to: {manager.zeek_log_dir}/current/")
        else:
            print("❌ Failed to start Zeek")
            
    elif args.action == "stop":
        print("🛑 Stopping Zeek...")
        if manager.stop_zeek():
            print("✅ Zeek stopped successfully!")
        else:
            print("❌ Failed to stop Zeek")
            
    elif args.action == "status":
        print("📊 Checking Zeek status...")
        if manager.is_zeek_running():
            print("✅ Zeek is running")
            log_files = manager.get_zeek_log_files()
            print(f"📁 Active log files: {len(log_files)}")
            for log_file in log_files[:5]:  # Show first 5
                print(f"   - {log_file}")
        else:
            print("❌ Zeek is not running")

if __name__ == "__main__":
    main()
