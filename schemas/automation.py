from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class SignupInput(BaseModel):
    first_name: str = Field(default="Alex", min_length=1, description="First name")
    last_name: str = Field(default="Smith", min_length=1, description="Last name")
    birth_day: int = Field(default=15, ge=1, le=31, description="Day of birth (1-31)")
    birth_month: str = Field(default="January", description="Month of birth (e.g. 'January' or '1')")
    birth_year: int = Field(default=1995, ge=1900, le=2020, description="Year of birth (YYYY)")
    gender: str = Field(default="female", description="Gender (e.g. 'female', 'male', 'rather not say')")
    password: str = Field(..., min_length=6, description="Account password")
    confirm_password: Optional[str] = Field(default=None, description="Password confirmation")
    preferred_username: Optional[str] = Field(default=None, description="Preferred handle identifier")

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.confirm_password and self.password != self.confirm_password:
            raise ValueError("Password and confirmation password do not match.")
        return self

class StartJobRequest(BaseModel):
    # Comprehensive signup details
    signup_data: Optional[SignupInput] = None

    # Top-level parameters for backward compatibility
    username: Optional[str] = Field(default=None, description="Desired email username or account handle")
    password: Optional[str] = Field(default=None, description="Account password")
    first_name: Optional[str] = Field(default="Alex", description="First name")
    last_name: Optional[str] = Field(default="Smith", description="Last name")
    target_url: Optional[str] = Field(default=None, description="Optional override for target signup URL")

    @model_validator(mode="after")
    def populate_signup_data(self):
        # If signup_data was not explicitly provided, build from top-level fields
        if not self.signup_data:
            pwd = self.password or "DefaultPass123!"
            self.signup_data = SignupInput(
                first_name=self.first_name or "Alex",
                last_name=self.last_name or "Smith",
                password=pwd,
                confirm_password=pwd,
                preferred_username=self.username
            )
        # Keep top-level username synced
        if not self.username and self.signup_data.preferred_username:
            self.username = self.signup_data.preferred_username
        elif not self.username:
            self.username = f"{self.signup_data.first_name.lower()}.{self.signup_data.last_name.lower()}"
        return self

class StartJobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    job_id: str
    username: str
    status: str
    current_step: str
    manual_intervention_required: bool
    completed_steps: list[str] = Field(default_factory=list, description="List of completed workflow steps")
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ResumeJobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class DeleteCredentialResponse(BaseModel):
    username: str
    deleted: bool
    message: str
