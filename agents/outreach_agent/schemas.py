
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OutreachStatus(str, Enum):
    PENDING = "PENDING"
    CONTACTED = "CONTACTED"
    WAITING_FOR_REPLY = "WAITING_FOR_REPLY"
    REPLIED = "REPLIED"
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    STOPPED = "STOPPED"
    BOUNCED = "BOUNCED"


class OutreachInput(BaseModel):
    restaurant_id: int
    restaurant_name: str
    email: str

    marketing_gaps: list[str] = Field(default_factory=list)
    qualification_summary: Optional[str] = None

    previous_messages: list[str] = Field(default_factory=list)
    current_status: OutreachStatus = OutreachStatus.PENDING
    follow_up_count: int = 0


class OutreachMessage(BaseModel):
    subject: str
    body: str
    message_type: str = "initial"


class OutreachResult(BaseModel):
    restaurant_id: int
    restaurant_name: str
    email: str

    status: OutreachStatus
    message: Optional[OutreachMessage] = None

    follow_up_count: int = 0
    should_send: bool = False
    should_stop: bool = False

    reason: Optional[str] = None