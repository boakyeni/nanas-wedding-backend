import os, ssl, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
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
        subject = "Nana-Serwaa and Abdul Wahab's Wedding ✨"

    html = build_html(guest_name, seats, venue_name, venue_address, maps_url, website_url, guide_url)
    text = build_text(guest_name, seats, website_url)

    # multipart/alternative: text then html
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr(("Nana-Serwaa & Abdul Wahab", GMAIL_ADDRESS))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")  # fine for Gmail SMTP
    if reply_to:
        msg["Reply-To"] = reply_to

    # Good for deliverability
    msg["List-Unsubscribe"] = f"<mailto:{GMAIL_ADDRESS}?subject=unsubscribe>, <{website_url.rstrip('/')}/unsubscribe?email={to_email}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # Attach text then html
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()

    # Either SSL 465 (as you had) OR STARTTLS 587. Both are fine with Gmail.
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        # Envelope MAIL FROM must be your Gmail to avoid DMARC/“via gmail.com” weirdness.
        smtp.sendmail(GMAIL_ADDRESS, [to_email], msg.as_string())

    # with smtplib.SMTP("127.0.0.1", 1025) as smtp:
    #     smtp.sendmail("test@example.com", [to_email], msg.as_string())
