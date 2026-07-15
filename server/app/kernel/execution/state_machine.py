""" state_machine

State machine for run/step lifecycle.
"""

from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.status import (
    ExecutionStatus,
    RuntimeTransitionError,
    validate_run_transition,
    validate_step_transition,
)
from app.kernel.runtime.status import (
    StepStatus as StepStatus,
)

RunStatus = ExecutionStatus


class StateMachine:
    """State machine for run/step transitions."""

    @classmethod
    def can_transition_run(cls, current: str, target: str) -> bool:
        """Check if run can transition from current to target status.

        Args:
            current: Current status.
            target: Target status.

        Returns:
            True if transition is valid.
        """
        try:
            validate_run_transition(current, target)
            return current != target
        except RuntimeTransitionError:
            return False

    @classmethod
    def can_transition_step(cls, current: str, target: str) -> bool:
        """Check if step can transition from current to target status.

        Args:
            current: Current status.
            target: Target status.

        Returns:
            True if transition is valid.
        """
        try:
            validate_step_transition(current, target)
            return current != target
        except RuntimeTransitionError:
            return False

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
        run.status = validate_run_transition(run.status, target_status)
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
        step.status = validate_step_transition(step.status, target_status)
        return step
