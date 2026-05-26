from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgentSessionCreate(BaseModel):
    user_id: UUID
    session_type: str


class AgentSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    session_type: str
    workflow_id: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
