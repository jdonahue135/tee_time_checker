#!/usr/bin/env python3

import time
import requests
import smtplib
import os
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Email configuration
SENDER_EMAIL = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
TO_EMAILS = os.getenv("EMAIL_RECEIVERS", "")

# Booking configuration
DATE = os.getenv("TARGET_DATE", "")
TIME = os.getenv("TIME_OF_DAY", "all")
PLAYERS = int(os.getenv("PLAYERS", "2"))
BOOKING_CLASS = os.getenv("BOOKING_CLASS", "8436")
SCHEDULE_ID = os.getenv("SCHEDULE_ID", "6992")
SCHEDULE_IDS = os.getenv("SCHEDULE_IDS", "6991,6992").split(",")

# Cooldown time in seconds
COOLDOWN_PERIOD = 3600 * int(os.getenv("COOLDOWN_HOURS", "3"))

# Path to the timestamp file
TIMESTAMP_FILE = 'last_sent.txt'


def should_send_email():
    """Returns True if enough time has passed since the last email was sent."""
    if os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, 'r') as file:
            content = file.read().strip()
            if not content:
                return True
            try:
                last_sent = float(content)
            except ValueError:
                return True
            current_time = time.time()
            cooldown_remaining = COOLDOWN_PERIOD - (current_time - last_sent)
            if cooldown_remaining > 0:
                print(f"⏳ Cooldown active. Next email in {cooldown_remaining // 60:.0f} min.")
                return False
    return True


def update_timestamp():
    """Update the timestamp file with the current time."""
    with open(TIMESTAMP_FILE, 'w') as file:
        file.write(str(time.time()))


def send_notification(tee_times):
    if not should_send_email():
        print("⏳ Cooldown period active. Not sending email yet.")
        return

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = TO_EMAILS
    msg['Subject'] = "⛳️ Tee Time Alert!"

    body = "Tee times just opened up!\n\n"
    for t in tee_times:
        body += f"Available Spots: {t.get('available_spots')}, Time: {t.get('time')}, Holes: {t.get('holes')}, Course: {t.get('course_name')}\n"
    body += f"\nBook here: https://foreupsoftware.com/index.php/booking/21120/{SCHEDULE_ID}#/teetimes"

    update_timestamp()
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ Notification sent.")
    except Exception as e:
        print("❌ Failed to send notification:", e)


def check_tee_times():
    url = "https://foreupsoftware.com/index.php/api/booking/times"

    params = {
        "time": TIME,
        "date": DATE,
        "holes": "all",
        "players": PLAYERS,
        "booking_class": BOOKING_CLASS,
        "schedule_id": SCHEDULE_ID,
        "schedule_ids[]": SCHEDULE_IDS,
        "specials_only": 0,
        "api_key": "",
    }

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9,pt;q=0.8",
        "api-key": "",
        "priority": "u=1, i",
        "referer": f"https://foreupsoftware.com/index.php/booking/21120/{SCHEDULE_ID}",
        "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "x-fu-golfer-location": "foreup",
        "x-requested-with": "XMLHttpRequest",
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Checked at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if response.ok:
            tee_times = response.json()
            if tee_times:
                print(f"🎉 Found {len(tee_times)} tee times!")
                send_notification(tee_times)
            else:
                print("No tee times available.")
        else:
            print(f"Request failed with status code {response.status_code}")
    except Exception as e:
        print("Error checking tee times:", e)


def main():
    check_tee_times()


if __name__ == "__main__":
    main()