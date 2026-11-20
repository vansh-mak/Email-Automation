import asyncio
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, field
from schemas.automation import SignupInput

@dataclass
class ActiveJob:
    job_id: str
    username: str
    password: str  # Held transiently in volatile memory for active browser fill
    signup_input: Optional[SignupInput] = None
    first_name: str = "Alex"
    last_name: str = "Smith"
    target_url: Optional[str] = None
    status: str = "PENDING"
    current_step: str = "INITIALIZING"
    manual_intervention_required: bool = False
    error_message: Optional[str] = None
    resume_event: asyncio.Event = field(default_factory=asyncio.Event)
    task: Optional[asyncio.Task] = None
    page: Optional[Any] = None  # Reference to the active browser page
    completed_steps: Set[str] = field(default_factory=set)

class JobRegistry:
    """In-memory registry for tracking active jobs and synchronization events."""
    def __init__(self):
        self._jobs: Dict[str, ActiveJob] = {}

    def register(self, job: ActiveJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Optional[ActiveJob]:
        return self._jobs.get(job_id)

    def resume(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job and job.status == "WAITING_FOR_USER":
            job.resume_event.set()
            return True
        return False

    def remove(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)

job_registry = JobRegistry()
