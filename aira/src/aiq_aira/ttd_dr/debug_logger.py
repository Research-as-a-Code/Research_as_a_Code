"""
TTD-DR Debug Logger - Persistent logging for debugging variable flow

Logs to file that survives pod restarts/timeouts for post-analysis.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


class TTDDRDebugLogger:
    """Persistent debug logger for TTD-DR pipeline."""
    
    def __init__(self, log_dir: str = "/tmp/ttd_dr_debug"):
        """Initialize with persistent log directory."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"ttd_dr_session_{self.current_session}.jsonl"
        self.logger = logging.getLogger(__name__)
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Log an event to persistent storage.
        
        Args:
            event_type: Type of event (stage_start, llm_call, iteration, etc.)
            data: Event data to log
        """
        try:
            event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                **data
            }
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
                
        except Exception as e:
            self.logger.error(f"Failed to write debug log: {e}")
    
    def log_stage(self, stage: str, iteration: int = 0, **kwargs):
        """Log a stage transition."""
        self.log_event("stage", {
            "stage": stage,
            "iteration": iteration,
            **kwargs
        })
    
    def log_llm_call(self, location: str, prompt_preview: str, response_preview: str, **kwargs):
        """Log an LLM call with input/output."""
        self.log_event("llm_call", {
            "location": location,
            "prompt_preview": prompt_preview[:500],  # First 500 chars
            "response_preview": response_preview[:500],
            **kwargs
        })
    
    def log_variable(self, var_name: str, var_value: Any, location: str):
        """Log a variable's value at a specific location."""
        # Convert to string, handle complex types
        if isinstance(var_value, (str, int, float, bool)):
            value_str = str(var_value)[:500]
        elif isinstance(var_value, dict):
            value_str = json.dumps(var_value, default=str)[:500]
        elif hasattr(var_value, 'to_dict'):
            value_str = json.dumps(var_value.to_dict(), default=str)[:500]
        else:
            value_str = str(var_value)[:500]
        
        self.log_event("variable", {
            "name": var_name,
            "value": value_str,
            "location": location
        })
    
    def log_error(self, error: Exception, location: str, **kwargs):
        """Log an error with context."""
        self.log_event("error", {
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],
            "location": location,
            **kwargs
        })
    
    def get_log_path(self) -> str:
        """Return path to current log file."""
        return str(self.log_file)

