import os, json
from twilio.rest import Client
from dotenv import load_dotenv
from utils.phone_utils import clean_phone_number

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
HX_ATTENDING = os.getenv("TWILIO_CONTENT_SID_ATTENDING")
HX_DECLINE = os.getenv("TWILIO_CONTENT_SID_DECLINE")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_whatsapp(guest_name: str, phone_number: str, attending: bool,
                  seats: str = None, rsvp_link: str = None) -> str:
    """
    Send WhatsApp message using Twilio Content templates.
    Uses HX_ATTENDING or HX_DECLINE based on attending flag.
    """
    if not guest_name or not phone_number:
        raise ValueError("guest_name and phone_number are required")

    # Normalize phone number
    formatted_number = clean_phone_number(phone_number)
    seat_text = "your seat" if str(seats) == "1" else f"{seats} seats for you and your party"

    if attending:
        if not seats or not rsvp_link:
            raise ValueError("seats and rsvp_link are required when attending=True")
        content_sid = HX_ATTENDING
        content_vars = {"1": guest_name, "2": seat_text, "3": rsvp_link}
    else:
        content_sid = HX_DECLINE
        content_vars = {"1": guest_name}

    message = twilio_client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=f"whatsapp:{formatted_number}",
        content_sid=content_sid,
        content_variables=json.dumps(content_vars),
    )

    return message.sid
