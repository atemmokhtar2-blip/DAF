# whatsapp_report_generator.py
# ============================================================
# WhatsApp Report Generator v6.0
# Multi-Channel + Multi-Language + Blast Mode
# 5 إيميلات + 5 لغات + 250 قالب + Anti-Repeat
# ============================================================
import os
import time
import json
import uuid
import random
import urllib.parse
from datetime import datetime

from config import redis_client, PUBLIC_URL
from logging_config import get_logger
from monitoring import metrics

logger = get_logger("wa_report_gen")


# ============================================================
# [1] ★★★ 5 إيميلات واتساب (Multi-Channel) ★★★
# ============================================================
WA_REPORT_CHANNELS = {
    "abuse": {
        "email": "abuse@whatsapp.com",
        "name": "Abuse Team",
    },
    "support": {
        "email": "support@whatsapp.com",
        "name": "Support Team",
    },
    "security": {
        "email": "security@whatsapp.com",
        "name": "Security Team",
    },
    "android": {
        "email": "android-support@whatsapp.com",
        "name": "Android Support",
    },
    "ios": {
        "email": "iphone-support@whatsapp.com",
        "name": "iOS Support",
    },
}

WA_REPORT_EMAILS = [ch["email"] for ch in WA_REPORT_CHANNELS.values()]


# ============================================================
# [2] ★★★ بيانات ديناميكية (5 لغات) ★★★
# ============================================================
SENDER_NAMES = {
    "en": [
        "Ahmed Mohamed", "Sara Ali", "Mahmoud Hassan", "Nour Ibrahim",
        "Omar Khaled", "Fatma Sayed", "Youssef Adel", "Mona Farouk",
        "Khaled Tarek", "Layla Ahmed", "Hassan Mostafa", "Dina Samir",
        "Ali Gamal", "Rana Waleed", "Mostafa Nabil", "Heba Rashad",
        "Mohamed Salim", "Yasmin Fawzy", "Karim Hossam", "Salma Ehab",
    ],
    "ar": [
        "أحمد محمد", "سارة علي", "محمود حسن", "نور إبراهيم",
        "عمر خالد", "فاطمة سيد", "يوسف عادل", "منى فاروق",
        "خالد طارق", "ليلى أحمد", "حسن مصطفى", "دينا سمير",
    ],
    "fr": [
        "Ahmed Mohamed", "Sara Ali", "Karim Ben Salah", "Nadia Haddad",
        "Youssef Aloui", "Leila Mansour", "Omar Trabelsi", "Samira Khalil",
    ],
    "es": [
        "Ahmed Mohamed", "Sara Ali", "Karim Hossam", "Maria Lopez",
        "Carlos Rodriguez", "Ana Martinez", "Diego Fernandez", "Sofia Garcia",
    ],
    "de": [
        "Ahmed Mohamed", "Sara Ali", "Karim Hossam", "Anna Schmidt",
        "Thomas Müller", "Julia Weber", "Michael Fischer", "Lisa Wagner",
    ],
}

SENDER_LOCATIONS = [
    "Cairo, Egypt", "Alexandria, Egypt", "Giza, Egypt",
    "Dubai, UAE", "Riyadh, Saudi Arabia", "Amman, Jordan",
    "Kuwait City, Kuwait", "Doha, Qatar", "Casablanca, Morocco",
    "Tunis, Tunisia", "Beirut, Lebanon", "Baghdad, Iraq",
    "Paris, France", "Madrid, Spain", "Berlin, Germany",
    "London, UK", "Rome, Italy", "Amsterdam, Netherlands",
]

DEVICES = [
    "iPhone 14 Pro", "iPhone 15", "iPhone 15 Pro Max",
    "Samsung Galaxy S23", "Samsung Galaxy S24", "Samsung Galaxy Note 20",
    "Huawei P50", "Xiaomi 13 Pro", "Google Pixel 7",
    "OnePlus 11", "Oppo Reno 10", "Realme GT 5",
]

LOST_AMOUNTS = [
    "$500", "$1,200", "$2,500", "$800", "$3,000",
    "$150", "$5,000", "$450", "€850", "€1,500",
    "EGP 15,000", "SAR 3,000", "AED 2,500", "$750", "$1,800",
]

SPECIFIC_TIMES = [
    "02:15 AM", "03:45 AM", "11:30 PM", "01:20 AM",
    "04:50 AM", "12:30 AM", "02:00 PM", "10:15 AM",
    "11:55 PM", "03:30 AM", "05:20 AM", "11:45 PM",
]


# ============================================================
# [3] ★★★ 50 قالب × 5 لغات = 250 قالب ★★★
# ============================================================
REPORT_TEMPLATES = {

    # ═══════════════════════════════════════════════════
    # ENGLISH — SPAM (5 قوالب)
    # ═══════════════════════════════════════════════════
    "en": {
        "spam": [
            {
                "id": "en_spam_01",
                "subject": "URGENT: Persistent spam from {number}",
                "body": """Dear WhatsApp Trust & Safety Team,

I am writing to file a formal complaint against the WhatsApp number {number}, which has been repeatedly sending me unsolicited spam messages containing suspicious links and fraudulent offers.

This account has sent me over 50 messages in the past {days} days. Despite blocking the number twice, the messages continue arriving from similar accounts linked to the same operator.

REPORTED NUMBER: {number}
INCIDENT DATE: {date}
INCIDENT TIME: {time}
CATEGORY: Spam / Unsolicited messages
FREQUENCY: Multiple times daily
DURATION: Over {days} days

The content includes fake lottery winnings, suspicious investment schemes, and phishing links disguised as bank notifications.

I request immediate suspension of this account to protect other users from this campaign.

Screenshots available upon request.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_spam_02",
                "subject": "Multiple users reporting {number} for organized spam",
                "body": """Hello WhatsApp Support,

I am reporting an organized spam operation running through the number {number}.

NUMBER: {number}
ISSUE: Bulk spam with malicious links
REPORT DATE: {date}
MESSAGE COUNT: 30+ in {days} days

This account is part of a wider spam network. Multiple contacts in my address book have received identical messages from similar numbers, all pushing the same fake investment scheme.

The messages contain:
- Shortened URLs masking phishing sites
- Fake "you won" notifications
- Requests to share the message with 10 contacts

I have already blocked and reported this number inside the app, but the spam continues. I am submitting this formal report as a final step.

Please investigate this number and the associated network urgently.

Regards,
{sender_name}"""
            },
            {
                "id": "en_spam_03",
                "subject": "Formal complaint: Spam campaign {number}",
                "body": """Dear WhatsApp Trust & Safety,

COMPLAINT TYPE: Persistent Spam
REPORTED NUMBER: {number}
DATE: {date}
DURATION: {days} days
STATUS: Ongoing

I am receiving continuous spam messages from {number} despite blocking the account multiple times. This clearly violates WhatsApp's Community Standards and Terms of Service (Section 5, Subsection 3.2 - Bulk Messaging).

The account uses rotating display names to avoid detection. Each message contains:
- Fake government notifications
- Suspicious prize claims
- Phishing links mimicking major banks

Previous reports via the in-app tool have had no effect. I am now escalating this complaint formally.

I request:
1. Immediate account termination
2. Investigation of linked accounts
3. Confirmation of action taken

Regards,
{sender_name}"""
            },
            {
                "id": "en_spam_04",
                "subject": "URGENT: Automated spam bot using {number}",
                "body": """To: WhatsApp Abuse Team

I am filing an urgent complaint about an automated spam bot operating through {number}.

REPORTED NUMBER: {number}
THREAT LEVEL: High
COMPLAINT DATE: {date}
DETECTED AT: {specific_time}

Behavioral indicators:
- Messages sent at {specific_time} and other unusual hours
- Identical formatting across multiple messages
- Immediate response time (suggesting automation)
- Message content: fake job offers and crypto schemes

The bot has contacted me and at least 8 of my contacts. This violates WhatsApp's policy on automated messaging and bulk spam.

I have collected screenshots and message timestamps for evidence.

Please terminate this account immediately.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_spam_05",
                "subject": "Recurring spam from {number} - Multiple reports",
                "body": """WhatsApp Security Team,

I am submitting a formal complaint regarding recurring spam from {number}.

REPORTED: {number}
COMPLAINT DATE: {date}
PRIOR BLOCKS: 2
NEW ACCOUNTS CREATED: 3+

This individual continues to bypass blocks by creating new accounts and re-contacting me. Each iteration uses different display names but identical message patterns.

Messages received so far:
- 15 promotional/spam messages
- 8 fake investment offers
- 5 phishing attempts disguised as delivery notifications

This persistent behavior constitutes clear harassment and violates WhatsApp's policies on platform abuse.

I request permanent action against the operator behind these accounts.

Regards,
{sender_name}"""
            },
        ],
        "scam": [
            {
                "id": "en_scam_01",
                "subject": "EMERGENCY: Financial fraud from {number}",
                "body": """EMERGENCY FRAUD REPORT

To: WhatsApp Trust & Safety Team

I am reporting a serious financial fraud operation running on WhatsApp through the number {number}.

FRAUD CATEGORY: Financial scam / Bank impersonation
REPORTED NUMBER: {number}
DATE OF REPORT: {date}
LOSSES: {amount}

This account contacted me claiming to be from my bank's security department. They requested:
- Full card number
- CVV code
- OTP codes
- PIN

I initially complied but realized it was a scam after {amount} was taken from my account.

IMMEDIATE ACTIONS REQUESTED:
1. Suspend account {number} immediately
2. Preserve all chat logs for police investigation
3. Report to relevant financial authorities
4. Warn other users who received similar messages

I have filed a police report and can provide the reference number upon request.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_scam_02",
                "subject": "Investment scam - {number} - Multiple victims",
                "body": """Dear WhatsApp Support,

I am filing an urgent complaint regarding a large-scale investment scam being operated via WhatsApp number {number}.

NUMBER: {number}
SCAM TYPE: Fake crypto/investment scheme
REPORT DATE: {date}
ESTIMATED VICTIMS: 5+ in my network

This account has:
- Promised unrealistic returns (300%+ monthly)
- Requested deposits via crypto/transfer
- Created fake "trading dashboards" showing profits
- Refused all withdrawal requests
- Disappeared after receiving {amount}

I have documented:
- Full chat history
- Transaction records
- Fake dashboard screenshots
- Contact information of other victims

This is an organized fraud operation. I request immediate termination and referral to authorities.

Regards,
{sender_name}"""
            },
            {
                "id": "en_scam_03",
                "subject": "Romance scam (pig butchering) from {number}",
                "body": """To Whom It May Concern,

I am reporting a romance scam (pig butchering) being operated from WhatsApp number {number}.

REPORTED: {number}
SCAM START: {days} days ago
REPORT DATE: {date}
LOSSES: {amount}

SCAM PATTERN:
1. Initial contact via wrong number excuse
2. Building fake emotional relationship over {days} days
3. Introducing "investment opportunities" through trusted contacts
4. Gradual escalation to larger deposits
5. Disappearance after receiving {amount}

I have:
- Screenshots of the entire conversation
- Transaction history
- Photos the scammer claimed were theirs (verified as stolen)

This is a sophisticated scam targeting vulnerable individuals. Please terminate this account immediately and preserve all data.

Regards,
{sender_name}"""
            },
            {
                "id": "en_scam_04",
                "subject": "Job scam from {number} - URGENT",
                "body": """Dear WhatsApp Team,

I am reporting a fake job offer scam from WhatsApp number {number}.

NUMBER: {number}
SCAM TYPE: Fake job offer requiring upfront payment
REPORT DATE: {date}
LOSSES: {amount}

The operator:
- Claimed to represent a well-known company
- Offered a remote job with unrealistic salary
- Requested "registration fee" of {amount}
- Requested ID documents and bank details
- Disappeared after receiving payment

Multiple people have been tricked by this same operation. I have identified 3 victims in my network.

Evidence collected:
- Job offer screenshots
- Payment confirmations
- Fake company documents
- Contact details of other victims

Request immediate termination and referral to fraud authorities.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_scam_05",
                "subject": "Bank impersonation scam: {number}",
                "body": """Dear WhatsApp Support Team,

I am reporting a bank impersonation scam from number {number}.

REPORTED NUMBER: {number}
IMPERSONATED BANK: [Major bank]
REPORT DATE: {date}
LOSSES: {amount}

The scammer:
- Used official bank logo as profile
- Sent message from "Bank Security Department"
- Claimed my account had suspicious activity
- Requested I "verify" by providing card details
- Also requested OTP codes sent to my phone

I provided partial information before realizing it was a scam. My bank account shows unauthorized transaction of {amount}.

I have:
- Filed a police report
- Notified my bank (case #{report_id})
- Collected all chat evidence

Please terminate this account urgently.

Regards,
{sender_name}
{sender_location}"""
            },
        ],
        "harassment": [
            {
                "id": "en_har_01",
                "subject": "HARASSMENT: Repeated threats from {number}",
                "body": """URGENT HARASSMENT COMPLAINT

To: WhatsApp Trust & Safety Team

I am filing a formal harassment complaint against WhatsApp number {number}.

REPORTED NUMBER: {number}
HARASSMENT TYPE: Repeated threatening messages
DATE: {date}
DURATION: Over {days} days
MESSAGES RECEIVED: 50+

This user has been sending:
- Direct physical threats to me and my family
- Abusive and insulting messages
- Graphic violent content
- Unsolicited explicit materials

I feel unsafe using WhatsApp. My family has been affected emotionally.

I have taken these steps:
- Filed a police report (case #{report_id})
- Documented all messages with timestamps
- Saved screenshots as evidence

I request:
1. Immediate account suspension
2. Preservation of chat logs for police
3. Cooperation with law enforcement if needed

Please act urgently.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_har_02",
                "subject": "Cyberbullying from {number}",
                "body": """To WhatsApp Trust & Safety,

I am reporting continued cyberbullying from number {number}.

NUMBER: {number}
BULLYING TYPE: Body shaming / Verbal abuse / Mocking
DATE: {date}
DURATION: {days} days

This person has been systematically harassing me through:
- Insulting messages about my appearance
- Mocking content sent to our mutual contacts
- Public humiliation attempts
- Sharing my private information without consent
- Encouraging others to contact me

The emotional impact on me has been severe. This is not just a disagreement — it's sustained harassment.

I have saved all messages and screenshots.

Request immediate action against this account.

Regards,
{sender_name}"""
            },
            {
                "id": "en_har_03",
                "subject": "Stalking via WhatsApp: {number}",
                "body": """URGENT: STALKING REPORT

To: WhatsApp Security Team

I am reporting a stalking case via WhatsApp number {number}.

REPORTED NUMBER: {number}
DATE: {date}
PATTERN: Obsessive stalking behavior
DURATION: {days} days

This individual has been:
- Sending messages at all hours, including {specific_time}
- Creating multiple accounts to bypass my blocks (3+ so far)
- Tracking my online activity
- Contacting my friends and family through WhatsApp
- Showing up at locations I mentioned in chats

I have filed a police report (case #{report_id}). Local authorities are involved.

IMMEDIATE ACTIONS NEEDED:
1. Terminate account {number}
2. Provide chat logs to law enforcement
3. Block all related accounts

My safety is at risk.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_har_04",
                "subject": "Threatening messages from {number}",
                "body": """Dear WhatsApp Support,

I am reporting threatening behavior from number {number}.

REPORTED NUMBER: {number}
DATE: {date}
THREAT TYPE: Physical threats
THREATENED PARTIES: Myself, my family

Sample threats received (paraphrased):
- "I know where you live"
- "You'll regret this"
- "I'll make you pay"

These are direct physical threats, not just angry messages. I take them very seriously.

I have:
- Screenshot all threatening messages
- Filed a police report
- Notified my family and workplace security

Please suspend this account immediately to prevent further threats.

Regards,
{sender_name}"""
            },
            {
                "id": "en_har_05",
                "subject": "Sexual harassment via {number}",
                "body": """CONFIDENTIAL: Sexual Harassment Report

To: WhatsApp Trust & Safety Team

I am reporting sexual harassment from number {number}.

REPORTED NUMBER: {number}
DATE: {date}
DURATION: {days} days

This user has sent:
- Sexually explicit messages without consent
- Unsolicited explicit images
- Sexually aggressive demands
- Requests for inappropriate content

This behavior is unwelcome, repeated, and has created a hostile environment for me on WhatsApp.

I have:
- Screenshot everything
- Documented dates and times
- Reported to local authorities

This violates WhatsApp's policy on sexual harassment and content. Immediate action is required.

Regards,
{sender_name}"""
            },
        ],
        "fake": [
            {
                "id": "en_fake_01",
                "subject": "Fake account impersonating me: {number}",
                "body": """Dear WhatsApp Support,

I am reporting a fake/impersonation account on WhatsApp.

REPORTED NUMBER: {number}
REASON: Impersonation of my personal identity
DATE: {date}

This account is using:
- My photos (stolen from social media)
- My name
- My biography details
- Fake claims to know my contacts

The operator is using this fake identity to:
- Deceive my friends and family
- Damage my reputation
- Potentially scam people who trust me

Multiple contacts have been fooled. I have verified:
- I did not create this account
- The photos were stolen
- The account is not associated with me

Please verify and take down this fake account.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_fake_02",
                "subject": "Business impersonation: {number}",
                "body": """To WhatsApp Business Team,

I am reporting a fake account impersonating our legitimate business.

REPORTED NUMBER: {number}
IMPERSONATED BRAND: [Your Business]
DATE: {date}

This account is:
- Using our exact brand name
- Copying our logo and branding elements
- Presenting itself as our official WhatsApp channel
- Misleading customers into fake transactions
- Damaging our brand reputation

We have verified:
- This is NOT our account
- We have never contacted these customers
- The operator has no affiliation with us

We request:
1. Immediate verification of this account
2. Removal/takeover prevention
3. Notification to affected customers

Legal action will follow if not addressed.

Regards,
{sender_name}
For [Business Name]"""
            },
            {
                "id": "en_fake_03",
                "subject": "Catfishing account {number}",
                "body": """Dear WhatsApp Support,

I am reporting a catfishing account operating on WhatsApp.

NUMBER: {number}
DATE: {date}
REASON: Fake profile with stolen photos

This account is using photos of someone else to create a fake identity. The purpose is:
- Deceptive romantic relationships
- Financial exploitation of victims
- Potential trafficking recruitment

Multiple people in my network have been targeted. The user:
- Refuses video calls
- Always has excuses
- Uses copy-paste conversation templates
- Requests money after building "trust"

I have:
- Reverse image searched the photos (found on other profiles)
- Connected with 3 other victims
- Documented all chats

Please investigate and take appropriate action.

Thanks,
{sender_name}"""
            },
            {
                "id": "en_fake_04",
                "subject": "Government impersonation - {number}",
                "body": """URGENT: OFFICIAL IMPERSONATION

To: WhatsApp Trust & Safety

I am reporting an account impersonating a government entity.

REPORTED NUMBER: {number}
IMPERSONATED: Government department
DATE: {date}

This account claims to represent a government agency and is:
- Requesting personal documents (ID, passport)
- Demanding payments for "fines" or "fees"
- Threatening legal action for non-compliance
- Using fake official seals and logos

This is a serious offense punishable by law in {sender_location}.

I have:
- Screenshots of all communications
- The fake credentials they provided
- Reports from other targeted users

This is a coordinated impersonation operation. Immediate action required.

Regards,
{sender_name}"""
            },
            {
                "id": "en_fake_05",
                "subject": "Charity impersonation: {number}",
                "body": """Dear WhatsApp Trust & Safety,

I am reporting a fake charity account.

REPORTED NUMBER: {number}
IMPERSONATED: [Legitimate charity name]
DATE: {date}

This account is:
- Using a well-known charity's name and logo
- Soliciting donations for fake causes
- Providing fraudulent donation receipts
- Diverting funds to personal accounts

The real charity has confirmed this is NOT an official account.

At least {amount} has been collected from unsuspecting donors. This is fraud.

Request immediate termination and referral to financial authorities.

Regards,
{sender_name}"""
            },
        ],
        "illegal": [
            {
                "id": "en_ill_01",
                "subject": "Illegal drug sales via {number}",
                "body": """Dear WhatsApp Trust & Safety,

I am reporting illegal activities conducted via number {number}.

NUMBER: {number}
ILLEGAL ACTIVITY: Drug distribution
DATE: {date}
EVIDENCE LEVEL: Strong

This account is using WhatsApp to:
- Sell controlled substances
- Coordinate deliveries
- Share images of products
- Process payments

Evidence collected:
- Chat conversations
- Product images
- Pricing menus
- Delivery arrangements

I have:
- Screenshot all evidence
- Notified local law enforcement (case #{report_id})

Request immediate termination and preservation of all data for police investigation.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_ill_02",
                "subject": "URGENT: Child safety violation - {number}",
                "body": """URGENT: CHILD SAFETY REPORT

To: WhatsApp Trust & Safety Team

I am reporting a serious child safety violation.

REPORTED NUMBER: {number}
VIOLATION TYPE: Inappropriate contact with minors
DATE: {date}
SEVERITY: Critical

This account has been:
- Contacting minors with inappropriate content
- Attempting to arrange meetings
- Requesting photos from underage users
- Using manipulation techniques

I have reason to believe there are multiple victims.

IMMEDIATE ACTIONS TAKEN:
- Reported to local child protection authorities
- Filed police report (case #{report_id})
- Preserved all evidence

I request WhatsApp to:
1. Terminate account {number} IMMEDIATELY
2. Preserve all chat logs and images
3. Cooperate fully with law enforcement

This is a priority case involving child safety.

Regards,
{sender_name}"""
            },
            {
                "id": "en_ill_03",
                "subject": "Human trafficking suspicion: {number}",
                "body": """CONFIDENTIAL REPORT

To: WhatsApp Security Team

I am reporting suspicious activity suggesting human trafficking.

NUMBER: {number}
DATE: {date}
SUSPICION LEVEL: High

Observed patterns:
- Job offers with vague terms and unusual promises
- Requests for ID documents and personal info
- Travel arrangement discussions for vulnerable individuals
- Multiple similar accounts contacting potential victims
- Use of coded language

I am concerned about potential victims being recruited through this account.

I have documented everything and alerted anti-trafficking organizations.

Request immediate investigation and coordination with appropriate authorities.

Regards,
{sender_name}
{sender_location}"""
            },
            {
                "id": "en_ill_04",
                "subject": "Extortion ring via {number}",
                "body": """Dear WhatsApp Support,

I am reporting an organized extortion ring.

MAIN NUMBER: {number}
DATE: {date}
OPERATION TYPE: Coordinated blackmail
ESTIMATED VICTIMS: 5+

The operation:
- Obtains personal info through various means
- Threatens victims with exposure
- Demands payments in crypto
- Uses multiple accounts to avoid detection
- Has successfully extorted from at least 3 identified victims

Amounts demanded: {amount} per victim

I have:
- Documented the network structure
- Collected victim testimonials
- Filed police report

Request immediate termination of all linked accounts.

Regards,
{sender_name}"""
            },
            {
                "id": "en_ill_05",
                "subject": "Hacking services advertised: {number}",
                "body": """URGENT: CRIMINAL SERVICES

To: WhatsApp Security Team

I am reporting an account advertising hacking services.

REPORTED NUMBER: {number}
DATE: {date}
ILLEGAL SERVICES OFFERED:
- WhatsApp account hacking
- Social media account takeover
- Email hacking
- Financial account access

The operator:
- Advertises "guaranteed results"
- Shows fake testimonials
- Requests upfront payments
- Has scammed multiple victims themselves

This is not only illegal but also a scam targeting people seeking illegal services.

I have documented all evidence and reported to cybercrime authorities.

Request immediate action.

Regards,
{sender_name}"""
            },
        ],
    },

    # ═══════════════════════════════════════════════════
    # ARABIC — 25 قالب
    # ═══════════════════════════════════════════════════
    "ar": {
        "spam": [
            {
                "id": "ar_spam_01",
                "subject": "عاجل: رسائل مزعجة متكررة من {number}",
                "body": """السادة فريق الأمان في واتساب،

أكتب إليكم لتقديم شكوى رسمية ضد رقم الواتساب {number} الذي يرسل لي رسائل مزعجة بشكل متكرر تحتوي على روابط مشبوهة وعروض احتيالية.

الرقم المُبلَّغ عنه: {number}
تاريخ الحادثة: {date}
وقت الحادثة: {time}
التصنيف: رسائل مزعجة
التكرار: عدة مرات يومياً
المدة: أكثر من {days} يوم

يتضمن المحتوى:
- جوائز وهمية
- مخططات استثمارية مشبوهة
- روابط تصيّد متنكرة في هيئة إشعارات بنكية

أطلب تعليق هذا الحساب فوراً لحماية المستخدمين الآخرين.

الصور متوفرة عند الطلب.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_spam_02",
                "subject": "عدة مستخدمين يبلغون عن {number} كحملة سبام",
                "body": """مرحباً فريق دعم واتساب،

أبلغ عن حملة سبام منظمة عبر الرقم {number}.

الرقم: {number}
المشكلة: رسائل جماعية بروابط خبيثة
تاريخ الإبلاغ: {date}
عدد الرسائل: أكثر من 30 خلال {days} يوم

هذا الحساب جزء من شبكة سبام أوسع. عدة جهات اتصال في دفتر هاتفي استقبلت رسائل متطابقة من أرقام مشابهة، جميعها تروج لنفس المخطط الاستثماري الوهمي.

تحتوي الرسائل على:
- روابط مختصرة تخفي مواقع تصيّد
- إشعارات "لقد فزت" وهمية
- طلبات لمشاركة الرسالة مع 10 جهات

قمت بحظر الرقم مرتين، لكن الرسائل مستمرة. أقدم هذا التقرير الرسمي كخطوة أخيرة.

الرجاء التحقيق العاجل في هذا الرقم والشبكة المرتبطة به.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_spam_03",
                "subject": "شكوى رسمية: حملة سبام {number}",
                "body": """السادة فريق الثقة والأمان في واتساب،

نوع الشكوى: سبام متكرر
الرقم المُبلَّغ: {number}
التاريخ: {date}
المدة: {days} يوم
الحالة: مستمر

أتلقى رسائل سبام متواصلة من الرقم {number} رغم حظره عدة مرات. هذا يخالف صراحة معايير المجتمع وشروط الخدمة (القسم 5، البند 3.2 - الرسائل الجماعية).

الحساب يستخدم أسماء عرض متغيرة لتفادي الكشف. كل رسالة تحتوي على:
- إشعارات حكومية وهمية
- ادعاءات جوائز مشبوهة
- روابط تصيّد تتنكر في هيئة بنوك كبرى

التقارير السابقة عبر التطبيق لم يكن لها تأثير. أرفع الشكوى رسمياً الآن.

أطلب:
1. إنهاء الحساب فوراً
2. التحقيق في الحسابات المرتبطة
3. تأكيد الإجراء المتخذ

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_spam_04",
                "subject": "عاجل: بوت سبام آلي عبر {number}",
                "body": """إلى: فريق الإبلاغ عن الإساءة في واتساب

أقدم شكوى عاجلة بخصوص بوت سبام آلي يعمل عبر الرقم {number}.

الرقم المُبلَّغ: {number}
مستوى التهديد: مرتفع
تاريخ الشكوى: {date}
تم اكتشافه في: {specific_time}

مؤشرات السلوك:
- رسائل تُرسل في {specific_time} وساعات غير معتادة
- تنسيق متطابق في عدة رسائل
- سرعة رد فورية (تدل على الأتمتة)
- محتوى الرسائل: عروض عمل وهمية ومخططات عملات رقمية

البوت تواصل معي ومع 8 من جهات اتصالي على الأقل. هذا يخالف سياسة واتساب بشأن الرسائل الآلية والسبام.

جمعت لقطات شاشة وأوقات الرسائل كأدلة.

الرجاء إنهاء هذا الحساب فوراً.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_spam_05",
                "subject": "سبام متكرر من {number} - تقارير متعددة",
                "body": """فريق أمان واتساب،

أقدم شكوى رسمية بخصوص سبام متكرر من الرقم {number}.

المُبلَّغ عنه: {number}
تاريخ الشكوى: {date}
حظر سابق: 2
حسابات جديدة: 3+

يستمر هذا الشخص في تجاوز الحظر بإنشاء حسابات جديدة والتواصل معي. كل مرة يستخدم أسماء عرض مختلفة لكن أنماط رسائل متطابقة.

الرسائل المستلمة حتى الآن:
- 15 رسالة دعائية/سبام
- 8 عروض استثمار وهمية
- 5 محاولات تصيّد متنكرة في هيئة إشعارات تسليم

هذا السلوك المتكرر يشكل مضايقة واضحة ويخالف سياسات واتساب بشأن إساءة استخدام المنصة.

أطلب اتخاذ إجراء دائم ضد المشغل وراء هذه الحسابات.

مع التحية،
{sender_name}"""
            },
        ],
        "scam": [
            {
                "id": "ar_scam_01",
                "subject": "طارئ: احتيال مالي من {number}",
                "body": """تقرير احتيال طارئ

إلى: فريق الثقة والأمان في واتساب

أبلغ عن عملية احتيال مالي خطيرة تعمل عبر رقم واتساب {number}.

فئة الاحتيال: احتيال مالي / انتحال بنكي
الرقم المُبلَّغ: {number}
تاريخ التقرير: {date}
الخسائر: {amount}

هذا الحساب تواصل معي مدعياً أنه من قسم أمان البنك. طلب مني:
- رقم البطاقة كاملاً
- رمز CVV
- رموز OTP
- الرقم السري

امتثلت في البداية لكن أدركت أنها عملية احتيال بعد أن تم سحب {amount} من حسابي.

الإجراءات المطلوبة:
1. تعليق الحساب {number} فوراً
2. حفظ سجلات المحادثة للتحقيق الشرطي
3. إبلاغ السلطات المالية المختصة
4. تحذير المستخدمين الآخرين

قدمت بلاغاً شرطياً ويمكنني تقديم رقم المرجع عند الطلب.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_scam_02",
                "subject": "احتيال استثماري - {number} - عدة ضحايا",
                "body": """السادة فريق دعم واتساب،

أقدم شكوى عاجلة بخصوص عملية احتيال استثماري واسعة النطاق تعمل عبر رقم واتساب {number}.

الرقم: {number}
نوع الاحتيال: مخطط استثماري/عملات وهمي
تاريخ التقرير: {date}
الضحايا المُقدَّرون: 5+ في شبكتي

هذا الحساب:
- وعد بأرباح غير واقعية (أكثر من 300% شهرياً)
- طلب إيداعات عبر العملات الرقمية
- أنشأ لوحات تداول وهمية تعرض أرباحاً مزيفة
- رفض جميع طلبات السحب
- اختفى بعد استلام {amount}

وثّقت:
- سجل محادثة كامل
- سجلات المعاملات
- صور اللوحات الوهمية
- بيانات اتصال ضحايا آخرين

هذه عملية احتيال منظمة. أطلب الإنهاء الفوري والإحالة للسلطات.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_scam_03",
                "subject": "احتيال عاطفي (ذبح الخنازير) من {number}",
                "body": """إلى كل من يهمه الأمر،

أبلغ عن احتيال عاطفي (ذبح الخنازير) يعمل من رقم واتساب {number}.

المُبلَّغ: {number}
بداية الاحتيال: قبل {days} يوم
تاريخ التقرير: {date}
الخسائر: {amount}

نمط الاحتيال:
1. تواصل أولي بذريعة "رقم خاطئ"
2. بناء علاقة عاطفية وهمية خلال {days} يوم
3. تقديم "فرص استثمارية" عبر أطراف موثوقة
4. تصعيد تدريجي لإيداعات أكبر
5. اختفاء بعد استلام {amount}

لدي:
- لقطات شاشة للمحادثة كاملة
- سجل المعاملات
- الصور التي ادعى المحتال أنها له (تأكدت أنها مسروقة)

هذا احتيال متطور يستهدف الأفراد الضعفاء. الرجاء إنهاء الحساب فوراً وحفظ جميع البيانات.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_scam_04",
                "subject": "احتيال وظيفي من {number} - عاجل",
                "body": """فريق واتساب،

أبلغ عن احتيال عرض عمل وهمي من رقم واتساب {number}.

الرقم: {number}
نوع الاحتيال: عرض عمل وهمي يتطلب دفعاً مسبقاً
تاريخ التقرير: {date}
الخسائر: {amount}

المشغل:
- ادعى تمثيل شركة معروفة
- عرض عملاً عن بعد براتب غير واقعي
- طلب "رسوم تسجيل" بقيمة {amount}
- طلب وثائق هوية وبيانات بنكية
- اختفى بعد استلام المبلغ

عدة أشخاص تعرضوا للخداع بنفس العملية. حددت 3 ضحايا في شبكتي.

الأدلة المجموعة:
- لقطات شاشة لعرض العمل
- تأكيدات الدفع
- وثائق الشركة المزيفة
- بيانات اتصال ضحايا آخرين

أطلب الإنهاء الفوري والإحالة لسلطات الاحتيال.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_scam_05",
                "subject": "احتيال انتحال بنكي: {number}",
                "body": """السادة فريق دعم واتساب،

أبلغ عن احتيال انتحال بنكي من الرقم {number}.

الرقم المُبلَّغ: {number}
البنك المُنتحَل: [بنك كبير]
تاريخ التقرير: {date}
الخسائر: {amount}

المحتال:
- استخدم شعار البنك الرسمي كصورة شخصية
- أرسل رسالة من "قسم أمان البنك"
- ادعى وجود نشاط مشبوه في حسابي
- طلب مني "التحقق" بتقديم بيانات البطاقة
- طلب أيضاً رموز OTP المرسلة لهاتفي

قدمت معلومات جزئية قبل إدراكي أنها عملية احتيال. حسابي البنكي يُظهر معاملة غير مصرح بها بقيمة {amount}.

لدي:
- بلاغ شرطي
- إشعار للبنك (قضية #{report_id})
- جميع أدلة المحادثة

الرجاء إنهاء هذا الحساب بشكل عاجل.

مع التحية،
{sender_name}
{sender_location}"""
            },
        ],
        "harassment": [
            {
                "id": "ar_har_01",
                "subject": "مضايقة: تهديدات متكررة من {number}",
                "body": """شكوى مضايقة عاجلة

إلى: فريق الثقة والأمان في واتساب

أقدم شكوى مضايقة رسمية ضد رقم واتساب {number}.

الرقم المُبلَّغ: {number}
نوع المضايقة: رسائل تهديد متكررة
التاريخ: {date}
المدة: أكثر من {days} يوم
الرسائل المستلمة: 50+

يرسل هذا المستخدم:
- تهديدات جسدية مباشرة لي ولعائلتي
- رسائل مسيئة ومهينة
- محتوى عنيف صادم
- مواد إباحية غير مرغوب فيها

أشعر بعدم الأمان في استخدام واتساب. عائلتي تأثرت نفسياً.

اتخذت الخطوات التالية:
- بلاغ شرطي (قضية #{report_id})
- توثيق جميع الرسائل بالتوقيتات
- حفظ لقطات الشاشة كأدلة

أطلب:
1. تعليق الحساب فوراً
2. حفظ سجلات المحادثة للشرطة
3. التعاون مع السلطات إذا لزم الأمر

الرجاء التصرف بسرعة.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_har_02",
                "subject": "تنمّر إلكتروني من {number}",
                "body": """إلى فريق الثقة والأمان في واتساب،

أبلغ عن تنمّر إلكتروني مستمر من الرقم {number}.

الرقم: {number}
نوع التنمّر: تنمّر / إساءة لفظية / سخرية
التاريخ: {date}
المدة: {days} يوم

هذا الشخص يضايقني بشكل منهجي عبر:
- رسائل مهينة عن مظهري
- محتوى ساخر يُرسل لمعارفي المشتركين
- محاولات إذلال علني
- مشاركة معلوماتي الخاصة بدون إذن
- تشجيع الآخرين على التواصل معي

التأثير العاطفي عليّ كان شديداً. هذه ليست خلافاً عادياً — إنها مضايقة مستمرة.

حفظت جميع الرسائل ولقطات الشاشة.

أطلب اتخاذ إجراء فوري ضد هذا الحساب.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_har_03",
                "subject": "ملاحقة عبر واتساب: {number}",
                "body": """عاجل: تقرير ملاحقة

إلى فريق أمان واتساب

أبلغ عن حالة ملاحقة عبر رقم واتساب {number}.

الرقم المُبلَّغ: {number}
التاريخ: {date}
النمط: سلوك ملاحقة هوسي
المدة: {days} يوم

هذا الفرد:
- يرسل رسائل في جميع الأوقات، بما في ذلك {specific_time}
- أنشأ عدة حسابات لتجاوز حظري (3+ حتى الآن)
- يتتبع نشاطي على الإنترنت
- يتواصل مع أصدقائي وعائلتي عبر واتساب
- يظهر في أماكن ذكرتها في المحادثات

قدمت بلاغاً شرطياً (قضية #{report_id}). السلطات المحلية متورطة.

إجراءات عاجلة مطلوبة:
1. إنهاء الحساب {number}
2. تسليم سجلات المحادثة للسلطات
3. حظر جميع الحسابات المرتبطة

سلامتي في خطر.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_har_04",
                "subject": "رسائل تهديد من {number}",
                "body": """فريق دعم واتساب،

أبلغ عن سلوك تهديدي من الرقم {number}.

الرقم المُبلَّغ: {number}
التاريخ: {date}
نوع التهديد: تهديدات جسدية
الطرف المهدَّد: أنا، عائلتي

أمثلة على التهديدات (مُعاد صياغتها):
- "أعرف أين تسكن"
- "سوف تندم على هذا"
- "سأجعلك تدفع الثمن"

هذه تهديدات جسدية مباشرة، ليست مجرد رسائل غاضبة. آخذها على محمل الجد.

لدي:
- لقطات شاشة لجميع رسائل التهديد
- بلاغ شرطي
- إشعار لعائلتي وأمن مكان عملي

الرجاء تعليق هذا الحساب فوراً لمنع المزيد من التهديدات.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_har_05",
                "subject": "تحرش جنسي عبر {number}",
                "body": """سري: تقرير تحرش جنسي

إلى فريق الثقة والأمان في واتساب

أبلغ عن تحرش جنسي من الرقم {number}.

الرقم المُبلَّغ: {number}
التاريخ: {date}
المدة: {days} يوم

أرسل هذا المستخدم:
- رسائل جنسية صريحة بدون موافقة
- صور إباحية غير مرغوب فيها
- مطالب جنسية عدوانية
- طلبات محتوى غير لائق

هذا السلوك غير مرحب به ومتكرر وخلق بيئة معادية لي على واتساب.

لدي:
- لقطات شاشة لكل شيء
- توثيق التواريخ والأوقات
- بلاغ للسلطات المحلية

هذا يخالف سياسة واتساب بشأن التحرش الجنسي والمحتوى. الإجراء الفوري مطلوب.

مع التحية،
{sender_name}"""
            },
        ],
        "fake": [
            {
                "id": "ar_fake_01",
                "subject": "حساب مزيف ينتحل شخصيتي: {number}",
                "body": """فريق دعم واتساب،

أبلغ عن حساب مزيف/انتحال شخصية على واتساب.

الرقم المُبلَّغ: {number}
السبب: انتحال هويتي الشخصية
التاريخ: {date}

هذا الحساب يستخدم:
- صوري (مسروقة من وسائل التواصل)
- اسمي
- تفاصيل سيرتي
- ادعاءات كاذبة بمعرفة جهات اتصالي

المشغل يستخدم هذه الهوية المزيفة لـ:
- خداع أصدقائي وعائلتي
- الإضرار بسمعتي
- الاحتيال المحتمل على من يثق بي

تم خداع عدة جهات اتصال. تحققت:
- لم أنشئ هذا الحساب
- الصور مسروقة
- الحساب غير مرتبط بي

الرجاء التحقق وإزالة هذا الحساب المزيف.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_fake_02",
                "subject": "انتحال نشاط تجاري: {number}",
                "body": """إلى فريق واتساب للأعمال،

أبلغ عن حساب مزيف ينتحل نشاطنا التجاري الشرعي.

الرقم المُبلَّغ: {number}
العلامة المُنتحَلة: [نشاطك التجاري]
التاريخ: {date}

هذا الحساب:
- يستخدم اسم علامتنا التجارية بالضبط
- ينسخ شعارنا وعناصر هويتنا
- يقدم نفسه كقناة واتساب الرسمية لنا
- يضلل العملاء إلى معاملات وهمية
- يضر بسمعة علامتنا

تحققنا:
- هذا ليس حسابنا
- لم نتواصل مع هؤلاء العملاء
- المشغل غير تابع لنا

نطلب:
1. التحقق الفوري من هذا الحساب
2. الإزالة ومنع الاستيلاء
3. إشعار العملاء المتأثرين

سيتم اتخاذ إجراء قانوني إن لم يتم التعامل مع الأمر.

مع التحية،
{sender_name}
نيابة عن [اسم النشاط]"""
            },
            {
                "id": "ar_fake_03",
                "subject": "حساب تصيّد عاطفي {number}",
                "body": """فريق دعم واتساب،

أبلغ عن حساب تصيّد عاطفي (catfishing) يعمل على واتساب.

الرقم: {number}
التاريخ: {date}
السبب: ملف شخصي مزيف بصور مسروقة

يستخدم هذا الحساب صور شخص آخر لإنشاء هوية مزيفة. الهدف:
- علاقات عاطفية خادعة
- استغلال مالي للضحايا
- تجنيد محتمل للاتجار

عدة أشخاص في شبكتي استُهدفوا. المستخدم:
- يرفض مكالمات الفيديو
- لديه أعذار دائماً
- يستخدم قوالب محادثة جاهزة
- يطلب مالاً بعد بناء "الثقة"

لدي:
- بحث عكسي للصور (وجدتها في ملفات أخرى)
- تواصل مع 3 ضحايا آخرين
- توثيق لجميع المحادثات

الرجاء التحقيق واتخاذ الإجراء المناسب.

شكراً،
{sender_name}"""
            },
            {
                "id": "ar_fake_04",
                "subject": "انتحال جهة حكومية - {number}",
                "body": """عاجل: انتحال مسؤول رسمي

إلى فريق الثقة والأمان في واتساب

أبلغ عن حساب ينتحل جهة حكومية.

الرقم المُبلَّغ: {number}
الجهة المُنتحَلة: إدارة حكومية
التاريخ: {date}

هذا الحساب يدعي تمثيل جهة حكومية وهو:
- يطلب وثائق شخصية (هوية، جواز سفر)
- يطالب بدفعات مقابل "غرامات" أو "رسوم"
- يهدد بإجراء قانوني عند عدم الامتثال
- يستخدم أختام وشعارات رسمية مزيفة

هذا جرم خطير معاقب عليه قانوناً في {sender_location}.

لدي:
- لقطات شاشة لجميع المحادثات
- بيانات الاعتماد المزيفة التي قدموها
- تقارير من مستخدمين آخرين مستهدفين

هذه عملية انتحال منظمة. الإجراء الفوري مطلوب.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_fake_05",
                "subject": "انتحال جمعية خيرية: {number}",
                "body": """السادة فريق الثقة والأمان في واتساب،

أبلغ عن حساب جمعية خيرية مزيف.

الرقم المُبلَّغ: {number}
الجمعية المُنتحَلة: [اسم جمعية شرعية]
التاريخ: {date}

هذا الحساب:
- يستخدم اسم وشعار جمعية خيرية معروفة
- يجمع تبرعات لأسباب وهمية
- يقدم إيصالات تبرع مزيفة
- يحوّل الأموال لحسابات شخصية

الجمعية الحقيقية أكدت أن هذا ليس حساباً رسمياً.

تم جمع {amount} على الأقل من متبرعين غير مدركين. هذا احتيال.

أطلب الإنهاء الفوري والإحالة للسلطات المالية.

مع التحية،
{sender_name}"""
            },
        ],
        "illegal": [
            {
                "id": "ar_ill_01",
                "subject": "بيع مخدرات غير قانوني عبر {number}",
                "body": """السادة فريق الثقة والأمان في واتساب،

أبلغ عن أنشطة غير قانونية تُمارس عبر الرقم {number}.

الرقم: {number}
النشاط غير القانوني: توزيع مخدرات
التاريخ: {date}
مستوى الأدلة: قوي

هذا الحساب يستخدم واتساب لـ:
- بيع مواد محظورة
- تنسيق عمليات التسليم
- مشاركة صور المنتجات
- معالجة المدفوعات

الأدلة المجمعة:
- محادثات
- صور المنتجات
- قوائم الأسعار
- ترتيبات التسليم

لدي:
- لقطات شاشة لجميع الأدلة
- إخطار لإنفاذ القانون المحلي (قضية #{report_id})

أطلب الإنهاء الفوري وحفظ جميع البيانات لتحقيق الشرطة.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_ill_02",
                "subject": "عاجل: انتهاك سلامة الأطفال - {number}",
                "body": """عاجل: تقرير سلامة أطفال

إلى فريق الثقة والأمان في واتساب

أبلغ عن انتهاك خطير لسلامة الأطفال.

الرقم المُبلَّغ: {number}
نوع الانتهاك: تواصل غير لائق مع قاصرين
التاريخ: {date}
الخطورة: حرجة

هذا الحساب:
- يتواصل مع قاصرين بمحتوى غير لائق
- يحاول ترتيب لقاءات
- يطلب صوراً من مستخدمين تحت السن
- يستخدم تقنيات التلاعب

لدي سبب للاعتقاد بوجود عدة ضحايا.

الإجراءات الفورية المتخذة:
- إبلاغ سلطات حماية الطفل المحلية
- بلاغ شرطي (قضية #{report_id})
- حفظ جميع الأدلة

أطلب من واتساب:
1. إنهاء الحساب {number} فوراً
2. حفظ جميع سجلات المحادثة والصور
3. التعاون الكامل مع إنفاذ القانون

هذه قضية ذات أولوية تتعلق بسلامة الأطفال.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_ill_03",
                "subject": "شبهة اتجار بالبشر: {number}",
                "body": """تقرير سري

إلى فريق أمان واتساب

أبلغ عن نشاط مشبوه يشير إلى اتجار بالبشر.

الرقم: {number}
التاريخ: {date}
مستوى الشبهة: مرتفع

الأنماط المرصودة:
- عروض عمل بشروط غامضة ووعود غير معتادة
- طلبات لوثائق هوية ومعلومات شخصية
- مناقشات ترتيبات السفر لأفراد ضعفاء
- عدة حسابات مشابهة تتواصل مع ضحايا محتملين
- استخدام لغة مشفرة

قلق بشأن ضحايا محتملين يتم تجنيدهم عبر هذا الحساب.

وثّقت كل شيء وأبلغت منظمات مكافحة الاتجار.

أطلب تحقيقاً فورياً وتنسيقاً مع السلطات المختصة.

مع التحية،
{sender_name}
{sender_location}"""
            },
            {
                "id": "ar_ill_04",
                "subject": "شبكة ابتزاز عبر {number}",
                "body": """فريق دعم واتساب،

أبلغ عن شبكة ابتزاز منظمة.

الرقم الرئيسي: {number}
التاريخ: {date}
نوع العملية: تخويف منسق
الضحايا المُقدَّرون: 5+

العملية:
- الحصول على معلومات شخصية بوسائل مختلفة
- تهديد الضحايا بالكشف
- مطالبة بدفعات بعملات رقمية
- استخدام حسابات متعددة لتفادي الكشف
- نجحت في ابتزاز 3 ضحايا على الأقل

المبالغ المطلوبة: {amount} لكل ضحية

لدي:
- توثيق هيكل الشبكة
- شهادات الضحايا
- بلاغ شرطي

أطلب الإنهاء الفوري لجميع الحسابات المرتبطة.

مع التحية،
{sender_name}"""
            },
            {
                "id": "ar_ill_05",
                "subject": "إعلان خدمات اختراق: {number}",
                "body": """عاجل: خدمات إجرامية

إلى فريق أمان واتساب

أبلغ عن حساب يعلن خدمات اختراق.

الرقم المُبلَّغ: {number}
التاريخ: {date}
الخدمات غير القانونية المعروضة:
- اختراق حسابات واتساب
- الاستيلاء على حسابات التواصل الاجتماعي
- اختراق البريد الإلكتروني
- الوصول للحسابات المالية

المشغل:
- يعلن "نتائج مضمونة"
- يعرض شهادات وهمية
- يطلب دفعات مسبقة
- احتال على عدة ضحايا بنفسه

هذا ليس فقط غير قانوني بل أيضاً احتيال يستهدف من يبحثون عن خدمات غير قانونية.

وثّقت جميع الأدلة وأبلغت سلطات الجريمة الإلكترونية.

أطلب اتخاذ إجراء فوري.

مع التحية،
{sender_name}"""
            },
        ],
    },

    # ═══════════════════════════════════════════════════
    # FRENCH — 25 قالب
    # ═══════════════════════════════════════════════════
    "fr": {
        "spam": [
            {
                "id": "fr_spam_01",
                "subject": "URGENT : Spam persistant depuis {number}",
                "body": """Cher équipe WhatsApp Trust & Safety,

Je vous écris pour déposer une plainte formelle contre le numéro WhatsApp {number}, qui m'envoie de manière répétée des messages spam contenant des liens suspects et des offres frauduleuses.

NUMÉRO SIGNALÉ : {number}
DATE : {date}
HEURE : {time}
CATÉGORIE : Spam
FRÉQUENCE : Plusieurs fois par jour
DURÉE : Plus de {days} jours

Le contenu inclut des fausses loteries, des schémas d'investissement suspects et des liens de phishing déguisés en notifications bancaires.

Je demande la suspension immédiate de ce compte pour protéger les autres utilisateurs.

Captures d'écran disponibles sur demande.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_spam_02",
                "subject": "Plusieurs utilisateurs signalent {number}",
                "body": """Bonjour Support WhatsApp,

Je signale une opération de spam organisée via le numéro {number}.

NUMÉRO : {number}
PROBLÈME : Spam massif avec liens malveillants
DATE : {date}
NOMBRE DE MESSAGES : 30+ en {days} jours

Ce compte fait partie d'un réseau de spam plus large. Plusieurs contacts de mon répertoire ont reçu des messages identiques de numéros similaires.

Les messages contiennent :
- URL raccourcies masquant des sites de phishing
- Fausses notifications "vous avez gagné"
- Demandes de partager le message avec 10 contacts

J'ai déjà bloqué ce numéro deux fois, mais le spam continue. Je soumets ce rapport formel en dernière étape.

Veuillez enquêter d'urgence.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_spam_03",
                "subject": "Plainte formelle : Campagne de spam {number}",
                "body": """Cher WhatsApp Trust & Safety,

TYPE DE PLAINTE : Spam persistant
NUMÉRO SIGNALÉ : {number}
DATE : {date}
DURÉE : {days} jours
STATUT : En cours

Je reçois des messages spam continus de {number} malgré plusieurs blocages. Cela viole clairement les Normes Communautaires et les Conditions d'Utilisation.

Le compte utilise des noms d'affichage rotatifs pour éviter la détection.

Je demande :
1. Résiliation immédiate du compte
2. Enquête sur les comptes liés
3. Confirmation de l'action prise

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_spam_04",
                "subject": "URGENT : Bot spam automatisé via {number}",
                "body": """À : Équipe Abus WhatsApp

Je dépose une plainte urgente concernant un bot spam automatisé via {number}.

NUMÉRO SIGNALÉ : {number}
NIVEAU DE MENACE : Élevé
DATE : {date}
DÉTECTÉ À : {specific_time}

Indicateurs :
- Messages envoyés à {specific_time} et heures inhabituelles
- Formatage identique sur plusieurs messages
- Temps de réponse immédiat (automatisation)
- Fausses offres d'emploi et schémas crypto

Le bot a contacté au moins 8 de mes contacts.

Veuillez résilier ce compte immédiatement.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_spam_05",
                "subject": "Spam récurrent de {number}",
                "body": """Équipe Sécurité WhatsApp,

Je soumets une plainte concernant le spam récurrent de {number}.

SIGNALÉ : {number}
DATE : {date}
BLOCAGES ANTÉRIEURS : 2
NOUVEAUX COMPTES : 3+

Cet individu contourne les blocages en créant de nouveaux comptes.

Messages reçus :
- 15 messages promotionnels
- 8 fausses offres d'investissement
- 5 tentatives de phishing

Je demande une action permanente.

Cordialement,
{sender_name}"""
            },
        ],
        "scam": [
            {
                "id": "fr_scam_01",
                "subject": "URGENT : Fraude financière depuis {number}",
                "body": """RAPPORT DE FRAUDE URGENT

À : WhatsApp Trust & Safety

Je signale une grave opération de fraude financière via le numéro {number}.

CATÉGORIE : Fraude financière / Usurpation bancaire
NUMÉRO SIGNALÉ : {number}
DATE : {date}
PERTES : {amount}

Ce compte m'a contacté prétendant être du service sécurité de ma banque. Ils ont demandé :
- Numéro de carte complet
- Code CVV
- Codes OTP
- Code PIN

J'ai d'abord obtempéré avant de réaliser l'arnaque.

J'ai déposé une plainte à la police.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_scam_02",
                "subject": "Arnaque à l'investissement - {number}",
                "body": """Cher Support WhatsApp,

Je dépose une plainte urgente concernant une arnaque à l'investissement via {number}.

NUMÉRO : {number}
TYPE : Faux schéma crypto/investissement
DATE : {date}
VICTIMES : 5+ dans mon réseau

Ce compte a :
- Promis des rendements irréalistes (300%+ mensuel)
- Demandé des dépôts via crypto
- Créé de faux tableaux de bord
- Refusé tous les retraits
- Disparu après avoir reçu {amount}

J'ai documenté toute la conversation.

Je demande la résiliation immédiate.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_scam_03",
                "subject": "Arnaque sentimentale depuis {number}",
                "body": """À qui de droit,

Je signale une arnaque sentimentale (pig butchering) via {number}.

SIGNALÉ : {number}
DÉBUT : il y a {days} jours
DATE : {date}
PERTES : {amount}

Modèle :
1. Contact initial par excuse de mauvais numéro
2. Relation émotionnelle factice sur {days} jours
3. Introduction d'"opportunités d'investissement"
4. Escalade progressive
5. Disparition après réception de {amount}

J'ai des preuves complètes.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_scam_04",
                "subject": "Arnaque à l'emploi depuis {number}",
                "body": """Équipe WhatsApp,

Je signale une arnaque à l'offre d'emploi depuis {number}.

NUMÉRO : {number}
TYPE : Fausse offre exigeant un paiement initial
DATE : {date}
PERTES : {amount}

L'opérateur :
- Prétendait représenter une entreprise connue
- Offrait un emploi à distance avec salaire irréaliste
- Demandait des frais d'inscription de {amount}
- Demandait des documents d'identité
- A disparu après réception

3 victimes identifiées dans mon réseau.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_scam_05",
                "subject": "Arnaque usurpation bancaire : {number}",
                "body": """Cher Support WhatsApp,

Je signale une arnaque par usurpation bancaire depuis {number}.

NUMÉRO : {number}
BANQUE USURPÉE : [Banque majeure]
DATE : {date}
PERTES : {amount}

L'escroc :
- Utilisait le logo officiel de la banque
- Envoyait un message du "Service Sécurité"
- Prétendait une activité suspecte
- Demandait des données de carte
- Demandait les codes OTP

Ma banque montre une transaction non autorisée de {amount}.

Cordialement,
{sender_name}
{sender_location}"""
            },
        ],
        "harassment": [
            {
                "id": "fr_har_01",
                "subject": "HARCÈLEMENT : Menaces répétées de {number}",
                "body": """PLAINTE DE HARCÈLEMENT URGENTE

À : WhatsApp Trust & Safety

Je dépose une plainte de harcèlement formelle contre {number}.

NUMÉRO SIGNALÉ : {number}
TYPE : Menaces répétées
DATE : {date}
DURÉE : {days} jours
MESSAGES : 50+

Cet utilisateur envoie :
- Menaces physiques directes
- Messages abusifs et insultants
- Contenu violent
- Matériaux explicites non sollicités

J'ai déposé une plainte à la police (dossier #{report_id}).

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_har_02",
                "subject": "Cyberharcèlement depuis {number}",
                "body": """À WhatsApp Trust & Safety,

Je signale un cyberharcèlement continu depuis {number}.

NUMÉRO : {number}
TYPE : Harcèlement / Abus verbal
DATE : {date}
DURÉE : {days} jours

Cette personne me harcèle systématiquement via :
- Messages insultants
- Contenu moqueur envoyé à nos contacts communs
- Tentatives d'humiliation publique
- Partage de mes informations privées

L'impact émotionnel a été sévère.

Je demande une action immédiate.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_har_03",
                "subject": "Traque via WhatsApp : {number}",
                "body": """URGENT : RAPPORT DE TRAQUE

À : Équipe Sécurité WhatsApp

Je signale un cas de traque via {number}.

NUMÉRO SIGNALÉ : {number}
DATE : {date}
MODÈLE : Comportement obsessionnel
DURÉE : {days} jours

Cet individu :
- Envoie des messages à toute heure, y compris {specific_time}
- Crée plusieurs comptes pour contourner mes blocages
- Suit mon activité en ligne
- Contacte mes amis et ma famille

J'ai déposé une plainte à la police.

Ma sécurité est en danger.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_har_04",
                "subject": "Messages menaçants de {number}",
                "body": """Cher Support WhatsApp,

Je signale un comportement menaçant depuis {number}.

NUMÉRO : {number}
DATE : {date}
TYPE : Menaces physiques
PARTIES MENACÉES : Moi-même, ma famille

Exemples de menaces :
- "Je sais où tu habites"
- "Tu vas le regretter"
- "Je vais te faire payer"

Ce sont des menaces physiques directes.

J'ai :
- Capturé toutes les captures d'écran
- Déposé une plainte
- Informé ma famille et mon travail

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_har_05",
                "subject": "Harcèlement sexuel via {number}",
                "body": """CONFIDENTIEL : Rapport de harcèlement sexuel

À : WhatsApp Trust & Safety

Je signale un harcèlement sexuel depuis {number}.

NUMÉRO SIGNALÉ : {number}
DATE : {date}
DURÉE : {days} jours

Cet utilisateur a envoyé :
- Messages explicites non sollicités
- Images explicites non sollicitées
- Demandes agressives de nature sexuelle

Ce comportement viole les politiques de WhatsApp.

Cordialement,
{sender_name}"""
            },
        ],
        "fake": [
            {
                "id": "fr_fake_01",
                "subject": "Faux compte usurpant mon identité : {number}",
                "body": """Cher Support WhatsApp,

Je signale un faux compte sur WhatsApp.

NUMÉRO SIGNALÉ : {number}
RAISON : Usurpation de mon identité
DATE : {date}

Ce compte utilise :
- Mes photos (volées sur les réseaux sociaux)
- Mon nom
- Ma biographie
- Fausses affirmations

L'opérateur utilise cette fausse identité pour :
- Tromper mes amis et ma famille
- Nuire à ma réputation
- Escroquer des personnes qui me font confiance

Veuillez vérifier et supprimer ce faux compte.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_fake_02",
                "subject": "Usurpation d'entreprise : {number}",
                "body": """À l'équipe WhatsApp Business,

Je signale un faux compte usurpant notre entreprise.

NUMÉRO SIGNALÉ : {number}
MARQUE USURPÉE : [Votre entreprise]
DATE : {date}

Ce compte :
- Utilise notre nom exact
- Copie notre logo
- Se présente comme notre chaîne WhatsApp officielle
- Trompe les clients
- Nuit à notre réputation

Ce n'est PAS notre compte.

Action légale en cas de non-résolution.

Cordialement,
{sender_name}
Pour [Nom de l'entreprise]"""
            },
            {
                "id": "fr_fake_03",
                "subject": "Catfishing {number}",
                "body": """Cher Support WhatsApp,

Je signale un compte de catfishing.

NUMÉRO : {number}
DATE : {date}
RAISON : Profil avec photos volées

Ce compte utilise les photos de quelqu'un d'autre pour créer une fausse identité.

Objectifs :
- Relations amoureuses trompeuses
- Exploitation financière
- Recrutement potentiel

J'ai fait une recherche d'image inversée.

Veuillez enquêter.

Merci,
{sender_name}"""
            },
            {
                "id": "fr_fake_04",
                "subject": "Usurpation gouvernementale - {number}",
                "body": """URGENT : USURPATION OFFICIELLE

À : WhatsApp Trust & Safety

Je signale un compte usurpant une entité gouvernementale.

NUMÉRO SIGNALÉ : {number}
USURPÉ : Département gouvernemental
DATE : {date}

Ce compte :
- Demande des documents personnels
- Exige des paiements pour "amendes"
- Menace d'action légale
- Utilise de faux sceaux officiels

Infraction grave punissable par la loi.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_fake_05",
                "subject": "Usurpation caritative : {number}",
                "body": """Cher WhatsApp Trust & Safety,

Je signale un faux compte caritatif.

NUMÉRO SIGNALÉ : {number}
USURPÉ : [Association légitime]
DATE : {date}

Ce compte :
- Utilise le nom d'une association connue
- Sollicite des dons pour de fausses causes
- Fournit de faux reçus
- Détourne les fonds

L'association réelle a confirmé que ce n'est PAS officiel.

Au moins {amount} collectés.

Cordialement,
{sender_name}"""
            },
        ],
        "illegal": [
            {
                "id": "fr_ill_01",
                "subject": "Vente de drogue illégale via {number}",
                "body": """Cher WhatsApp Trust & Safety,

Je signale des activités illégales via {number}.

NUMÉRO : {number}
ACTIVITÉ : Distribution de drogue
DATE : {date}

Ce compte utilise WhatsApp pour :
- Vendre des substances contrôlées
- Coordonner les livraisons
- Partager des images
- Traiter les paiements

J'ai signalé à la police locale.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_ill_02",
                "subject": "URGENT : Violation sécurité enfant - {number}",
                "body": """URGENT : RAPPORT SÉCURITÉ ENFANT

À : WhatsApp Trust & Safety

Je signale une grave violation.

NUMÉRO SIGNALÉ : {number}
TYPE : Contact inapproprié avec mineurs
DATE : {date}
GRAVITÉ : Critique

Ce compte :
- Contacte des mineurs avec contenu inapproprié
- Tente d'organiser des rencontres
- Demande des photos à des mineurs

Signalé aux autorités de protection de l'enfance.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_ill_03",
                "subject": "Soupçon de traite : {number}",
                "body": """RAPPORT CONFIDENTIEL

À : Équipe Sécurité WhatsApp

Je signale une activité suspecte suggérant de la traite humaine.

NUMÉRO : {number}
DATE : {date}

Modèles observés :
- Offres d'emploi vagues
- Demandes de documents d'identité
- Discussions de voyages pour personnes vulnérables
- Langage codé

J'ai alerté les organisations anti-traite.

Cordialement,
{sender_name}
{sender_location}"""
            },
            {
                "id": "fr_ill_04",
                "subject": "Réseau d'extorsion via {number}",
                "body": """Cher Support WhatsApp,

Je signale un réseau d'extorsion organisé.

NUMÉRO PRINCIPAL : {number}
DATE : {date}
VICTIMES : 5+

L'opération :
- Obtient des informations personnelles
- Menace les victimes de divulgation
- Exige des paiements crypto
- Utilise plusieurs comptes

J'ai déposé une plainte.

Cordialement,
{sender_name}"""
            },
            {
                "id": "fr_ill_05",
                "subject": "Services de piratage annoncés : {number}",
                "body": """URGENT : SERVICES CRIMINELS

À : Équipe Sécurité WhatsApp

Je signale un compte annonçant des services de piratage.

NUMÉRO SIGNALÉ : {number}
DATE : {date}

Services offerts :
- Piratage de comptes WhatsApp
- Prise de contrôle de réseaux sociaux
- Piratage d'email

Signalé aux autorités cybercriminelles.

Cordialement,
{sender_name}"""
            },
        ],
    },

    # ═══════════════════════════════════════════════════
    # SPANISH — 25 قالب
    # ═══════════════════════════════════════════════════
    "es": {
        "spam": [
            {
                "id": "es_spam_01",
                "subject": "URGENTE: Spam persistente de {number}",
                "body": """Estimado equipo de WhatsApp Trust & Safety,

Escribo para presentar una queja formal contra el número de WhatsApp {number}, que me envía repetidamente mensajes de spam con enlaces sospechosos y ofertas fraudulentas.

NÚMERO REPORTADO: {number}
FECHA: {date}
HORA: {time}
CATEGORÍA: Spam
FRECUENCIA: Varias veces al día
DURACIÓN: Más de {days} días

El contenido incluye falsas loterías, esquemas de inversión sospechosos y enlaces de phishing disfrazados de notificaciones bancarias.

Solicito la suspensión inmediata de esta cuenta.

Saludos cordiales,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_spam_02",
                "subject": "Múltiples usuarios reportan {number}",
                "body": """Hola Soporte de WhatsApp,

Reporto una operación de spam organizada a través del número {number}.

NÚMERO: {number}
PROBLEMA: Spam masivo con enlaces maliciosos
FECHA: {date}
MENSAJES: 30+ en {days} días

Esta cuenta es parte de una red de spam más amplia.

Los mensajes contienen:
- URLs acortadas que ocultan sitios de phishing
- Falsas notificaciones "has ganado"
- Solicitudes de compartir con 10 contactos

He bloqueado este número dos veces, pero el spam continúa.

Por favor investiguen con urgencia.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_spam_03",
                "subject": "Queja formal: Campaña de spam {number}",
                "body": """Estimado WhatsApp Trust & Safety,

TIPO: Spam persistente
NÚMERO REPORTADO: {number}
FECHA: {date}
DURACIÓN: {days} días
ESTADO: En curso

Recibo mensajes de spam continuos de {number} a pesar de bloquear varias veces.

La cuenta utiliza nombres de visualización rotativos.

Solicito:
1. Terminación inmediata
2. Investigación de cuentas vinculadas
3. Confirmación de la acción tomada

Saludos,
{sender_name}"""
            },
            {
                "id": "es_spam_04",
                "subject": "URGENTE: Bot de spam automático {number}",
                "body": """Para: Equipo de Abuso de WhatsApp

Presento una queja urgente sobre un bot de spam automático a través de {number}.

NÚMERO REPORTADO: {number}
NIVEL DE AMENAZA: Alto
FECHA: {date}
DETECTADO EN: {specific_time}

Indicadores:
- Mensajes enviados a {specific_time} y horas inusuales
- Formato idéntico
- Tiempo de respuesta inmediato

Por favor terminen esta cuenta inmediatamente.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_spam_05",
                "subject": "Spam recurrente de {number}",
                "body": """Equipo de Seguridad de WhatsApp,

Presento una queja sobre spam recurrente de {number}.

REPORTADO: {number}
FECHA: {date}
BLOQUEOS PREVIOS: 2
NUEVAS CUENTAS: 3+

Este individuo evade los bloqueos creando nuevas cuentas.

Solicito acción permanente.

Saludos,
{sender_name}"""
            },
        ],
        "scam": [
            {
                "id": "es_scam_01",
                "subject": "URGENTE: Fraude financiero de {number}",
                "body": """REPORTE DE FRAUDE URGENTE

Para: WhatsApp Trust & Safety

Reporto una grave operación de fraude financiero a través del número {number}.

CATEGORÍA: Fraude financiero / Suplantación bancaria
NÚMERO REPORTADO: {number}
FECHA: {date}
PÉRDIDAS: {amount}

Esta cuenta me contactó afirmando ser del departamento de seguridad de mi banco.

He presentado una denuncia policial.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_scam_02",
                "subject": "Estafa de inversión - {number}",
                "body": """Estimado Soporte de WhatsApp,

Presento una queja urgente sobre una estafa de inversión a gran escala a través de {number}.

NÚMERO: {number}
TIPO: Esquema falso de cripto/inversión
FECHA: {date}
VÍCTIMAS: 5+ en mi red

Esta cuenta:
- Prometió rendimientos irreales
- Solicitó depósitos en cripto
- Creó paneles falsos
- Se negó a permitir retiros
- Desapareció tras recibir {amount}

Solicito terminación inmediata.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_scam_03",
                "subject": "Estafa romántica de {number}",
                "body": """A quien corresponda,

Reporto una estafa romántica (pig butchering) desde {number}.

REPORTADO: {number}
INICIO: hace {days} días
FECHA: {date}
PÉRDIDAS: {amount}

Patrón:
1. Contacto inicial por número equivocado
2. Relación emocional falsa
3. Introducción de "oportunidades de inversión"
4. Escalada gradual
5. Desaparición

Tengo pruebas completas.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_scam_04",
                "subject": "Estafa de empleo desde {number}",
                "body": """Equipo de WhatsApp,

Reporto una estafa de oferta de empleo desde {number}.

NÚMERO: {number}
TIPO: Oferta falsa exigiendo pago inicial
FECHA: {date}
PÉRDIDAS: {amount}

El operador:
- Afirmaba representar una empresa conocida
- Ofrecía trabajo remoto con salario irreal
- Solicitaba tarifa de registro
- Desapareció tras recibir el pago

3 víctimas identificadas.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_scam_05",
                "subject": "Estafa de suplantación bancaria: {number}",
                "body": """Estimado Soporte de WhatsApp,

Reporto una estafa por suplantación bancaria desde {number}.

NÚMERO: {number}
BANCO SUPLANTADO: [Banco importante]
FECHA: {date}
PÉRDIDAS: {amount}

El estafador:
- Usaba el logo oficial del banco
- Enviaba mensajes del "Departamento de Seguridad"
- Solicitaba datos de tarjeta
- Solicitaba códigos OTP

Mi cuenta muestra una transacción no autorizada.

Saludos,
{sender_name}
{sender_location}"""
            },
        ],
        "harassment": [
            {
                "id": "es_har_01",
                "subject": "ACOSO: Amenazas repetidas de {number}",
                "body": """QUEJA URGENTE DE ACOSO

Para: WhatsApp Trust & Safety

Presento una queja formal de acoso contra {number}.

NÚMERO REPORTADO: {number}
TIPO: Amenazas repetidas
FECHA: {date}
DURACIÓN: {days} días
MENSAJES: 50+

Este usuario envía:
- Amenazas físicas directas
- Mensajes abusivos
- Contenido violento
- Materiales explícitos no solicitados

He presentado una denuncia policial (caso #{report_id}).

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_har_02",
                "subject": "Ciberacoso desde {number}",
                "body": """A WhatsApp Trust & Safety,

Reporto ciberacoso continuo desde {number}.

NÚMERO: {number}
TIPO: Acoso / Abuso verbal
FECHA: {date}
DURACIÓN: {days} días

Esta persona me acosa sistemáticamente.

El impacto emocional ha sido grave.

Solicito acción inmediata.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_har_03",
                "subject": "Acecho via WhatsApp: {number}",
                "body": """URGENTE: REPORTE DE ACECHO

Para: Equipo de Seguridad de WhatsApp

Reporto un caso de acecho via {number}.

NÚMERO REPORTADO: {number}
FECHA: {date}
PATRÓN: Comportamiento obsesivo
DURACIÓN: {days} días

Este individuo:
- Envía mensajes a todas horas, incluyendo {specific_time}
- Crea múltiples cuentas para evadir bloqueos
- Sigue mi actividad en línea
- Contacta a mi familia

Mi seguridad está en riesgo.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_har_04",
                "subject": "Mensajes amenazantes de {number}",
                "body": """Estimado Soporte de WhatsApp,

Reporto comportamiento amenazante desde {number}.

NÚMERO: {number}
FECHA: {date}
TIPO: Amenazas físicas

Ejemplos:
- "Sé dónde vives"
- "Te vas a arrepentir"
- "Te haré pagar"

Son amenazas físicas directas.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_har_05",
                "subject": "Acoso sexual via {number}",
                "body": """CONFIDENCIAL: Reporte de acoso sexual

Para: WhatsApp Trust & Safety

Reporto acoso sexual desde {number}.

NÚMERO REPORTADO: {number}
FECHA: {date}
DURACIÓN: {days} días

Este usuario ha enviado:
- Mensajes sexuales explícitos no solicitados
- Imágenes explícitas no solicitadas
- Demandas de naturaleza sexual

Esto viola las políticas de WhatsApp.

Saludos,
{sender_name}"""
            },
        ],
        "fake": [
            {
                "id": "es_fake_01",
                "subject": "Cuenta falsa suplantando mi identidad: {number}",
                "body": """Estimado Soporte de WhatsApp,

Reporto una cuenta falsa en WhatsApp.

NÚMERO REPORTADO: {number}
RAZÓN: Suplantación de mi identidad
FECHA: {date}

Esta cuenta usa:
- Mis fotos (robadas de redes sociales)
- Mi nombre
- Mi biografía

El operador usa esta identidad para:
- Engañar a mis amigos
- Dañar mi reputación
- Estafar

Por favor eliminen esta cuenta falsa.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_fake_02",
                "subject": "Suplantación de empresa: {number}",
                "body": """Al equipo de WhatsApp Business,

Reporto una cuenta falsa que suplanta nuestra empresa.

NÚMERO REPORTADO: {number}
MARCA SUPLANTADA: [Su empresa]
FECHA: {date}

Esta cuenta:
- Usa nuestro nombre exacto
- Copia nuestro logo
- Se presenta como nuestra cuenta oficial
- Engaña a clientes

No es nuestra cuenta.

Saludos,
{sender_name}
En nombre de [Empresa]"""
            },
            {
                "id": "es_fake_03",
                "subject": "Catfishing {number}",
                "body": """Estimado Soporte de WhatsApp,

Reporto una cuenta de catfishing.

NÚMERO: {number}
FECHA: {date}
RAZÓN: Perfil con fotos robadas

Esta cuenta usa fotos de otra persona.

He realizado búsqueda inversa de imágenes.

Por favor investiguen.

Gracias,
{sender_name}"""
            },
            {
                "id": "es_fake_04",
                "subject": "Suplantación gubernamental - {number}",
                "body": """URGENTE: SUPLANTACIÓN OFICIAL

Para: WhatsApp Trust & Safety

Reporto una cuenta suplantando una entidad gubernamental.

NÚMERO REPORTADO: {number}
SUPLANTADO: Departamento gubernamental
FECHA: {date}

Esta cuenta:
- Solicita documentos personales
- Exige pagos por "multas"
- Amenaza con acción legal
- Usa sellos oficiales falsos

Delito grave punible por ley.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_fake_05",
                "subject": "Suplantación caritativa: {number}",
                "body": """Estimado WhatsApp Trust & Safety,

Reporto una cuenta benéfica falsa.

NÚMERO REPORTADO: {number}
SUPLANTADO: [Organización legítima]
FECHA: {date}

Esta cuenta:
- Usa el nombre de una organización conocida
- Solicita donaciones para causas falsas
- Proporciona recibos falsos
- Desvía fondos

La organización real confirmó que no es oficial.

Al menos {amount} recaudados.

Saludos,
{sender_name}"""
            },
        ],
        "illegal": [
            {
                "id": "es_ill_01",
                "subject": "Venta ilegal de drogas via {number}",
                "body": """Estimado WhatsApp Trust & Safety,

Reporto actividades ilegales via {number}.

NÚMERO: {number}
ACTIVIDAD: Distribución de drogas
FECHA: {date}

Esta cuenta usa WhatsApp para:
- Vender sustancias controladas
- Coordinar entregas
- Compartir imágenes
- Procesar pagos

He reportado a la policía local.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_ill_02",
                "subject": "URGENTE: Violación seguridad infantil - {number}",
                "body": """URGENTE: REPORTE SEGURIDAD INFANTIL

Para: WhatsApp Trust & Safety

Reporto una grave violación.

NÚMERO REPORTADO: {number}
TIPO: Contacto inapropiado con menores
FECHA: {date}
GRAVEDAD: Crítica

Esta cuenta:
- Contacta menores con contenido inapropiado
- Intenta organizar encuentros
- Solicita fotos a menores

Reportado a autoridades de protección infantil.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_ill_03",
                "subject": "Sospecha de trata: {number}",
                "body": """REPORTE CONFIDENCIAL

Para: Equipo de Seguridad de WhatsApp

Reporto actividad sospechosa que sugiere trata de personas.

NÚMERO: {number}
FECHA: {date}

Patrones observados:
- Ofertas de empleo vagas
- Solicitudes de documentos de identidad
- Discusiones de viajes para personas vulnerables
- Lenguaje codificado

He alertado a organizaciones anti-trata.

Saludos,
{sender_name}
{sender_location}"""
            },
            {
                "id": "es_ill_04",
                "subject": "Red de extorsión via {number}",
                "body": """Estimado Soporte de WhatsApp,

Reporto una red de extorsión organizada.

NÚMERO PRINCIPAL: {number}
FECHA: {date}
VÍCTIMAS: 5+

La operación:
- Obtiene información personal
- Amenaza con exposición
- Exige pagos en cripto
- Usa múltiples cuentas

He presentado una denuncia.

Saludos,
{sender_name}"""
            },
            {
                "id": "es_ill_05",
                "subject": "Servicios de hacking anunciados: {number}",
                "body": """URGENTE: SERVICIOS CRIMINALES

Para: Equipo de Seguridad de WhatsApp

Reporto una cuenta que anuncia servicios de hacking.

NÚMERO REPORTADO: {number}
FECHA: {date}

Servicios ofrecidos:
- Hackeo de cuentas de WhatsApp
- Toma de control de redes sociales
- Hackeo de email

Reportado a autoridades cibercriminales.

Saludos,
{sender_name}"""
            },
        ],
    },

    # ═══════════════════════════════════════════════════
    # GERMAN — 25 قالب
    # ═══════════════════════════════════════════════════
    "de": {
        "spam": [
            {
                "id": "de_spam_01",
                "subject": "DRINGEND: Anhaltender Spam von {number}",
                "body": """Sehr geehrtes WhatsApp Trust & Safety Team,

Ich schreibe, um eine formelle Beschwerde gegen die WhatsApp-Nummer {number} einzureichen, die mir wiederholt Spam-Nachrichten mit verdächtigen Links und betrügerischen Angeboten sendet.

GEMELDETE NUMMER: {number}
DATUM: {date}
UHRZEIT: {time}
KATEGORIE: Spam
HÄUFIGKEIT: Mehrmals täglich
DAUER: Über {days} Tage

Der Inhalt enthält gefälschte Lotteriegewinne und Phishing-Links.

Ich fordere die sofortige Sperrung dieses Kontos.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_spam_02",
                "subject": "Mehrere Nutzer melden {number}",
                "body": """Hallo WhatsApp Support,

Ich melde eine organisierte Spam-Operation über die Nummer {number}.

NUMMER: {number}
PROBLEM: Massenspam mit bösartigen Links
DATUM: {date}
NACHRICHTEN: 30+ in {days} Tagen

Dieses Konto ist Teil eines größeren Spam-Netzwerks.

Bitte dringend untersuchen.

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_spam_03",
                "subject": "Formelle Beschwerde: Spam-Kampagne {number}",
                "body": """Sehr geehrtes WhatsApp Trust & Safety,

ART: Anhaltender Spam
GEMELDETE NUMMER: {number}
DATUM: {date}
DAUER: {days} Tage
STATUS: Laufend

Ich erhalte kontinuierliche Spam-Nachrichten von {number}.

Ich fordere:
1. Sofortige Kontokündigung
2. Untersuchung verknüpfter Konten
3. Bestätigung der Maßnahmen

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_spam_04",
                "subject": "DRINGEND: Automatischer Spam-Bot {number}",
                "body": """An: WhatsApp Abuse Team

Ich reiche eine dringende Beschwerde über einen automatischen Spam-Bot über {number} ein.

GEMELDETE NUMMER: {number}
BEDROHUNGSSTUFE: Hoch
DATUM: {date}
ERKANNT UM: {specific_time}

Bitte sofort dieses Konto kündigen.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_spam_05",
                "subject": "Wiederkehrender Spam von {number}",
                "body": """WhatsApp Sicherheitsteam,

Ich reiche eine Beschwerde über wiederkehrenden Spam von {number} ein.

GEMELDET: {number}
DATUM: {date}
VORHERIGE BLOCKIERUNGEN: 2
NEUE KONTEN: 3+

Ich fordere dauerhafte Maßnahmen.

Mit freundlichen Grüßen,
{sender_name}"""
            },
        ],
        "scam": [
            {
                "id": "de_scam_01",
                "subject": "DRINGEND: Finanzbetrug von {number}",
                "body": """DRINGENDER BETRUGSBERICHT

An: WhatsApp Trust & Safety

Ich melde eine schwerwiegende Finanzbetrugsoperation über die Nummer {number}.

KATEGORIE: Finanzbetrug / Bank-Identitätsdiebstahl
GEMELDETE NUMMER: {number}
DATUM: {date}
VERLUSTE: {amount}

Ich habe Strafanzeige erstattet.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_scam_02",
                "subject": "Investitionsbetrug - {number}",
                "body": """Sehr geehrter WhatsApp Support,

Ich reiche eine dringende Beschwerde über einen großangelegten Investitionsbetrug über {number} ein.

NUMMER: {number}
ART: Falsches Krypto/Investment-Schema
DATUM: {date}
OPFER: 5+ in meinem Netzwerk

Ich fordere sofortige Kündigung.

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_scam_03",
                "subject": "Romance-Betrug von {number}",
                "body": """An wen es betrifft,

Ich melde einen Romance-Betrug (Pig Butchering) von {number}.

GEMELDET: {number}
START: vor {days} Tagen
DATUM: {date}
VERLUSTE: {amount}

Muster:
1. Erster Kontakt durch falsche Nummer
2. Emotionale Beziehung
3. "Investitionsmöglichkeiten"
4. Eskalation
5. Verschwinden

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_scam_04",
                "subject": "Job-Betrug von {number}",
                "body": """WhatsApp Team,

Ich melde einen Job-Angebot-Betrug von {number}.

NUMMER: {number}
ART: Falsches Jobangebot mit Vorauszahlung
DATUM: {date}
VERLUSTE: {amount}

3 Opfer in meinem Netzwerk identifiziert.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_scam_05",
                "subject": "Bank-Identitätsbetrug: {number}",
                "body": """Sehr geehrter WhatsApp Support,

Ich melde einen Bank-Identitätsbetrug von {number}.

NUMMER: {number}
BANK: [Große Bank]
DATUM: {date}
VERLUSTE: {amount}

Mein Konto zeigt eine nicht autorisierte Transaktion.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
        ],
        "harassment": [
            {
                "id": "de_har_01",
                "subject": "BELÄSTIGUNG: Wiederholte Drohungen von {number}",
                "body": """DRINGENDE BELÄSTIGUNGSBESCHWERDE

An: WhatsApp Trust & Safety

Ich reiche eine formelle Belästigungsbeschwerde gegen {number} ein.

GEMELDETE NUMMER: {number}
ART: Wiederholte Drohungen
DATUM: {date}
DAUER: {days} Tage
NACHRICHTEN: 50+

Ich habe Strafanzeige erstattet (Fall #{report_id}).

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_har_02",
                "subject": "Cybermobbing von {number}",
                "body": """An WhatsApp Trust & Safety,

Ich melde anhaltendes Cybermobbing von {number}.

NUMMER: {number}
ART: Mobbing / Verbaler Missbrauch
DATUM: {date}
DAUER: {days} Tage

Ich fordere sofortige Maßnahmen.

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_har_03",
                "subject": "Stalking über WhatsApp: {number}",
                "body": """DRINGEND: STALKING-BERICHT

An: WhatsApp Sicherheitsteam

Ich melde einen Stalking-Fall über {number}.

GEMELDETE NUMMER: {number}
DATUM: {date}
MUSTER: Obsessives Stalking
DAUER: {days} Tage

Meine Sicherheit ist in Gefahr.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_har_04",
                "subject": "Drohnachrichten von {number}",
                "body": """Sehr geehrter WhatsApp Support,

Ich melde drohendes Verhalten von {number}.

NUMMER: {number}
DATUM: {date}
ART: Körperliche Drohungen

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_har_05",
                "subject": "Sexuelle Belästigung über {number}",
                "body": """VERTRAULICH: Sexuelle Belästigung

An: WhatsApp Trust & Safety

Ich melde sexuelle Belästigung von {number}.

GEMELDETE NUMMER: {number}
DATUM: {date}
DAUER: {days} Tage

Dies verstößt gegen WhatsApp-Richtlinien.

Mit freundlichen Grüßen,
{sender_name}"""
            },
        ],
        "fake": [
            {
                "id": "de_fake_01",
                "subject": "Falsches Konto: Identitätsdiebstahl {number}",
                "body": """Sehr geehrter WhatsApp Support,

Ich melde ein falsches Konto auf WhatsApp.

GEMELDETE NUMMER: {number}
GRUND: Identitätsdiebstahl
DATUM: {date}

Bitte entfernen Sie dieses falsche Konto.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_fake_02",
                "subject": "Unternehmens-Identitätsdiebstahl: {number}",
                "body": """An das WhatsApp Business Team,

Ich melde ein falsches Konto, das unser Unternehmen imitiert.

GEMELDETE NUMMER: {number}
MARKENNACHAHMUNG: [Ihr Unternehmen]
DATUM: {date}

Rechtliche Schritte werden folgen.

Mit freundlichen Grüßen,
{sender_name}
Für [Unternehmensname]"""
            },
            {
                "id": "de_fake_03",
                "subject": "Catfishing {number}",
                "body": """Sehr geehrter WhatsApp Support,

Ich melde ein Catfishing-Konto.

NUMMER: {number}
DATUM: {date}
GRUND: Profil mit gestohlenen Fotos

Bitte untersuchen Sie.

Danke,
{sender_name}"""
            },
            {
                "id": "de_fake_04",
                "subject": "Regierungs-Identitätsdiebstahl - {number}",
                "body": """DRINGEND: OFFIZIELLER IDENTITÄTSDIEBSTAHL

An: WhatsApp Trust & Safety

Ich melde ein Konto, das eine Regierungsstelle imitiert.

GEMELDETE NUMMER: {number}
IMITIERT: Regierungsabteilung
DATUM: {date}

Schwere Straftat.

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_fake_05",
                "subject": "Wohltätigkeits-Identitätsdiebstahl: {number}",
                "body": """Sehr geehrtes WhatsApp Trust & Safety,

Ich melde ein falsches Wohltätigkeitskonto.

GEMELDETE NUMMER: {number}
IMITIERT: [Legitime Organisation]
DATUM: {date}

Mindestens {amount} gesammelt.

Mit freundlichen Grüßen,
{sender_name}"""
            },
        ],
        "illegal": [
            {
                "id": "de_ill_01",
                "subject": "Illegaler Drogenverkauf über {number}",
                "body": """Sehr geehrtes WhatsApp Trust & Safety,

Ich melde illegale Aktivitäten über {number}.

NUMMER: {number}
AKTIVITÄT: Drogenvertrieb
DATUM: {date}

Ich habe die Polizei informiert.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_ill_02",
                "subject": "DRINGEND: Kindersicherheitsverletzung - {number}",
                "body": """DRINGEND: KINDERSICHERHEITSBERICHT

An: WhatsApp Trust & Safety

Ich melde eine schwerwiegende Verletzung.

GEMELDETE NUMMER: {number}
ART: Unangemessener Kontakt mit Minderjährigen
DATUM: {date}
SCHWEREGRAD: Kritisch

An Kinderschutzbehörden gemeldet.

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_ill_03",
                "subject": "Verdacht auf Menschenhandel: {number}",
                "body": """VERTRAULICHER BERICHT

An: WhatsApp Sicherheitsteam

Ich melde verdächtige Aktivitäten, die auf Menschenhandel hindeuten.

NUMMER: {number}
DATUM: {date}

Anti-Menschenhandels-Organisationen informiert.

Mit freundlichen Grüßen,
{sender_name}
{sender_location}"""
            },
            {
                "id": "de_ill_04",
                "subject": "Erpressungsnetzwerk über {number}",
                "body": """Sehr geehrter WhatsApp Support,

Ich melde ein organisiertes Erpressungsnetzwerk.

HAUPTNUMMER: {number}
DATUM: {date}
OPFER: 5+

Strafanzeige erstattet.

Mit freundlichen Grüßen,
{sender_name}"""
            },
            {
                "id": "de_ill_05",
                "subject": "Hacking-Dienste beworben: {number}",
                "body": """DRINGEND: KRIMINELLE DIENSTE

An: WhatsApp Sicherheitsteam

Ich melde ein Konto, das Hacking-Dienste bewirbt.

GEMELDETE NUMMER: {number}
DATUM: {date}

An Cybercrime-Behörden gemeldet.

Mit freundlichen Grüßen,
{sender_name}"""
            },
        ],
    },
}


# ============================================================
# [4] Helpers
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
    return random.choice(WA_REPORT_EMAILS)


# ============================================================
# [5] Anti-Repeat System (لكل لغة + سبب)
# ============================================================
def get_used_template_ids(user_id):
    if not redis_client or not user_id:
        return set()
    try:
        used = redis_client.smembers(f"wa_used_templates:{user_id}")
        return set(used or [])
    except Exception:
        return set()


def mark_template_used(user_id, template_id):
    if not redis_client or not user_id or not template_id:
        return
    try:
        redis_client.sadd(f"wa_used_templates:{user_id}", template_id)
        redis_client.expire(f"wa_used_templates:{user_id}", 86400 * 90)
    except Exception as e:
        logger.warning(f"mark_template_used error: {e}")


def pick_unique_template(user_id, reason, lang=None):
    """يختار قالب من أي لغة مع تجنب التكرار"""
    if lang is None:
        lang = random.choice(list(REPORT_TEMPLATES.keys()))

    lang_templates = REPORT_TEMPLATES.get(lang, {})
    templates = lang_templates.get(reason, [])

    if not templates:
        # fallback للـ English
        templates = REPORT_TEMPLATES["en"].get(reason, [])
        lang = "en"

    if not templates:
        templates = REPORT_TEMPLATES["en"]["spam"]
        lang = "en"

    if not user_id:
        return random.choice(templates), lang

    used_ids = get_used_template_ids(user_id)
    available = [t for t in templates if t.get("id") not in used_ids]

    if not available:
        # امسح المستخدم من الـ used
        try:
            redis_client.delete(f"wa_used_templates:{user_id}")
        except Exception:
            pass
        available = templates
        logger.info(f"Reset template pool for user {user_id}")

    chosen = random.choice(available)
    mark_template_used(user_id, chosen.get("id"))
    logger.info(f"User {user_id} got {chosen.get('id')} (lang={lang}, used={len(used_ids)})")
    return chosen, lang


# ============================================================
# [6] Payload Storage
# ============================================================
def save_report_payload(to_email, subject, body):
    if not redis_client:
        return None
    try:
        payload_id = uuid.uuid4().hex[:10]
        redis_client.setex(
            f"wa_payload:{payload_id}",
            86400,
            json.dumps({
                "to": to_email,
                "subject": subject,
                "body": body,
                "created_at": time.time(),
            }, ensure_ascii=False)
        )
        return payload_id
    except Exception as e:
        logger.exception(f"save_report_payload error: {e}")
        return None


def get_report_payload(payload_id):
    if not redis_client:
        return None
    try:
        raw = redis_client.get(f"wa_payload:{payload_id}")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"get_report_payload error: {e}")
    return None


# ============================================================
# [7] ★★★ الدالة الرئيسية ★★★
# ============================================================
def generate_report(victim_number, reason="spam", user_id=None, lang=None):
    """يولد بلاغ كامل مع قالب فريد"""
    number = normalize_number(victim_number)
    if not number:
        return {"error": "رقم غير صالح"}

    # اختر قالب فريد
    template, used_lang = pick_unique_template(user_id, reason, lang=lang)

    # اختر اسم مرسل حسب اللغة
    sender_names_for_lang = SENDER_NAMES.get(used_lang, SENDER_NAMES["en"])
    sender_name = random.choice(sender_names_for_lang)

    to_email = pick_random_email()

    # متغيرات ديناميكية
    vars_dict = {
        "number": number,
        "date": time.strftime("%Y-%m-%d"),
        "time": time.strftime("%H:%M"),
        "days": random.randint(3, 30),
        "sender_name": sender_name,
        "sender_location": random.choice(SENDER_LOCATIONS),
        "device": random.choice(DEVICES),
        "amount": random.choice(LOST_AMOUNTS),
        "specific_time": random.choice(SPECIFIC_TIMES),
        "report_id": f"WR-{random.randint(100000, 999999)}",
    }

    try:
        subject = template["subject"].format(**vars_dict)
        body = template["body"].format(**vars_dict)
    except (KeyError, IndexError) as e:
        logger.exception(f"Template format error: {e}")
        return {"error": "خطأ في القالب"}

    payload_id = save_report_payload(to_email, subject, body)

    if payload_id:
        base = PUBLIC_URL.rstrip("/")
        mailto_link = f"{base}/wa/redirect/{payload_id}"
    else:
        mailto_link = (
            f"mailto:{to_email}"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )

    return {
        "mailto": mailto_link,
        "payload_id": payload_id,
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "reason": reason,
        "number": number,
        "template_id": template.get("id"),
        "language": used_lang,
    }


# ============================================================
# [8] ★★★ Blast Mode — 5 بلاغات × 5 إيميلات ★★★
# ============================================================
def generate_blast_reports(victim_number, reason="spam", user_id=None):
    """
    يولد 5 بلاغات:
    - 5 لغات مختلفة
    - 5 قوالب مختلفة
    - 5 إيميلات واتساب مختلفة
    """
    number = normalize_number(victim_number)
    if not number:
        return {"error": "رقم غير صالح"}

    languages = list(REPORT_TEMPLATES.keys())
    random.shuffle(languages)

    channels = list(WA_REPORT_CHANNELS.values())
    random.shuffle(channels)

    reports = []
    for i, lang in enumerate(languages[:5]):
        # اختر قالب فريد من اللغة دي
        template, used_lang = pick_unique_template(user_id, reason, lang=lang)

        # اختر إيميل مختلف
        channel = channels[i % len(channels)]
        to_email = channel["email"]

        # اسم مرسل حسب اللغة
        sender_names_for_lang = SENDER_NAMES.get(used_lang, SENDER_NAMES["en"])
        sender_name = random.choice(sender_names_for_lang)

        vars_dict = {
            "number": number,
            "date": time.strftime("%Y-%m-%d"),
            "time": time.strftime("%H:%M"),
            "days": random.randint(3, 30),
            "sender_name": sender_name,
            "sender_location": random.choice(SENDER_LOCATIONS),
            "device": random.choice(DEVICES),
            "amount": random.choice(LOST_AMOUNTS),
            "specific_time": random.choice(SPECIFIC_TIMES),
            "report_id": f"WR-{random.randint(100000, 999999)}",
        }

        try:
            subject = template["subject"].format(**vars_dict)
            body = template["body"].format(**vars_dict)
        except (KeyError, IndexError) as e:
            logger.warning(f"Skip template {template.get('id')}: {e}")
            continue

        payload_id = save_report_payload(to_email, subject, body)

        if payload_id:
            base = PUBLIC_URL.rstrip("/")
            mailto_link = f"{base}/wa/redirect/{payload_id}"
        else:
            mailto_link = (
                f"mailto:{to_email}"
                f"?subject={urllib.parse.quote(subject)}"
                f"&body={urllib.parse.quote(body)}"
            )

        reports.append({
            "mailto": mailto_link,
            "payload_id": payload_id,
            "to_email": to_email,
            "channel_name": channel["name"],
            "subject": subject,
            "body": body,
            "reason": reason,
            "number": number,
            "template_id": template.get("id"),
            "language": used_lang,
            "index": i + 1,
        })

    return {
        "number": number,
        "reason": reason,
        "reports": reports,
        "total": len(reports),
    }


# ============================================================
# [9] Session Management
# ============================================================
def create_report_session(chat_id, victim_number, reason):
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


# ============================================================
# [10] Stats
# ============================================================
def get_template_stats():
    """إحصائيات القوالب"""
    stats = {"by_lang": {}, "total": 0}
    for lang, reasons in REPORT_TEMPLATES.items():
        lang_total = 0
        for reason, templates in reasons.items():
            count = len(templates)
            lang_total += count
            stats[f"{lang}_{reason}"] = count
        stats["by_lang"][lang] = lang_total
        stats["total"] += lang_total
    return stats
