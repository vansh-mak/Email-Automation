import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from database import crud
from schemas.automation import (
    StartJobRequest,
    StartJobResponse,
    JobStatusResponse,
    ResumeJobResponse,
    DeleteCredentialResponse
)
from services.job_registry import job_registry, ActiveJob
from services.orchestrator import run_orchestrated_workflow

router = APIRouter(prefix="/automation", tags=["Automation"])

@router.post("/start", response_model=StartJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_automation(request: StartJobRequest, db: AsyncSession = Depends(get_db)):
    """
    Accept username and password or full SignupInput, create a unique job ID, and initialize the background workflow.
    """
    job_id = str(uuid.uuid4())
    username = request.username or (request.signup_data.preferred_username if request.signup_data else "new_user")
    password = request.password or (request.signup_data.password if request.signup_data else "")

    # 1. Persist initial Job record in SQLite
    await crud.create_job(db, username=username, job_id=job_id)

    # 2. Register ActiveJob in volatile memory for execution
    active_job = ActiveJob(
        job_id=job_id,
        username=username,
        password=password,
        signup_input=request.signup_data,
        first_name=request.signup_data.first_name if request.signup_data else (request.first_name or "Alex"),
        last_name=request.signup_data.last_name if request.signup_data else (request.last_name or "Smith"),
        target_url=request.target_url,
        status="RUNNING",
        current_step="INITIALIZING"
    )
    job_registry.register(active_job)

    # 3. Spawn background execution task
    task = asyncio.create_task(run_orchestrated_workflow(job_id))
    active_job.task = task

    return StartJobResponse(
        job_id=job_id,
        status="RUNNING",
        message="Automation workflow started successfully."
    )

@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_automation_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Query the current status, step, and human-intervention requirements of a job.
    """
    job = await crud.get_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found."
        )

    # If job is currently active in memory, reflect real-time active status
    active = job_registry.get(job_id)
    current_status = active.status if active else job.status
    current_step = active.current_step if active else job.current_step
    current_username = active.username if active else job.username
    intervention_req = active.manual_intervention_required if active else job.manual_intervention_required
    err_msg = active.error_message if active else job.error_message

    import json
    completed = sorted(list(active.completed_steps)) if active else json.loads(job.completed_steps or "[]")

    return JobStatusResponse(
        job_id=job.id,
        username=current_username,
        status=current_status,
        current_step=current_step,
        manual_intervention_required=intervention_req,
        completed_steps=completed,
        error_message=err_msg,
        created_at=job.created_at,
        updated_at=job.updated_at
    )

@router.post("/resume/{job_id}", response_model=ResumeJobResponse)
async def resume_automation(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Allow the user to resume a paused workflow after completing required manual interactions.
    """
    active = job_registry.get(job_id)
    if not active:
        job = await crud.get_job(db, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID '{job_id}' not found."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' is not currently active in memory."
        )

    if active.status != "WAITING_FOR_USER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' is not in WAITING_FOR_USER state (current status: {active.status})."
        )

    # Signal the event to resume execution
    job_registry.resume(job_id)

    return ResumeJobResponse(
        job_id=job_id,
        status="RUNNING",
        message="Workflow resumed successfully."
    )

@router.delete("/credentials/{username}", response_model=DeleteCredentialResponse)
async def delete_saved_credentials(username: str, db: AsyncSession = Depends(get_db)):
    """
    Delete stored credentials for a given username.
    """
    deleted = await crud.delete_credential(db, username)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stored credentials found for username '{username}'."
        )

    return DeleteCredentialResponse(
        username=username,
        deleted=True,
        message=f"Credentials for '{username}' successfully deleted."
    )
