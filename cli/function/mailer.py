# --- IMPORT ---
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from function.generator import safe_filename

# Load credentials from .env file (safer than hardcoding)
load_dotenv()

# --- CONFIG ---
SMTP_HOST = "smtp-relay.brevo.com"
SMTP_PORT = 587
SMTP_LOGIN = os.getenv("SMTP_LOGIN")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

SENDER_NAME = "Osalasi Company Limited"
SENDER_EMAIL = os.getenv("SENDER_EMAIL")   # your verified sender in Brevo

# --- EMAIL BUILDER ---
def build_email(row, pdf_path):
    msg = MIMEMultipart()
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = row["Email"]
    msg["Subject"] = f"CBT Examination Invitation — {row['ExamDate'].strftime('%d %B %Y')}"

    # HTML body — personalised with Name and ExamDate
    body_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #2C2C2C; line-height: 1.5;">
        <p>Dear {row['Name']},</p>

        <p>Following your successful shortlisting in the ongoing recruitment exercise
        for the employment of teachers into primary and secondary schools in Rivers State,
        we are pleased to formally invite you to the Computer-Based Test (CBT) examination.</p>

        <p>Your examination is scheduled for
        <strong>{row['ExamDate'].strftime('%A, %d %B %Y')}</strong>.
        The full details — including your assigned time slot, hall, and examination
        centre — are contained in the attached invitation letter.</p>

        <p>Please download, print, and bring the attached letter to the examination venue
        along with a valid means of identification.</p>

        <p>We wish you success.</p>

        <p>Yours faithfully,<br>
        <strong>Osalasi Company Limited</strong><br>
        <em>On behalf of the Rivers State Government</em></p>
      </body>
    </html>
    """
    msg.attach(MIMEText(body_html, "html"))

    # Attach the PDF
    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename=\"{os.path.basename(pdf_path)}\"",
    )
    msg.attach(part)

    return msg


# --- SENDER ---
def send_email(row, pdf_path):
    try:
        msg = build_email(row, pdf_path)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_LOGIN, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✓ Sent to {row['Name']} ({row['Email']})")
        return True
    except Exception as e:
        print(f"✗ Failed to send to {row['Email']}: {e}")
        return False


if __name__ == "__main__":
    import pandas as pd
    data = pd.read_excel("./data/allocated_exam_schedule.xlsx")
    row = data.iloc[0]
    pdf_path = f"./pdf/{safe_filename(row['ExamNo'])}.pdf"
    send_email(row, pdf_path)