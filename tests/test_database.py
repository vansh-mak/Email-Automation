import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, JobRecord, CredentialRecord
from database.crud import (
    create_job,
    get_job,
    update_job,
    save_credential,
    get_credential,
    delete_credential
)
from security.encryption import generate_key, encrypt_password, decrypt_password

@pytest_asyncio.fixture
async def db_session():
    """Provides an isolated in-memory SQLite database session for unit testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()

@pytest.mark.asyncio
async def test_job_crud_lifecycle(db_session):
    # 1. Create Job
    job = await create_job(db_session, username="alex.smith", job_id="test-job-123")
    assert job.id == "test-job-123"
    assert job.username == "alex.smith"
    assert job.status == "PENDING"
    assert job.current_step == "INITIALIZING"
    assert job.manual_intervention_required is False

    # 2. Get Job
    retrieved = await get_job(db_session, "test-job-123")
    assert retrieved is not None
    assert retrieved.id == "test-job-123"

    # 3. Update Job
    updated = await update_job(
        db_session,
        job_id="test-job-123",
        status="WAITING_FOR_USER",
        current_step="CHALLENGE_DETECTED",
        manual_intervention_required=True
    )
    assert updated.status == "WAITING_FOR_USER"
    assert updated.current_step == "CHALLENGE_DETECTED"
    assert updated.manual_intervention_required is True

@pytest.mark.asyncio
async def test_credential_encryption_storage(db_session):
    key = generate_key()
    raw_password = "SecurePassword2026!"
    encrypted = encrypt_password(raw_password, key)

    # Save encrypted credential
    cred = await save_credential(
        db_session,
        username="alex.smith",
        encrypted_password=encrypted,
        job_id="test-job-123"
    )
    assert cred.username == "alex.smith"
    assert cred.encrypted_password == encrypted
    assert cred.encrypted_password != raw_password.encode("utf-8")

    # Retrieve and decrypt
    retrieved = await get_credential(db_session, "alex.smith")
    assert retrieved is not None
    decrypted = decrypt_password(retrieved.encrypted_password, key)
    assert decrypted == raw_password

    # Delete credential
    deleted = await delete_credential(db_session, "alex.smith")
    assert deleted is True

    # Verify gone
    assert await get_credential(db_session, "alex.smith") is None
