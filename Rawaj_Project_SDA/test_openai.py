import os
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

token = os.getenv("APIFY_API_TOKEN")

if not token:
    print("APIFY_API_TOKEN was not found in .env")
    raise SystemExit

try:
    client = ApifyClient(token)

    user = client.user().get()

    print("Apify connection successful!")
    print("Username:", user.username)
    print("User ID:", user.id)

except Exception as e:
    print("Apify connection failed")
    print("Error:", e)