# whatsapp_report_generator.py
# ============================================================
# WhatsApp Report Generator v2.0
# توليد بلاغات قوية ومتنوعة لحظر أرقام واتساب
# ============================================================
import os
import time
import json
import uuid
import random
import urllib.parse
from datetime import datetime, timedelta

from config import redis_client, PUBLIC_URL
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("wa_report_gen")

# ============================================================
# [1] إيميلات واتساب الرسمية للبلاغات
# ============================================================
WA_REPORT_EMAILS = {
    "support": "support@whatsapp.com",
    "abuse": "abuse@whatsapp.com",
    "security": "security@whatsapp.com",
    "android": "android-support@whatsapp.com",
    "ios": "iphone-support@whatsapp.com",
}

# ============================================================
# [2] قوالب البلاغات القوية — 25 قالب متنوع
# ============================================================
REPORT_TEMPLATES = {
    # ═══════════════════════════════════════════════════
    # SPAM — 6 قوالب
    # ═══════════════════════════════════════════════════
    "spam": [
        {
            "subject": "URGENT: Repeated spam from WhatsApp number {number}",
            "body": """Dear WhatsApp Trust & Safety Team,

I am writing to file a formal complaint against the WhatsApp number {number} which has been repeatedly sending me unsolicited spam messages containing suspicious links and fraudulent offers.

This account has violated WhatsApp's Terms of Service and Community Guidelines multiple times. Despite blocking, similar messages continue to arrive.

REPORTED NUMBER: {number}
INCIDENT DATE: {date}
INCIDENT TIME: {time}
CATEGORY: Spam / Unsolicited messages
FREQUENCY: Multiple times daily
DURATION: Over {days} days

Please review this account and take immediate action to protect other users from this spam campaign.

Evidence: Screenshots available upon request.

Best regards,
A verified WhatsApp user"""
        },
        {
            "subject": "Spam Campaign Report - {number}",
            "body": """Hello WhatsApp Support,

I am reporting a spam account that is aggressively targeting WhatsApp users.

NUMBER: {number}
ISSUE: Bulk spam messaging with malicious links
REPORT DATE: {date}

This account has sent me over 50 messages in the past {days} days, all containing promotional content and suspicious URLs designed to steal personal information.

I have already blocked and reported this number in the app, but I am submitting this formal report as requested.

Please investigate this account urgently.

Regards"""
        },
        {
            "subject": "Formal Spam Complaint: {number}",
            "body": """Dear WhatsApp Support Team,

COMPLAINT TYPE: Persistent Spam
REPORTED NUMBER: {number}
DATE OF COMPLAINT: {date}

I am receiving continuous spam messages from the number {number} despite my repeated requests to stop. This behavior constitutes a clear violation of WhatsApp's Community Standards.

The content includes:
- Fake lottery winning notifications
- Suspicious investment schemes
- Phishing links disguised as bank notifications

I request immediate suspension of this account.

Thank you for your prompt attention to this matter."""
        },
        {
            "subject": "Multiple users reporting {number} for spam",
            "body": """WhatsApp Security Team,

I am submitting this report on behalf of myself and several contacts who have all received spam messages from {number}.

REPORTED NUMBER: {number}
COMPLAINT: Organized spam campaign
DATE: {date}

Multiple users in our network have blocked this number. We believe it is part of an automated spam bot network.

Request you to investigate and take appropriate action.

Regards,
Concerned WhatsApp user"""
        },
        {
            "subject": "Immediate action required: Spam from {number}",
            "body": """URGENT SECURITY REPORT

To: WhatsApp Trust & Safety

I am filing an urgent complaint against the WhatsApp account {number}.

THREAT LEVEL: HIGH
ISSUE: Aggressive spam messaging with malicious intent
DATE: {date}
TIME: {time}

This account has been sending bulk messages containing:
- Phishing links
- Fake job offers
- Financial scam attempts

Multiple users are at risk. Please terminate this account immediately.

Thank you."""
        },
        {
            "subject": "Spam violation report - Number {number}",
            "body": """Dear WhatsApp Team,

I would like to formally report the WhatsApp number {number} for violating WhatsApp's spam policy.

DETAILS:
Reported Number: {number}
Violation Type: Unsolicited bulk messaging
Report Date: {date}
Prior Blocks: 1
Message Count: 30+

The messages are clearly automated and part of a spam operation. Kindly review and take action.

Best regards."""
        },
    ],

    # ═══════════════════════════════════════════════════
    # SCAM — 6 قوالب
    # ═══════════════════════════════════════════════════
    "scam": [
        {
            "subject": "FRAUD ALERT: {number} is a scam account",
            "body": """EMERGENCY FRAUD REPORT

To: WhatsApp Trust & Safety Team

I am reporting a serious fraud operation running on WhatsApp through the number {number}.

FRAUD CATEGORY: Financial scam
REPORTED NUMBER: {number}
DATE OF REPORT: {date}
ESTIMATED VICTIMS: Multiple users

This account contacted me claiming to be from a financial institution and requested sensitive information including:
- Banking details
- OTP codes
- Personal identification

This is a clear attempt at financial fraud. I request WhatsApp to:
1. Immediately suspend this account
2. Preserve chat logs for law enforcement
3. Warn other users who may be targeted

Please act urgently to prevent further victims.

Regards,
A concerned user"""
        },
        {
            "subject": "Investment Scam: {number} - Multiple Victims",
            "body": """Dear WhatsApp Support,

I am filing an urgent complaint regarding a large-scale investment scam being run via WhatsApp number {number}.

NUMBER: {number}
SCAM TYPE: Fake crypto/investment scheme
DATE: {date}

This account has:
- Promised unrealistic returns (300%+ monthly)
- Requested upfront payments via crypto/transfer
- Pressured victims with fake "limited time" offers
- Refused to return money upon request

At least 5 people in my network have been targeted. This is an organized fraud operation.

I request immediate account termination and reporting to authorities.

Regards"""
        },
        {
            "subject": "Romance/Financial scam from {number}",
            "body": """To Whom It May Concern,

I am reporting a romance scam (pig butchering) being operated from WhatsApp number {number}.

REPORTED: {number}
DATE: {date}
SCAM PATTERN: Long-term emotional manipulation leading to financial fraud

The operator behind this number:
- Creates fake emotional connection
- Gradually introduces "investment opportunities"
- Uses fake screenshots of profits
- Requests money transfers

This is a well-known scam pattern. Please investigate and ban immediately.

Thank you."""
        },
        {
            "subject": "Job scam from {number} - URGENT",
            "body": """Dear WhatsApp Team,

I am reporting a fake job offer scam from WhatsApp number {number}.

NUMBER: {number}
SCAM TYPE: Fake job offer requiring upfront payment
DATE: {date}

This account claims to be from a legit company and offers jobs that require:
- Registration fees
- Training payments
- "Security deposits"

Multiple people have been tricked. This is clearly fraudulent activity.

Please ban this account immediately.

Regards"""
        },
        {
            "subject": "Phishing attempt via {number}",
            "body": """Security Alert - WhatsApp Support Team,

I am reporting a phishing attempt from WhatsApp number {number}.

REPORTED NUMBER: {number}
ATTACK TYPE: Phishing / Credential theft
DATE: {date}

This account sent me a message pretending to be from WhatsApp itself, asking me to verify my account by clicking a suspicious link that leads to a fake login page.

This is a clear phishing attempt designed to steal account credentials. Immediate action is required.

Please ban this number and warn other users.

Sincerely,
A vigilant WhatsApp user"""
        },
        {
            "subject": "Crypto scam - Account {number}",
            "body": """Dear WhatsApp Trust & Safety,

URGENT: I am reporting a cryptocurrency scam account operating via WhatsApp number {number}.

NUMBER: {number}
SCAM TYPE: Fake crypto trading platform
DATE: {date}

The operator behind this account:
- Advertises fake crypto trading signals
- Shows photoshopped profit screenshots
- Asks for deposits in USDT/Bitcoin
- Vanishes after receiving funds

I have evidence of chats and transactions. Please take action.

Regards"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # HARASSMENT — 5 قوالب
    # ═══════════════════════════════════════════════════
    "harassment": [
        {
            "subject": "HARASSMENT REPORT: Number {number}",
            "body": """URGENT HARASSMENT COMPLAINT

To: WhatsApp Trust & Safety Team

I am filing a formal harassment complaint against WhatsApp number {number}.

REPORTED NUMBER: {number}
HARASSMENT TYPE: Repeated threatening messages
DATE: {date}
DURATION: Over {days} days

This user has been sending me:
- Threatening messages
- Abusive language
- Intimidating content
- Unsolicited explicit material

I feel unsafe and violated. This is a clear case of cyberbullying and harassment.

I request:
1. Immediate account suspension
2. Preservation of chat logs
3. Cooperation with law enforcement if needed

Please act urgently.

Regards,
A victim of harassment"""
        },
        {
            "subject": "Threatening messages from {number}",
            "body": """Dear WhatsApp Support,

I am reporting threatening behavior from WhatsApp number {number}.

REPORTED NUMBER: {number}
DATE: {date}
THREAT TYPE: Physical threats and intimidation

This account has sent me multiple messages containing threats of physical harm to me and my family.

I have reported this to local authorities and I am now submitting this formal report to WhatsApp.

Please suspend this account immediately to prevent further harm.

Thank you."""
        },
        {
            "subject": "Cyberbullying from {number}",
            "body": """To WhatsApp Trust & Safety,

I am reporting continued cyberbullying from WhatsApp number {number}.

NUMBER: {number}
DATE: {date}
ABUSE TYPE: Cyberbullying / Body shaming / Verbal abuse

This person has been systematically harassing me through WhatsApp with:
- Insulting messages
- Mocking content
- Public humiliation attempts
- Sharing my private information with others

This violates WhatsApp's Community Guidelines on harassment.

I request immediate action.

Regards"""
        },
        {
            "subject": "Stalking via WhatsApp: {number}",
            "body": """URGENT: STALKING REPORT

To: WhatsApp Security Team

I am reporting a stalking case via WhatsApp number {number}.

REPORTED NUMBER: {number}
DATE: {date}
PATTERN: Obsessive stalking behavior

This individual has been:
- Sending messages at all hours
- Creating multiple accounts to bypass blocks
- Tracking my online activity
- Contacting my friends and family through WhatsApp

This is a serious stalking situation. I have filed a police report and I request WhatsApp to cooperate.

Please take immediate action.

Regards"""
        },
        {
            "subject": "Abusive content from {number}",
            "body": """Dear WhatsApp Support,

I am reporting an abusive account on WhatsApp.

REPORTED NUMBER: {number}
DATE: {date}
ABUSE CATEGORY: Offensive language + Hate speech

This account has been sending me abusive and offensive messages including:
- Racial slurs
- Hate speech
- Offensive images
- Mocking my religion/beliefs

This violates WhatsApp's anti-hate-speech policy. Please ban this account.

Regards"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # FAKE ACCOUNT — 4 قوالب
    # ═══════════════════════════════════════════════════
    "fake": [
        {
            "subject": "Fake account impersonation: {number}",
            "body": """Dear WhatsApp Support,

I am reporting a fake/impersonation account on WhatsApp.

REPORTED NUMBER: {number}
REASON: Impersonation of a real person/company
DATE: {date}

This account is using:
- Stolen photos of a real person
- Fake name matching a public figure
- Copy of a legitimate business profile

The operator is using this fake identity to deceive users.

Please verify and take down this fake account.

Regards"""
        },
        {
            "subject": "Business impersonation: {number}",
            "body": """To WhatsApp Business Team,

I am reporting a fake account impersonating a legitimate business.

REPORTED NUMBER: {number}
IMPERSONATED BRAND: [Business Name]
DATE: {date}

This account is:
- Using our brand name
- Copying our logo and branding
- Misleading our customers
- Potentially damaging our reputation

We request immediate verification and removal.

Regards,
On behalf of the legitimate business"""
        },
        {
            "subject": "Catfishing account {number}",
            "body": """Dear WhatsApp Support,

I am reporting a catfishing account on WhatsApp.

NUMBER: {number}
DATE: {date}
REASON: Fake profile with stolen photos

This account is using photos of someone else to create a fake identity for deceptive purposes. Multiple people have been misled.

Please verify and take appropriate action.

Thanks"""
        },
        {
            "subject": "Government/official impersonation - {number}",
            "body": """URGENT: OFFICIAL IMPERSONATION

To: WhatsApp Trust & Safety

I am reporting an account impersonating a government/official entity.

REPORTED NUMBER: {number}
IMPERSONATED: Official government department
DATE: {date}

This account claims to represent a government agency and is:
- Requesting personal documents
- Demanding payments for fake services
- Threatening legal action

This is a serious offense. Immediate action required.

Regards"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # ILLEGAL — 4 قوالب
    # ═══════════════════════════════════════════════════
    "illegal": [
        {
            "subject": "Illegal activity via {number}",
            "body": """Dear WhatsApp Trust & Safety,

I am reporting illegal activities being conducted via WhatsApp number {number}.

NUMBER: {number}
ILLEGAL ACTIVITY: Drug sales / Illegal goods
DATE: {date}

This account is using WhatsApp to:
- Sell illegal substances
- Distribute illegal content
- Arrange illegal transactions

Evidence: Chat screenshots available.

I request immediate account termination and reporting to authorities.

Regards"""
        },
        {
            "subject": "Child safety violation - {number}",
            "body": """URGENT: CHILD SAFETY REPORT

To: WhatsApp Trust & Safety Team

I am reporting a serious child safety violation on WhatsApp number {number}.

REPORTED NUMBER: {number}
VIOLATION: Inappropriate contact with minors
DATE: {date}

This account has been contacting minors with inappropriate content. This violates WhatsApp's Child Safety Policy and may violate laws.

IMMEDIATE ACTION REQUIRED.

Regards"""
        },
        {
            "subject": "Human trafficking suspicion - {number}",
            "body": """CONFIDENTIAL REPORT

To: WhatsApp Security Team

I am reporting suspicious activity suggesting human trafficking via number {number}.

NUMBER: {number}
SUSPICION: Human trafficking recruitment
DATE: {date}

Patterns observed:
- Job offers with unusual terms
- Requests for personal documents
- Travel arrangement discussions
- Multiple similar accounts

Please investigate urgently.

Regards"""
        },
        {
            "subject": "Extortion attempt from {number}",
            "body": """Dear WhatsApp Support,

I am reporting an extortion attempt via WhatsApp.

REPORTED NUMBER: {number}
CRIME: Blackmail / Extortion
DATE: {date}

This account is threatening to share private information unless I pay a ransom. This is a criminal act.

I have filed a police report. Please cooperate with authorities and ban this account.

Regards"""
        },
    ],
}

# ============================================================
# [3] مولّد الروابط
# ============================================================
def build_gmail_link(to_email, subject, body):
    """Gmail Compose Link"""
    base = "https://mail.google.com/mail/?view=cm&fs=1&tf=1"
    params = urllib.parse.urlencode({
        "to": to_email,
        "su": subject,
        "body": body,
    })
    return f"{base}&{params}"

def build_outlook_link(to_email, subject, body):
    """Outlook Compose Link"""
    base = "https://outlook.live.com/mail/0/deeplink/compose"
    params = urllib.parse.urlencode({
        "to": to_email,
        "subject": subject,
        "body": body,
    })
    return f"{base}?{params}"

def build_yahoo_link(to_email, subject, body):
    """Yahoo Mail Compose"""
    base = "https://compose.mail.yahoo.com/"
    params = urllib.parse.urlencode({
        "to": to_email,
        "sub": subject,
        "body": body,
    })
    return f"{base}?{params}"

def build_mailto_link(to_email, subject, body):
    """mailto عام"""
    params = urllib.parse.urlencode({
        "subject": subject,
        "body": body,
    })
    return f"mailto:{to_email}?{params}"

# ============================================================
# [4] دوال مساعدة
# ============================================================
def normalize_number(number):
    """تطبيع الرقم"""
    if not number:
        return None
    clean = number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if not clean.startswith("+"):
        clean = "+" + clean
    if len(clean) < 10 or len(clean) > 16:
        return None
    return clean

def pick_random_email():
    """اختيار إيميل واتساب عشوائي"""
    return random.choice(list(WA_REPORT_EMAILS.values()))

def pick_template(reason):
    """اختيار قالب عشوائي"""
    templates = REPORT_TEMPLATES.get(reason)
    if not templates:
        templates = REPORT_TEMPLATES["spam"]
    return random.choice(templates)

# ============================================================
# [5] الدالة الرئيسية — توليد بلاغ
# ============================================================
def generate_report(victim_number, reason="spam"):
    """
    يولد بلاغ كامل مع كل الروابط
    Returns: dict فيه كل المعلومات
    """
    number = normalize_number(victim_number)
    if not number:
        return {"error": "رقم غير صالح"}

    template = pick_template(reason)
    to_email = pick_random_email()

    # ⚠️ ملاحظة: Gmail بيفصل بين السطور بـ \n عادي
    subject = template["subject"].format(number=number)
    body = template["body"].format(
        number=number,
        date=time.strftime("%Y-%m-%d"),
        time=time.strftime("%H:%M"),
        days=random.randint(3, 20),
    )

    links = {
        "gmail": build_gmail_link(to_email, subject, body),
        "outlook": build_outlook_link(to_email, subject, body),
        "yahoo": build_yahoo_link(to_email, subject, body),
        "mailto": build_mailto_link(to_email, subject, body),
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "reason": reason,
        "number": number,
    }
    return links

# ============================================================
# [6] Session Management
# ============================================================
def create_report_session(chat_id, victim_number, reason):
    """ينشئ session لمتابعة البلاغات"""
    if not redis_client:
        return None
    try:
        session_id = uuid.uuid4().hex[:12]
        redis_client.setex(
            f"wa_report:{session_id}",
            86400 * 7,
            json.dumps({
                "session_id": session_id,
                "chat_id": str(chat_id),
                "victim_number": victim_number,
                "reason": reason,
                "reports_sent": 0,
                "created_at": time.time(),
            }, ensure_ascii=False)
        )
        return session_id
    except Exception as e:
        logger.exception(f"create_report_session error: {e}")
        return None

def get_report_session(session_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"wa_report:{session_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None

def log_report_sent(session_id):
    """يزود عداد البلاغات"""
    if not redis_client:
        return 0
    try:
        raw = redis_client.get(f"wa_report:{session_id}")
        if not raw:
            return 0
        data = json.loads(raw)
        data["reports_sent"] = data.get("reports_sent", 0) + 1
        data["last_report_at"] = time.time()
        redis_client.setex(
            f"wa_report:{session_id}",
            86400 * 7,
            json.dumps(data, ensure_ascii=False)
        )
        metrics.inc_counter("wa_email_reports_sent")
        return data["reports_sent"]
    except Exception as e:
        logger.warning(f"log_report_sent error: {e}")
        return 0

def get_user_report_history(chat_id, limit=20):
    """جلب سجل بلاغات المستخدم"""
    if not redis_client:
        return []
    try:
        items = redis_client.lrange(f"wa_report_history:{chat_id}", 0, limit - 1) or []
        result = []
        for item in items:
            try:
                result.append(json.loads(item))
            except Exception:
                continue
        return result
    except Exception:
        return []

def add_to_history(chat_id, victim_number, reason):
    """يضيف بلاغ للسجل"""
    if not redis_client:
        return
    try:
        redis_client.lpush(
            f"wa_report_history:{chat_id}",
            json.dumps({
                "number": victim_number,
                "reason": reason,
                "timestamp": time.time(),
                "date_str": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }, ensure_ascii=False)
        )
        redis_client.ltrim(f"wa_report_history:{chat_id}", 0, 99)
        redis_client.expire(f"wa_report_history:{chat_id}", 86400 * 30)
    except Exception as e:
        logger.warning(f"add_to_history error: {e}")
