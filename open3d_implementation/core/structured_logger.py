"""
Structured Logger for AI Film Pipeline
Provides detailed logging with context and metadata
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class StructuredLogger:
    """
    Structured logger with JSON output and context tracking
    """
    
    def __init__(self, session_id: str, output_dir: str = "."):
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self.log_file = self.output_dir / f"pipeline_{session_id}.log"
        
        # Setup logging
        self.logger = logging.getLogger(f"pipeline.{session_id}")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def log_workflow_stage(self, stage: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a workflow stage"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "stage": stage,
            "metadata": metadata or {}
        }
        self.logger.info(json.dumps(log_entry))
        print(f"📝 {stage}")
    
    def log_error(self, error: str, context: Optional[Dict[str, Any]] = None):
        """Log an error"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "error": error,
            "context": context or {}
        }
        self.logger.error(json.dumps(log_entry))
        print(f"❌ {error}")
    
    def log_success(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a success"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "message": message,
            "metadata": metadata or {}
        }
        self.logger.info(json.dumps(log_entry))
        print(f"✅ {message}")
