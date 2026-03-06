""" state_machine

State machine for run/step lifecycle.
"""

from typing import Optional
from enum import Enum

from app.kernel.trace.models import Run, RunStep


class RunStatus(Enum):
    """Run status enum."""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class StepStatus(Enum):
    """Step status enum."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELED = "canceled"


class StateMachine:
    """State machine for run/step transitions."""
    
    # Valid transitions
    RUN_TRANSITIONS = {
        RunStatus.QUEUED: [RunStatus.RUNNING, RunStatus.CANCELED],
        RunStatus.RUNNING: [RunStatus.PAUSED, RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED],
        RunStatus.PAUSED: [RunStatus.RUNNING, RunStatus.CANCELED],
        RunStatus.SUCCEEDED: [],
        RunStatus.FAILED: [],
        RunStatus.CANCELED: [],
    }
    
    STEP_TRANSITIONS = {
        StepStatus.QUEUED: [StepStatus.RUNNING, StepStatus.SKIPPED, StepStatus.CANCELED],
        StepStatus.RUNNING: [StepStatus.SUCCEEDED, StepStatus.FAILED, StepStatus.CANCELED],
        StepStatus.SUCCEEDED: [],
        StepStatus.FAILED: [],
        StepStatus.SKIPPED: [],
        StepStatus.CANCELED: [],
    }
    
    @classmethod
    def can_transition_run(cls, current: str, target: str) -> bool:
        """Check if run can transition from current to target status.
        
        Args:
            current: Current status.
            target: Target status.
            
        Returns:
            True if transition is valid.
        """
        current_enum = RunStatus(current)
        target_enum = RunStatus(target)
        return target_enum in cls.RUN_TRANSITIONS.get(current_enum, [])
    
    @classmethod
    def can_transition_step(cls, current: str, target: str) -> bool:
        """Check if step can transition from current to target status.
        
        Args:
            current: Current status.
            target: Target status.
            
        Returns:
            True if transition is valid.
        """
        current_enum = StepStatus(current)
        target_enum = StepStatus(target)
        return target_enum in cls.STEP_TRANSITIONS.get(current_enum, [])
    
    @classmethod
    def transition_run(cls, run: Run, target_status: str) -> Run:
        """Transition run to target status.
        
        Args:
            run: Run instance.
            target_status: Target status.
            
        Returns:
            Updated run.
            
        Raises:
            ValueError: If transition is invalid.
        """
        if not cls.can_transition_run(run.status, target_status):
            raise ValueError(
                f"Invalid transition: {run.status} -> {target_status}"
            )
        run.status = target_status
        return run
    
    @classmethod
    def transition_step(cls, step: RunStep, target_status: str) -> RunStep:
        """Transition step to target status.
        
        Args:
            step: Step instance.
            target_status: Target status.
            
        Returns:
            Updated step.
            
        Raises:
            ValueError: If transition is invalid.
        """
        if not cls.can_transition_step(step.status, target_status):
            raise ValueError(
                f"Invalid transition: {step.status} -> {target_status}"
            )
        step.status = target_status
        return step
