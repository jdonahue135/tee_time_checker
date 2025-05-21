#!/usr/bin/env python3

from enum import Enum
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
DATE = "05-18-2025"

class TIME_OF_DAY(Enum):
    MORNING = "morning"
    ALL = "all"

TIME = TIME_OF_DAY.MORNING
# Cooldown time in seconds (e.g., 60 minutes = 3600 seconds)
COOLDOWN_PERIOD = 3600 * 3

# Path to the timestamp file
TIMESTAMP_FILE = '/Users/jakedonahue/tee_time_checker/last_sent.txt'

def should_send_email():
    """Returns True if enough time has passed since the last email was sent."""
    if os.path.exists(TIMESTAMP_FILE):
        with open(TIMESTAMP_FILE, 'r') as file:
            content = file.read().strip()
            if not content:
                return True  # Treat empty file as if no email was ever sent
            try:
                last_sent = float(content)
            except ValueError:
                return True  # Invalid content—assume no email sent
        current_time = time.time()
        return (current_time - last_sent > COOLDOWN_PERIOD)
    return True  # If the file doesn't exist, assume we can send the first email

def update_timestamp():
    """Update the timestamp file with the current time."""
    with open(TIMESTAMP_FILE, 'w') as file:
        file.write(str(time.time()))

# Function to send email/SMS
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
    
    body += "\nBook here: https://app.foreupsoftware.com/index.php/booking/21120/6992#/teetimes"
    update_timestamp()
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ Notification sent.")
    except Exception as e:
        print("❌ Failed to send notification:", e)

# Tee time checking logic
def check_tee_times():
    url = "https://app.foreupsoftware.com/index.php/api/booking/times"
    params = {
        "time": TIME,
        "date": DATE,
        "holes": "all",
        "players": 2,
        "booking_class": "8436",
        "schedule_id": "6992",
        "schedule_ids[]": ["6991", "6992"],
        "specials_only": 0,
        "api_key": "no_limits"
    }

    headers = {
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "en-US,en;q=0.9,pt;q=0.8",
        "api-key": "no_limits",
        "priority": "u=1, i",
        "referer": "https://app.foreupsoftware.com/index.php/booking/21120/6992",
        "sec-ch-ua": '"Google Chrome";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "x-fu-golfer-location": "foreup",
        "x-requested-with": "XMLHttpRequest"
    }

    cookies = {
        "PHPSESSID": "ok92h697p3s1ht8k9jpckauaq5",
        "_ga_Y0N3BHPPWG": "GS2.1.s1747152348$o2$g0$t1747152348$j0$l0$h0",
        "_ga": "GA1.2.826621824.1744642715",
        "_gid": "GA1.2.1840340421.1747152349",
        "__stripe_mid": "2900bead-b40a-477c-af03-67f1256f3cb071697f",
        "__stripe_sid": "2cb39532-b2d7-49be-84fd-ed06a58a2ec39f30ab"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            # cookies=cookies
        )
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

# Call the function once (for testing)
def main():
    check_tee_times()

if __name__ == "__main__":
    main()
