
import os
import smtplib

from email.message import EmailMessage
from email.utils import make_msgid

from dotenv import load_dotenv

load_dotenv()


def build_prompt_variables(
    restaurant_data=None,
    **kwargs,
) -> dict:
    """
    Build the variables used by the Outreach Agent prompt.

    Supports restaurant data as a dictionary and additional
    keyword arguments.
    """

    variables = {}

    if isinstance(restaurant_data, dict):
        variables.update(restaurant_data)

    elif restaurant_data is not None:
        try:
            variables.update(vars(restaurant_data))
        except TypeError:
            pass

    variables.update(kwargs)

    # Common fields used by the outreach prompt
    prompt_variables = {
        "restaurant_name": variables.get(
            "restaurant_name",
            variables.get("name", "the restaurant"),
        ),
        "location": variables.get(
            "location",
            variables.get("city", "Unknown"),
        ),
        "city": variables.get(
            "city",
            variables.get("location", "Unknown"),
        ),
        "contact_name": variables.get(
            "contact_name",
            variables.get("owner_name", ""),
        ),
        "contact_email": variables.get(
            "contact_email",
            variables.get("email", ""),
        ),
        "instagram_url": variables.get(
            "instagram_url",
            variables.get("instagram", ""),
        ),
        "website": variables.get(
            "website",
            variables.get("domain", ""),
        ),
        "marketing_gaps": variables.get(
            "marketing_gaps",
            variables.get("gaps", []),
        ),
        "research_summary": variables.get(
            "research_summary",
            variables.get("summary", ""),
        ),
        "qualification_result": variables.get(
            "qualification_result",
            variables.get("qualification", ""),
        ),
        "strategy": variables.get(
            "strategy",
            variables.get("marketing_strategy", ""),
        ),
    }

    # Preserve additional fields that may be needed by the prompt
    for key, value in variables.items():
        if key not in prompt_variables:
            prompt_variables[key] = value

    return prompt_variables


def send_outreach_email(
    recipient_email: str,
    subject: str,
    body: str,
) -> str:
    """
    Send an email in TEST MODE.

    The email can only be sent to TEST_RECIPIENT_EMAIL.
    Returns the generated Message-ID.
    """

    sender_email = os.getenv("GMAIL_SENDER_EMAIL")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    test_recipient = os.getenv("TEST_RECIPIENT_EMAIL")

    if not sender_email or not app_password:
        raise ValueError(
            "GMAIL_SENDER_EMAIL or GMAIL_APP_PASSWORD is missing."
        )

    if not test_recipient:
        raise ValueError(
            "TEST_RECIPIENT_EMAIL is missing."
        )

    if recipient_email != test_recipient:
        raise PermissionError(
            "TEST MODE: Sending is allowed only to "
            "TEST_RECIPIENT_EMAIL."
        )

    message = EmailMessage()

    message_id = make_msgid()

    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = subject
    message["Message-ID"] = message_id

    message.set_content(body)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(message)

    print(
        f"Email sent with Message-ID: {message_id}"
    )

    return message_id

import re


def validate_email(email: str) -> bool:
    """
    Validate an email address format.
    """

    if not email or not isinstance(email, str):
        return False

    email = email.strip()

    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

    return bool(re.match(pattern, email))