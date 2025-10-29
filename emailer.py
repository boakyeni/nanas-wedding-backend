import os
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from flask import render_template
from dotenv import load_dotenv

load_dotenv()

SES_FROM_ADDRESS = os.getenv("SES_FROM_ADDRESS")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# create reusable SES client
ses = boto3.client("ses", region_name=AWS_REGION)

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

def build_text(guest_name, seats, website_url):
    seats_line = "your seat" if int(seats) == 1 else f"{seats} seats for you and your party"
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
        subject = "Nana-Serwaa and Abdul Wahab’s Wedding ✨"

    html = build_html(guest_name, seats, venue_name, venue_address, maps_url, website_url, guide_url)
    text = build_text(guest_name, seats, website_url)

    # Assemble MIME (for clarity; SES will parse both)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("Nana-Serwaa & Abdul Wahab", SES_FROM_ADDRESS))
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="nanaandwahabwedding.com")
    if reply_to:
        msg["Reply-To"] = reply_to

    msg["List-Unsubscribe"] = (
        f"<mailto:{SES_FROM_ADDRESS}?subject=unsubscribe>, "
        f"<{website_url.rstrip('/')}/unsubscribe?email={to_email}>"
    )
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Send through SES
    response = ses.send_raw_email(
        Source=SES_FROM_ADDRESS,
        Destinations=[to_email],
        RawMessage={"Data": msg.as_string()},
    )

    print("Email sent via SES:", response["MessageId"])
    return response
