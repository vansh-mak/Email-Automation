import pytest
import pytest_asyncio
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from main import app
from database.session import init_db
from services.job_registry import job_registry, ActiveJob

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()

@pytest.mark.asyncio
async def test_health_route():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "app" in data

@pytest.mark.asyncio
async def test_start_automation_route():
    transport = ASGITransport(app=app)
    # Mock orchestrator background task to test the API route in isolation
    with patch("routes.automation.run_orchestrated_workflow") as mock_orchestrator:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "username": "alex.test.dev",
                "password": "Password123!",
                "first_name": "Alex",
                "last_name": "Smith"
            }
            resp = await client.post("/automation/start", json=payload)
            assert resp.status_code == 202
            data = resp.json()
            assert "job_id" in data
            assert data["status"] == "RUNNING"

            # Query status
            status_resp = await client.get(f"/automation/status/{data['job_id']}")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert status_data["job_id"] == data["job_id"]
            assert status_data["username"] == "alex.test.dev"

@pytest.mark.asyncio
async def test_resume_not_in_waiting_state():
    job = ActiveJob(job_id="running-job-1", username="testuser", password="pwd", status="RUNNING")
    job_registry.register(job)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/automation/resume/running-job-1")
        assert resp.status_code == 400
        assert "WAITING_FOR_USER" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_resume_waiting_job_success():
    job = ActiveJob(
        job_id="waiting-job-2",
        username="testuser2",
        password="pwd",
        status="WAITING_FOR_USER",
        manual_intervention_required=True
    )
    job_registry.register(job)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/automation/resume/waiting-job-2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "RUNNING"
        assert data["job_id"] == "waiting-job-2"
        assert job.resume_event.is_set()
