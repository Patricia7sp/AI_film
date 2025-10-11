#!/usr/bin/env python3
"""
Service Starter Script
Starts Dagster and Flask services in background for CI/CD automation
"""

import os
import sys
import subprocess
import time
import requests
import argparse
from datetime import datetime


class ServiceStarter:
    """Starts and monitors Dagster + Flask services"""
    
    def __init__(self, dagster_port=3000, flask_port=5001):
        self.dagster_port = dagster_port
        self.flask_port = flask_port
        self.dagster_process = None
        self.flask_process = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        sys.stdout.flush()
    
    def start_dagster(self, workspace_path: str = "open3d_implementation/orchestration") -> bool:
        """Start Dagster webserver"""
        try:
            self.log(f"🚀 Starting Dagster webserver on port {self.dagster_port}...")
            
            # Change to workspace directory
            if not os.path.exists(workspace_path):
                self.log(f"❌ Workspace path not found: {workspace_path}", "ERROR")
                return False
            
            # Start Dagster in background
            dagster_cmd = [
                "dagster",
                "dev",
                "-p", str(self.dagster_port),
                "-f", "dagster_pipeline.py"
            ]
            
            self.log(f"Command: {' '.join(dagster_cmd)}")
            self.log(f"Working dir: {workspace_path}")
            
            self.dagster_process = subprocess.Popen(
                dagster_cmd,
                cwd=workspace_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.log(f"✅ Dagster process started (PID: {self.dagster_process.pid})")
            
            # Write PID to file for cleanup
            with open("/tmp/dagster.pid", "w") as f:
                f.write(str(self.dagster_process.pid))
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error starting Dagster: {e}", "ERROR")
            return False
    
    def start_flask(self) -> bool:
        """Start Flask server"""
        try:
            self.log(f"🚀 Starting Flask server on port {self.flask_port}...")
            
            # Start Flask in background
            flask_cmd = [
                sys.executable,  # Current Python interpreter
                "app.py"
            ]
            
            self.flask_process = subprocess.Popen(
                flask_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "FLASK_ENV": "production"}
            )
            
            self.log(f"✅ Flask process started (PID: {self.flask_process.pid})")
            
            # Write PID to file for cleanup
            with open("/tmp/flask.pid", "w") as f:
                f.write(str(self.flask_process.pid))
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error starting Flask: {e}", "ERROR")
            return False
    
    def wait_for_service(self, url: str, service_name: str, max_attempts: int = 30, delay: int = 2) -> bool:
        """Wait for service to be ready"""
        self.log(f"⏳ Waiting for {service_name} to be ready...")
        
        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.get(url, timeout=5)
                if response.status_code in [200, 404]:  # 404 is ok for some endpoints
                    self.log(f"✅ {service_name} is ready! (attempt {attempt}/{max_attempts})")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            if attempt % 5 == 0:
                self.log(f"⏳ Still waiting for {service_name}... (attempt {attempt}/{max_attempts})")
            
            time.sleep(delay)
        
        self.log(f"❌ {service_name} did not become ready in time", "ERROR")
        return False
    
    def check_process_status(self):
        """Check if processes are still running"""
        dagster_running = self.dagster_process and self.dagster_process.poll() is None
        flask_running = self.flask_process and self.flask_process.poll() is None
        
        self.log(f"📊 Process Status:")
        self.log(f"   Dagster: {'✅ Running' if dagster_running else '❌ Stopped'}")
        self.log(f"   Flask: {'✅ Running' if flask_running else '❌ Stopped'}")
        
        return dagster_running and flask_running
    
    def export_urls(self):
        """Export service URLs to GitHub Actions"""
        dagster_url = f"http://localhost:{self.dagster_port}"
        flask_url = f"http://localhost:{self.flask_port}"
        
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"dagster_url={dagster_url}\n")
                f.write(f"flask_url={flask_url}\n")
            
            self.log(f"✅ URLs exported to GitHub Actions")
        
        self.log(f"📊 Service URLs:")
        self.log(f"   Dagster: {dagster_url}")
        self.log(f"   Flask: {flask_url}")


def main():
    parser = argparse.ArgumentParser(description="Start Dagster + Flask services")
    parser.add_argument("--dagster-port", type=int, default=3000, help="Dagster port (default: 3000)")
    parser.add_argument("--flask-port", type=int, default=5001, help="Flask port (default: 5001)")
    parser.add_argument("--workspace", default="open3d_implementation/orchestration", help="Dagster workspace path")
    parser.add_argument("--wait", action="store_true", help="Wait for services to be ready")
    parser.add_argument("--max-wait", type=int, default=60, help="Max wait time in seconds (default: 60)")
    
    args = parser.parse_args()
    
    starter = ServiceStarter(
        dagster_port=args.dagster_port,
        flask_port=args.flask_port
    )
    
    starter.log("=" * 60)
    starter.log("🚀 SERVICE STARTER")
    starter.log("=" * 60)
    
    # Start Dagster
    if not starter.start_dagster(args.workspace):
        starter.log("❌ Failed to start Dagster", "ERROR")
        sys.exit(1)
    
    # Start Flask
    if not starter.start_flask():
        starter.log("❌ Failed to start Flask", "ERROR")
        sys.exit(1)
    
    starter.log("=" * 60)
    
    # Wait for services if requested
    if args.wait:
        dagster_url = f"http://localhost:{args.dagster_port}/server_info"
        flask_url = f"http://localhost:{args.flask_port}/"
        
        max_attempts = args.max_wait // 2  # 2 second delay per attempt
        
        dagster_ready = starter.wait_for_service(dagster_url, "Dagster", max_attempts)
        flask_ready = starter.wait_for_service(flask_url, "Flask", max_attempts)
        
        if not (dagster_ready and flask_ready):
            starter.log("❌ One or more services failed to start", "ERROR")
            sys.exit(1)
        
        # Check process status
        if not starter.check_process_status():
            starter.log("❌ One or more processes died", "ERROR")
            sys.exit(1)
    
    # Export URLs
    starter.export_urls()
    
    starter.log("=" * 60)
    starter.log("✅ ALL SERVICES STARTED SUCCESSFULLY!")
    starter.log("=" * 60)
    starter.log("💡 Services are running in background")
    starter.log("💡 PID files: /tmp/dagster.pid, /tmp/flask.pid")
    starter.log("=" * 60)


if __name__ == "__main__":
    main()
