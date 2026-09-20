
import imaplib
import os
import time

from datetime import datetime, timezone
from email import message_from_bytes

from dotenv import load_dotenv

from agents.outreach_agent.outreach_agent import (
    generate_outreach_message,
)

from agents.outreach_agent.tools import (
    send_outreach_email,
)

from agents.outreach_agent.follow_up import (
    get_follow_up_action,
)


load_dotenv()

TEST_EMAIL = os.getenv("TEST_RECIPIENT_EMAIL")

CHECK_INTERVAL_SECONDS = 30
MAX_FOLLOW_UPS = 1


def generate_message(
    message_type,
    previous_messages,
    follow_up_count,
):
    return generate_outreach_message(
        restaurant_name="Test Restaurant",
        email=TEST_EMAIL,
        marketing_gaps=[
            "Inconsistent Posting Frequency",
            "Limited Content Variety",
        ],
        qualification_summary=(
            "The restaurant may have an opportunity "
            "to improve its social media marketing."
        ),
        previous_messages=previous_messages,
        follow_up_count=follow_up_count,
        message_type=message_type,
    )


def send_message(message):
    """
    Sends the email and returns its Message-ID.
    """

    message_id = send_outreach_email(
        recipient_email=TEST_EMAIL,
        subject=message.subject,
        body=message.body,
    )

    return message_id


def has_received_reply(
    original_message_ids: list[str],
    sender_email: str,
    since_datetime: datetime,
) -> bool:
    """
    Checks Gmail INBOX for replies to sent messages.
    """

    app_password = os.getenv("GMAIL_APP_PASSWORD")

    if not sender_email or not app_password:
        raise ValueError(
            "GMAIL_SENDER_EMAIL or GMAIL_APP_PASSWORD "
            "is missing from .env"
        )

    if not original_message_ids:
        print("Reply check: No Message-IDs available.")
        return False

    normalized_ids = [
        message_id.strip()
        for message_id in original_message_ids
        if message_id
    ]

    since_date = since_datetime.strftime("%d-%b-%Y")

    try:
        with imaplib.IMAP4_SSL(
            "imap.gmail.com",
            993,
        ) as mail:

            mail.login(
                sender_email,
                app_password,
            )

            mail.select("INBOX")

            status, data = mail.search(
                None,
                "SINCE",
                since_date,
            )

            if status != "OK":
                print("Reply check: Gmail search failed.")
                return False

            email_ids = data[0].split()

            print(
                f"Reply check: Found {len(email_ids)} "
                "emails in INBOX."
            )

            for email_id in email_ids:

                status, message_data = mail.fetch(
                    email_id,
                    "(BODY.PEEK[HEADER.FIELDS "
                    "(FROM SUBJECT IN-REPLY-TO REFERENCES DATE)])",
                )

                if status != "OK" or not message_data:
                    continue

                raw_headers = message_data[0][1]

                if not isinstance(raw_headers, bytes):
                    continue

                email_message = message_from_bytes(
                    raw_headers
                )

                from_header = email_message.get(
                    "From",
                    "",
                )

                in_reply_to = email_message.get(
                    "In-Reply-To",
                    "",
                )

                references = email_message.get(
                    "References",
                    "",
                )

                if sender_email.lower() not in (
                    from_header.lower()
                ):
                    continue

                for message_id in normalized_ids:

                    if (
                        message_id in in_reply_to
                        or message_id in references
                    ):
                        print(
                            "Reply check: FOUND"
                        )

                        return True

            print(
                "Reply check: NOT FOUND"
            )

            return False

    except imaplib.IMAP4.error as error:

        print(
            f"IMAP error while checking replies: {error}"
        )

        return False


def main():

    if not TEST_EMAIL:
        raise ValueError(
            "TEST_RECIPIENT_EMAIL is missing from .env"
        )

    sender_email = os.getenv("GMAIL_SENDER_EMAIL")

    if not sender_email:
        raise ValueError(
            "GMAIL_SENDER_EMAIL is missing from .env"
        )

    print("Starting Outreach Scheduler...")
    print("Test recipient:", TEST_EMAIL)

    # -----------------------------------------
    # SEND INITIAL EMAIL
    # -----------------------------------------

    initial_message = generate_message(
        message_type="initial",
        previous_messages=[],
        follow_up_count=0,
    )

    initial_message_id = send_message(
        initial_message
    )

    print("Initial email sent.")

    sent_message_ids = [
        initial_message_id
    ]

    initial_sent_at = datetime.now(
        timezone.utc
    )

    last_contact_time = initial_sent_at

    follow_up_count = 0

    previous_messages = [
        initial_message.body
    ]

    status = "WAITING_FOR_REPLY"

    # -----------------------------------------
    # CHECK FOR REPLY
    # -----------------------------------------

    while True:

        time.sleep(
            CHECK_INTERVAL_SECONDS
        )

        current_time = datetime.now(
            timezone.utc
        )

        # Check the inbox BEFORE generating
        # or sending any follow-up.

        reply_found = has_received_reply(
            original_message_ids=sent_message_ids,
            sender_email=sender_email,
            since_datetime=initial_sent_at,
        )

        if reply_found:

            print(
                "Reply detected. "
                "Stopping follow-ups."
            )

            status = "REPLIED"

            break

        action = get_follow_up_action(
            last_contact_time=last_contact_time,
            follow_up_count=follow_up_count,
            status=status,
            current_time=current_time,
        )

        print(
            f"[{current_time.isoformat()}] "
            f"Action: {action}"
        )

        if action != "SEND_FOLLOW_UP":

            continue

        if follow_up_count >= MAX_FOLLOW_UPS:

            print(
                "Maximum test follow-ups reached."
            )

            break

        follow_up_count += 1

        follow_up_message = generate_message(
            message_type="follow_up_1",
            previous_messages=previous_messages,
            follow_up_count=follow_up_count,
        )

        follow_up_message_id = send_message(
            follow_up_message
        )

        sent_message_ids.append(
            follow_up_message_id
        )

        print(
            "Follow-up 1 sent."
        )

        last_contact_time = current_time

        previous_messages.append(
            follow_up_message.body
        )

        # Stop after one follow-up in test mode.
        break


if __name__ == "__main__":
    main()