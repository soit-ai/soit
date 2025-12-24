""" scheduler

Scheduling and concurrency primitives.
"""

import asyncio
from typing import Callable, Any, Optional
from concurrent.futures import ThreadPoolExecutor


class TaskScheduler:
    """Task scheduler for async execution."""
    
    def __init__(self, max_workers: int = 10):
        """Initialize scheduler.
        
        Args:
            max_workers: Maximum concurrent workers.
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def schedule(
        self,
        func: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Schedule a task for execution.
        
        Args:
            func: Function to execute.
            *args: Function arguments.
            **kwargs: Function keyword arguments.
            
        Returns:
            Function result.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    async def schedule_async(
        self,
        coro: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Schedule an async coroutine.
        
        Args:
            coro: Coroutine to execute.
            *args: Coroutine arguments.
            **kwargs: Coroutine keyword arguments.
            
        Returns:
            Coroutine result.
        """
        return await coro(*args, **kwargs)
    
    def shutdown(self) -> None:
        """Shutdown scheduler."""
        self.executor.shutdown(wait=True)


# Global scheduler instance
scheduler = TaskScheduler()
