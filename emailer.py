import os, ssl, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import render_template
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def build_html(guest_name, seats, venue_name, venue_address, maps_url, website_url, guide_url):
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
):
    # if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
    #     raise RuntimeError("Missing GMAIL_ADDRESS or GMAIL_APP_PASSWORD")

    subject = "We’re excited to celebrate with you ✨"
    html = build_html(guest_name, seats, venue_name, venue_address, maps_url, website_url, guide_url)

    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    # with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
    #     smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    #     smtp.sendmail(GMAIL_ADDRESS, [to_email], msg.as_string())
    with smtplib.SMTP("127.0.0.1", 1025) as smtp:
        smtp.sendmail("test@example.com", [to_email], msg.as_string())
