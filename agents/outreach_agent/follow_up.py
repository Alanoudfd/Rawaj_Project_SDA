
from datetime import datetime, timedelta, timezone
from enum import Enum


# =========================================================
# CONFIGURATION
# =========================================================

TEST_MODE = True

# Test: 5 minutes
# Production: 1 day
FOLLOW_UP_INTERVAL_MINUTES = 5 if TEST_MODE else 24 * 60

# Maximum number of follow-up emails
MAX_FOLLOW_UPS = 3


# =========================================================
# OUTREACH STATUS
# =========================================================

class FollowUpStatus(str, Enum):
    PENDING = "PENDING"
    WAITING_FOR_REPLY = "WAITING_FOR_REPLY"
    REPLIED = "REPLIED"
    STOPPED = "STOPPED"
    BOUNCED = "BOUNCED"
    COMPLETED = "COMPLETED"


# =========================================================
# TIME CALCULATION
# =========================================================

def get_next_follow_up_time(
    last_contact_time: datetime,
) -> datetime:
    """
    Calculate when the next follow-up can be sent.

    Test mode:
        After 5 minutes.

    Production mode:
        After 24 hours.
    """

    interval = timedelta(
        minutes=FOLLOW_UP_INTERVAL_MINUTES
    )

    return last_contact_time + interval


def is_follow_up_due(
    last_contact_time: datetime,
    current_time: datetime | None = None,
) -> bool:
    """
    Check whether enough time has passed
    to send the next follow-up.
    """

    if current_time is None:
        current_time = datetime.now(timezone.utc)

    next_follow_up_time = get_next_follow_up_time(
        last_contact_time
    )

    return current_time >= next_follow_up_time


# =========================================================
# FOLLOW-UP LIMITS
# =========================================================

def can_send_follow_up(
    follow_up_count: int,
    status: str,
) -> bool:
    """
    Decide whether another follow-up is allowed.
    """

    blocked_statuses = {
        FollowUpStatus.REPLIED.value,
        FollowUpStatus.STOPPED.value,
        FollowUpStatus.BOUNCED.value,
        FollowUpStatus.COMPLETED.value,
    }

    if status in blocked_statuses:
        return False

    if follow_up_count >= MAX_FOLLOW_UPS:
        return False

    return True


# =========================================================
# NEXT ACTION
# =========================================================

def get_follow_up_action(
    last_contact_time: datetime,
    follow_up_count: int,
    status: str,
    current_time: datetime | None = None,
) -> str:
    """
    Return the next action for the Outreach Agent.

    Possible results:
        SEND_FOLLOW_UP
        WAIT
        STOP
    """

    if not can_send_follow_up(
        follow_up_count=follow_up_count,
        status=status,
    ):
        return "STOP"

    if not is_follow_up_due(
        last_contact_time=last_contact_time,
        current_time=current_time,
    ):
        return "WAIT"

    return "SEND_FOLLOW_UP"