
from agents.outreach_agent.outreach_agent import (
    generate_outreach_message,
)

from agents.outreach_agent.tools import (
    send_outreach_email,
)

import os
from dotenv import load_dotenv


load_dotenv()

MY_EMAIL = os.getenv("TEST_RECIPIENT_EMAIL")


def main():
    if not MY_EMAIL:
        raise ValueError(
            "TEST_RECIPIENT_EMAIL is missing from .env"
        )

    print("Generating outreach message...")

    result = generate_outreach_message(
        restaurant_name="Test Restaurant",
        email=MY_EMAIL,
        marketing_gaps=[
            "Inconsistent Posting Frequency",
            "Limited Content Variety",
        ],
        qualification_summary=(
            "The restaurant may have an opportunity "
            "to improve its social media marketing."
        ),
        previous_messages=[],
        follow_up_count=0,
        message_type="initial",
    )

    print("Subject generated:", result.subject)

    # Actual email sending
    print("Sending email to:", MY_EMAIL)

    sent = send_outreach_email(
        recipient_email=MY_EMAIL,
        subject=result.subject,
        body=result.body,
    )

    if sent:
        print("Email sent successfully!")


if __name__ == "__main__":
    main()