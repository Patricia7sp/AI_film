#!/usr/bin/env python3
"""
Automatic Story Upload Script
Uploads story file to Flask API and triggers pipeline execution
"""

import os
import sys
import requests
import argparse
import time
import json
from datetime import datetime
from pathlib import Path


class StoryUploader:
    """Automatically uploads story file to Flask API"""
    
    def __init__(self, flask_url: str, story_file: str):
        self.flask_url = flask_url.rstrip('/')
        self.story_file = story_file
        self.api_endpoint = f"{self.flask_url}/api/start"
        
    def log(self, message: str, level: str = "INFO"):
        """Log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
        sys.stdout.flush()
    
    def read_story_file(self) -> str:
        """Read story file content"""
        try:
            self.log(f"📖 Reading story file: {self.story_file}")
            
            if not os.path.exists(self.story_file):
                self.log(f"❌ Story file not found: {self.story_file}", "ERROR")
                return None
            
            with open(self.story_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.log(f"✅ Story loaded: {len(content)} characters")
            self.log(f"📝 First 100 chars: {content[:100]}...")
            
            return content
            
        except Exception as e:
            self.log(f"❌ Error reading story file: {e}", "ERROR")
            return None
    
    def upload_via_file(self) -> dict:
        """Upload story as file (multipart/form-data)"""
        try:
            self.log("📤 Uploading story as file...")
            
            with open(self.story_file, 'rb') as f:
                files = {'story_file': (os.path.basename(self.story_file), f, 'text/plain')}
                
                self.log(f"POST {self.api_endpoint}")
                response = requests.post(
                    self.api_endpoint,
                    files=files,
                    timeout=30
                )
            
            self.log(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                self.log("✅ File upload successful!")
                return response.json()
            else:
                self.log(f"❌ Upload failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Error uploading file: {e}", "ERROR")
            return None
    
    def upload_via_json(self, story_text: str) -> dict:
        """Upload story as JSON"""
        try:
            self.log("📤 Uploading story as JSON...")
            
            payload = {
                "story_text": story_text
            }
            
            self.log(f"POST {self.api_endpoint}")
            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            self.log(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                self.log("✅ JSON upload successful!")
                return response.json()
            else:
                self.log(f"❌ Upload failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Error uploading JSON: {e}", "ERROR")
            return None
    
    def upload_via_form(self, story_text: str) -> dict:
        """Upload story as form data"""
        try:
            self.log("📤 Uploading story as form data...")
            
            data = {
                "story_text": story_text
            }
            
            self.log(f"POST {self.api_endpoint}")
            response = requests.post(
                self.api_endpoint,
                data=data,
                timeout=30
            )
            
            self.log(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                self.log("✅ Form upload successful!")
                return response.json()
            else:
                self.log(f"❌ Upload failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log(f"❌ Error uploading form: {e}", "ERROR")
            return None
    
    def upload(self, method: str = "file") -> dict:
        """
        Upload story using specified method
        Methods: file, json, form
        """
        self.log("=" * 60)
        self.log(f"🚀 Starting story upload (method: {method})")
        self.log("=" * 60)
        
        # Try file upload first (most natural)
        if method == "file":
            result = self.upload_via_file()
            if result:
                return result
            
            # Fallback to JSON if file upload fails
            self.log("⚠️ File upload failed, trying JSON...", "WARN")
            method = "json"
        
        # Read story text for JSON/form methods
        story_text = self.read_story_file()
        if not story_text:
            return None
        
        # Try JSON
        if method == "json":
            result = self.upload_via_json(story_text)
            if result:
                return result
            
            # Fallback to form
            self.log("⚠️ JSON upload failed, trying form data...", "WARN")
            method = "form"
        
        # Try form data
        if method == "form":
            result = self.upload_via_form(story_text)
            if result:
                return result
        
        self.log("❌ All upload methods failed", "ERROR")
        return None
    
    def export_result(self, result: dict):
        """Export result to GitHub Actions"""
        if not result:
            return
        
        session_id = result.get('session_id')
        message = result.get('message')
        
        self.log(f"📊 Upload Result:")
        self.log(f"   Session ID: {session_id}")
        self.log(f"   Message: {message}")
        
        # Export to GitHub Actions
        github_output = os.getenv("GITHUB_OUTPUT")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"session_id={session_id}\n")
                f.write(f"upload_status=success\n")
            
            self.log("✅ Results exported to GitHub Actions")


def main():
    parser = argparse.ArgumentParser(description="Upload story to Flask API")
    parser.add_argument("--flask-url", required=True, help="Flask server URL (e.g., http://localhost:5001)")
    parser.add_argument("--story-file", required=True, help="Path to story file")
    parser.add_argument("--method", default="file", choices=["file", "json", "form"], 
                       help="Upload method (default: file)")
    parser.add_argument("--retry", type=int, default=3, help="Number of retries (default: 3)")
    parser.add_argument("--retry-delay", type=int, default=5, help="Delay between retries in seconds (default: 5)")
    
    args = parser.parse_args()
    
    uploader = StoryUploader(
        flask_url=args.flask_url,
        story_file=args.story_file
    )
    
    uploader.log("=" * 60)
    uploader.log("📤 AUTOMATIC STORY UPLOADER")
    uploader.log("=" * 60)
    uploader.log(f"Flask URL: {args.flask_url}")
    uploader.log(f"Story File: {args.story_file}")
    uploader.log(f"Method: {args.method}")
    uploader.log("=" * 60)
    
    # Retry logic
    result = None
    for attempt in range(1, args.retry + 1):
        if attempt > 1:
            uploader.log(f"⏳ Retry attempt {attempt}/{args.retry}...")
            time.sleep(args.retry_delay)
        
        result = uploader.upload(method=args.method)
        
        if result:
            break
    
    if not result:
        uploader.log("❌ Upload failed after all retries", "ERROR")
        sys.exit(1)
    
    # Export result
    uploader.export_result(result)
    
    uploader.log("=" * 60)
    uploader.log("✅ STORY UPLOADED SUCCESSFULLY!")
    uploader.log("✅ Pipeline execution started!")
    uploader.log("=" * 60)


if __name__ == "__main__":
    main()
