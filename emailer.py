import os, requests
from email.utils import formataddr, formatdate, make_msgid
from flask import render_template
from dotenv import load_dotenv
from logging_setup import setup_logger

load_dotenv()

log = setup_logger()
# Zepto env
ZEPTO_TOKEN = os.getenv("ZEPTO_TOKEN")  # Zepto "Send Mail Token"
FROM_ADDRESS = os.getenv("FROM_ADDRESS", "info@nanaandwahabwedding.com")
FROM_NAME = os.getenv("FROM_NAME", "Nana-Serwaa & Abdul Wahab")
ZEPTO_API = "https://api.zeptomail.com/v1.1/email"


def build_html(
    guest_name, seats, venue_name, venue_address, maps_url, website_url, guide_url
):
    return render_template(
        "email_attendance.html",
        guest_name=guest_name,
        seats=seats,
        venue_name=venue_name,
        venue_address=venue_address,
        maps_url=maps_url,
        website_url=website_url,
        guide_url=guide_url,
    )


def build_text(guest_name, seats, website_url):
    seats_line = (
        "1 seat in your honor" if int(seats) == 1 else f"{seats} seats for you and your party"
    )
    return (
        f"Hi {guest_name},\n\n"
        f"Your attendance is confirmed. We’ve reserved {seats_line}.\n\n"
        f"If plans change, please update your RSVP here: {website_url}\n\n"
        f"— The Nimako & Bandau Families\n"
    )


def send_attendance_email(
    to_email: str,
    guest_name: str,
    seats: int,
    venue_name: str,
    venue_address: str,
    maps_url: str,
    website_url: str,
    guide_url: str,
    reply_to: str | None = None,
    subject: str | None = None,
):
    if not subject:
        subject = "Nana-Serwaa and Abdul Wahab's Wedding ✨"

    html = build_html(
        guest_name, seats, venue_name, venue_address, maps_url, website_url, guide_url
    )
    text = build_text(guest_name, seats, website_url)

    payload = {
        "from": {"address": FROM_ADDRESS, "name": FROM_NAME},
        "to": [{"email_address": {"address": to_email, "name": guest_name}}],
        **({"reply_to": [{"address": reply_to}]} if reply_to else {}),
        "subject": subject,
        "htmlbody": html,
        "textbody": text,
        # Zepto expects mime_headers as a dict, not an array
        "mime_headers": {
            "Date": formatdate(localtime=True),
            "Message-ID": make_msgid(domain="nanaandwahabwedding.com"),
        },
    }

    try:
        r = requests.post(
            ZEPTO_API,
            json=payload,
            headers={
                "Authorization": f"Zoho-enczapikey {ZEPTO_TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=60,
        )

        # try to parse JSON safely
        try:
            resp_json = r.json()
        except Exception as e:
            resp_json = {"non_json_response": r.text[:500]}  # truncate to be safe

        log.debug("Zepto response: %s %s", r.status_code, resp_json)

    except requests.RequestException as e:
        log.error("Zepto request failed: %s", e, exc_info=True)

    # print Zepto error body if it fails, so you see the reason
    try:
        r.raise_for_status()
    except Exception:
        log.error("ZEPTOMAIL ERROR:", r.status_code, r.text)
        raise
    return r.json()
