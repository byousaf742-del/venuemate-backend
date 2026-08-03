import os
import uuid
from datetime import datetime
from bson import ObjectId
from app.core.config import get_db
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import firebase_admin
from firebase_admin import credentials, messaging

_firebase_initialized = False

def _init_firebase():
    global _firebase_initialized
    if not _firebase_initialized:
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            key_path = os.path.join(base_dir, "serviceAccountKey.json")
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("✅ Firebase Admin initialized")
        except Exception as e:
            print(f"❌ Firebase init error: {e}")



def to_str_id(doc: dict) -> dict:
    """Convert ObjectId _id to string id for JSON."""
    if doc is None:
        return doc
    doc["id"] = str(doc.pop("_id"))
    for key in ("owner_id", "user_id", "venue_id", "bid_id"):
        if key in doc and doc[key]:
            doc[key] = str(doc[key])
    return doc

def make_token() -> str:
    return f"VL-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

async def push_notification(
    db, user_id: str, type_: str,
    title: str, body: str,
    entity_type: str = None, entity_id: str = None,
):
    if not user_id or len(str(user_id)) != 24:
        return

    await db.notifications.insert_one({
        "user_id": ObjectId(user_id),
        "type": type_,
        "title": title,
        "body": body,
        "entity_type": entity_type,
        "entity_id": ObjectId(entity_id) if entity_id else None,
        "is_read": False,
        "created_at": datetime.utcnow(),
    })

    try:
        _init_firebase()
        user = await db.users.find_one(
            {"_id": ObjectId(user_id)},
            {"fcm_tokens": 1}
        )
        tokens = user.get("fcm_tokens", []) if user else []
        if not tokens:
            return

        for token in tokens:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data={
                        "type": type_,
                        "entity_type": entity_type or "",
                        "entity_id": entity_id or "",
                    },
                    token=token,
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            sound="default",
                            click_action="FLUTTER_NOTIFICATION_CLICK",
                        ),
                    ),
                )
                messaging.send(message)
            except Exception as e:
                print(f"FCM send error for token {token}: {e}")
    except Exception as e:
        print(f"FCM error: {e}")

def send_email(to_email: str, subject: str, body: str):
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    print(f"Sending email from: {gmail_user}")
    print(f"App password set: {bool(gmail_pass)}")
    print(f"Sending to: {to_email}")
    try:
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, to_email, msg.as_string())
        server.quit()
        print("Email sent successfully")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def generate_otp() -> str:
    return str(random.randint(100000, 999999))