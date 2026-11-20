import uuid
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import JobRecord, CredentialRecord

async def create_job(db: AsyncSession, username: str, job_id: Optional[str] = None) -> JobRecord:
    """Create a new job record with initial PENDING status."""
    job = JobRecord(
        id=job_id or str(uuid.uuid4()),
        username=username,
        status="PENDING",
        current_step="INITIALIZING",
        manual_intervention_required=False,
        completed_steps="[]"
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

async def get_job(db: AsyncSession, job_id: str) -> Optional[JobRecord]:
    """Retrieve a job by its ID."""
    result = await db.execute(select(JobRecord).where(JobRecord.id == job_id))
    return result.scalar_one_or_none()

async def update_job(
    db: AsyncSession,
    job_id: str,
    status: Optional[str] = None,
    current_step: Optional[str] = None,
    manual_intervention_required: Optional[bool] = None,
    error_message: Optional[str] = None,
    completed_steps: Optional[str] = None,
    username: Optional[str] = None
) -> Optional[JobRecord]:
    """Update job status, step, manual intervention flags, and captured username."""
    job = await get_job(db, job_id)
    if not job:
        return None

    if username is not None:
        job.username = username
    if status is not None:
        job.status = status
    if current_step is not None:
        job.current_step = current_step
    if manual_intervention_required is not None:
        job.manual_intervention_required = manual_intervention_required
    if error_message is not None:
        job.error_message = error_message
    if completed_steps is not None:
        job.completed_steps = completed_steps

    await db.commit()
    await db.refresh(job)
    return job

async def save_credential(
    db: AsyncSession,
    username: str,
    encrypted_password: bytes,
    job_id: Optional[str] = None
) -> CredentialRecord:
    """
    Save encrypted credentials after successful registration.
    Upserts if username already exists.
    """
    existing = await get_credential(db, username)
    if existing:
        existing.encrypted_password = encrypted_password
        existing.job_id = job_id
        await db.commit()
        await db.refresh(existing)
        return existing

    credential = CredentialRecord(
        username=username,
        encrypted_password=encrypted_password,
        job_id=job_id
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential

async def get_credential(db: AsyncSession, username: str) -> Optional[CredentialRecord]:
    """Retrieve encrypted credential record for a username."""
    result = await db.execute(select(CredentialRecord).where(CredentialRecord.username == username))
    return result.scalar_one_or_none()

async def delete_credential(db: AsyncSession, username: str) -> bool:
    """Delete a stored credential record."""
    result = await db.execute(delete(CredentialRecord).where(CredentialRecord.username == username))
    await db.commit()
    return result.rowcount > 0
