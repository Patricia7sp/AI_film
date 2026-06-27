#!/usr/bin/env python3
"""
Dagster Pipeline Trigger Agent
Triggers and monitors Dagster pipeline execution via GraphQL API
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("❌ ERROR: 'requests' module not found. Installing...")
    os.system("pip install requests")
    import requests


class DagsterTriggerAgent:
    """Agent for triggering and monitoring Dagster pipelines"""
    
    def __init__(self, dagster_url: str, comfyui_url: str):
        self.dagster_url = dagster_url.rstrip('/')
        self.comfyui_url = comfyui_url
        self.graphql_url = f"{self.dagster_url}/graphql"
        
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        sys.stdout.flush()
    
    def test_dagster_connection(self) -> bool:
        """Test if Dagster is accessible"""
        try:
            self.log("🔍 Testing Dagster connection...")
            response = requests.get(
                f"{self.dagster_url}/server_info",
                timeout=10
            )
            
            if response.status_code == 200:
                self.log(f"✅ Dagster is accessible at {self.dagster_url}")
                return True
            else:
                self.log(f"⚠️ Dagster returned status {response.status_code}", "WARN")
                return False
                
        except requests.exceptions.ConnectionError:
            self.log("❌ Cannot connect to Dagster. Is it running?", "ERROR")
            self.log(f"💡 Expected URL: {self.dagster_url}", "INFO")
            return False
        except Exception as e:
            self.log(f"❌ Error testing Dagster connection: {e}", "ERROR")
            return False
    
    def trigger_pipeline(self, pipeline_name: str = "ai_film_pipeline") -> Optional[str]:
        """
        Trigger Dagster pipeline execution via GraphQL
        Returns run_id if successful
        """
        try:
            self.log(f"🚀 Triggering Dagster pipeline: {pipeline_name}")
            
            # GraphQL mutation to launch pipeline
            mutation = """
            mutation LaunchPipeline($runConfigData: RunConfigData!) {
              launchPipelineExecution(
                executionParams: {
                  selector: {
                    repositoryLocationName: "ai_film_pipeline"
                    repositoryName: "ai_film_pipeline"
                    pipelineName: "ai_film_pipeline"
                  }
                  runConfigData: $runConfigData
                }
              ) {
                __typename
                ... on LaunchRunSuccess {
                  run {
                    runId
                    pipelineName
                    status
                  }
                }
                ... on PythonError {
                  message
                  stack
                }
              }
            }
            """
            
            # Run configuration with ComfyUI URL
            run_config = {
                "ops": {
                    "multimodal_input_asset": {
                        "config": {
                            "session_id": f"cicd_{int(time.time())}",
                            "comfyui_url": self.comfyui_url,
                            "input_type": "text",
                            "max_scenes": 8,
                            "quality_threshold": 0.9
                        }
                    }
                }
            }
            
            variables = {
                "runConfigData": run_config
            }
            
            response = requests.post(
                self.graphql_url,
                json={"query": mutation, "variables": variables},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                self.log(f"❌ GraphQL request failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
            
            result = response.json()
            
            if "errors" in result:
                self.log(f"❌ GraphQL errors: {result['errors']}", "ERROR")
                return None
            
            data = result.get("data", {}).get("launchPipelineExecution", {})
            
            if data.get("__typename") == "LaunchRunSuccess":
                run_id = data["run"]["runId"]
                self.log(f"✅ Pipeline launched successfully!")
                self.log(f"📊 Run ID: {run_id}")
                return run_id
            elif data.get("__typename") == "PythonError":
                self.log(f"❌ Python error: {data.get('message')}", "ERROR")
                return None
            else:
                self.log(f"❌ Unexpected response: {data}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Error triggering pipeline: {e}", "ERROR")
            return None
    
    def get_run_status(self, run_id: str) -> Optional[str]:
        """
        Get current status of a pipeline run
        Returns: SUCCESS, FAILURE, STARTED, etc.
        """
        try:
            query = """
            query GetRunStatus($runId: ID!) {
              pipelineRunOrError(runId: $runId) {
                __typename
                ... on Run {
                  runId
                  status
                  stats {
                    __typename
                    ... on RunStatsSnapshot {
                      stepsSucceeded
                      stepsFailed
                      expectations
                      materializations
                    }
                  }
                }
              }
            }
            """
            
            variables = {"runId": run_id}
            
            response = requests.post(
                self.graphql_url,
                json={"query": query, "variables": variables},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            data = result.get("data", {}).get("pipelineRunOrError", {})
            
            if data.get("__typename") == "Run":
                status = data.get("status")
                stats = data.get("stats", {})
                
                if stats:
                    succeeded = stats.get("stepsSucceeded", 0)
                    failed = stats.get("stepsFailed", 0)
                    self.log(f"📊 Steps: {succeeded} succeeded, {failed} failed")
                
                return status
            
            return None
            
        except Exception as e:
            self.log(f"⚠️ Error getting run status: {e}", "WARN")
            return None
    
    def wait_for_completion(self, run_id: str, timeout: int = 1800, check_interval: int = 10) -> bool:
        """
        Wait for pipeline run to complete
        Returns True if successful, False otherwise
        """
        self.log(f"⏳ Aguardando conclusão do pipeline (timeout: {timeout}s)...")
        
        start_time = time.time()
        last_status = None
        
        while True:
            elapsed = int(time.time() - start_time)
            
            if elapsed > timeout:
                self.log(f"❌ Timeout after {elapsed}s", "ERROR")
                return False
            
            status = self.get_run_status(run_id)
            
            if status and status != last_status:
                self.log(f"📊 Status: {status} (elapsed: {elapsed}s)")
                last_status = status
            
            # Success states
            if status == "SUCCESS":
                self.log(f"✅ Pipeline completed successfully! (time: {elapsed}s)")
                return True
            
            # Failure states
            if status in ["FAILURE", "CANCELED"]:
                self.log(f"❌ Pipeline {status.lower()}! (time: {elapsed}s)", "ERROR")
                return False
            
            # Still running
            if status in ["STARTED", "STARTING", "NOT_STARTED"]:
                time.sleep(check_interval)
                continue
            
            # Unknown status
            if status is None:
                self.log(f"⚠️ Cannot get status, retrying...", "WARN")
                time.sleep(check_interval)
                continue
            
            # Other states
            self.log(f"⏳ Status: {status}, waiting...")
            time.sleep(check_interval)


def main():
    parser = argparse.ArgumentParser(description="Trigger Dagster Pipeline")
    parser.add_argument("--dagster-url", required=True, help="Dagster URL (e.g., http://localhost:3000)")
    parser.add_argument("--comfyui-url", required=True, help="ComfyUI endpoint URL")
    parser.add_argument("--pipeline-name", default="ai_film_pipeline", help="Pipeline name to trigger")
    parser.add_argument("--wait-completion", action="store_true", help="Wait for pipeline completion")
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout in seconds (default: 1800)")
    parser.add_argument("--check-interval", type=int, default=10, help="Status check interval (default: 10s)")
    
    args = parser.parse_args()
    
    # Initialize agent
    agent = DagsterTriggerAgent(
        dagster_url=args.dagster_url,
        comfyui_url=args.comfyui_url
    )
    
    agent.log("=" * 60)
    agent.log("📊 DAGSTER PIPELINE TRIGGER AGENT")
    agent.log("=" * 60)
    agent.log(f"Dagster URL: {args.dagster_url}")
    agent.log(f"ComfyUI URL: {args.comfyui_url}")
    agent.log(f"Pipeline: {args.pipeline_name}")
    agent.log("=" * 60)
    
    # Test connection
    if not agent.test_dagster_connection():
        agent.log("❌ Cannot connect to Dagster. Exiting.", "ERROR")
        agent.log("💡 Make sure Dagster is running and accessible", "INFO")
        sys.exit(1)
    
    # Trigger pipeline
    run_id = agent.trigger_pipeline(args.pipeline_name)
    
    if not run_id:
        agent.log("❌ Failed to trigger pipeline", "ERROR")
        sys.exit(1)
    
    # Export run_id for GitHub Actions
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"run_id={run_id}\n")
    
    # Wait for completion if requested
    if args.wait_completion:
        success = agent.wait_for_completion(
            run_id,
            timeout=args.timeout,
            check_interval=args.check_interval
        )
        
        if success:
            agent.log("🎉 Pipeline execution completed successfully!")
            
            # Export status
            if github_output:
                with open(github_output, "a") as f:
                    f.write("status=SUCCESS\n")
            
            sys.exit(0)
        else:
            agent.log("❌ Pipeline execution failed or timed out", "ERROR")
            
            # Export status
            if github_output:
                with open(github_output, "a") as f:
                    f.write("status=FAILURE\n")
            
            sys.exit(1)
    else:
        agent.log("✅ Pipeline triggered successfully (not waiting for completion)")
        sys.exit(0)


if __name__ == "__main__":
    main()
