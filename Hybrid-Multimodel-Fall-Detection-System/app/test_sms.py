import os
from twilio.rest import Client

account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "your_account_sid_here")
auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "your_auth_token_here")

client = Client(account_sid, auth_token)

target_number = os.environ.get("TARGET_PHONE_NUMBER", "+919353227125")
from_number = os.environ.get("TWILIO_PHONE_NUMBER", "+17372508034")

message = client.messages.create(
    body="⚠️ Fall Alert System Test: Emergency SMS dispatch verification.",
    from_=from_number,
    to=target_number
)

print("SMS sent successfully!")
print("Message SID:", message.sid)