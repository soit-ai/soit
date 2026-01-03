""" logging

Structured logging setup.
"""

import json
import logging
import sys
from typing import Any, Dict
from app.settings.settings import settings


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record.
            
        Returns:
            JSON string.
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "tenant_id"):
            log_data["tenant_id"] = record.tenant_id
        if hasattr(record, "workspace_id"):
            log_data["workspace_id"] = record.workspace_id
        if hasattr(record, "run_id"):
            log_data["run_id"] = record.run_id
        if hasattr(record, "step_id"):
            log_data["step_id"] = record.step_id
        
        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """Setup structured logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    root_logger.addHandler(handler)


# Setup on import
setup_logging()
