# whatsapp_report_generator.py
# ============================================================
# WhatsApp Report Generator v5.0
# 50 قالب قوي + نظام عدم التكرار
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
# [1] إيميلات واتساب
# ============================================================
WA_REPORT_EMAILS = {
    "support": "support@whatsapp.com",
    "abuse": "abuse@whatsapp.com",
    "security": "security@whatsapp.com",
    "android": "android-support@whatsapp.com",
    "ios": "iphone-support@whatsapp.com",
}

# ============================================================
# [2] بيانات ديناميكية للمتغيرات
# ============================================================
SENDER_NAMES = [
    "Ahmed Mohamed", "Sara Ali", "Mahmoud Hassan", "Nour Ibrahim",
    "Omar Khaled", "Fatma Sayed", "Youssef Adel", "Mona Farouk",
    "Khaled Tarek", "Layla Ahmed", "Hassan Mostafa", "Dina Samir",
    "Ali Gamal", "Rana Waleed", "Mostafa Nabil", "Heba Rashad",
    "Mohamed Salim", "Yasmin Fawzy", "Karim Hossam", "Salma Ehab",
]

SENDER_LOCATIONS = [
    "Cairo, Egypt", "Alexandria, Egypt", "Giza, Egypt",
    "Dubai, UAE", "Riyadh, Saudi Arabia", "Amman, Jordan",
    "Kuwait City, Kuwait", "Doha, Qatar", "Casablanca, Morocco",
    "Tunis, Tunisia", "Beirut, Lebanon", "Baghdad, Iraq",
]

DEVICES = [
    "iPhone 14 Pro", "iPhone 15", "Samsung Galaxy S23",
    "Samsung Galaxy S24", "Huawei P50", "Xiaomi 13 Pro",
    "Google Pixel 7", "OnePlus 11", "Oppo Reno 10",
]

LOST_AMOUNTS = [
    "$500", "$1,200", "$2,500", "$800", "$3,000",
    "$150", "$5,000", "$450", "EGP 15,000",
    "SAR 3,000", "AED 2,500", "$750", "$1,800",
]

SPECIFIC_TIMES = [
    "02:15 AM", "03:45 AM", "11:30 PM", "01:20 AM",
    "04:50 AM", "12:30 AM", "02:00 PM", "10:15 AM",
    "11:55 PM", "03:30 AM",
]

# ============================================================
# [3] القوالب — 50 قالب قوي (10 لكل سبب)
# ============================================================
REPORT_TEMPLATES = {

    # ═══════════════════════════════════════════════════
    # SPAM — 10 قوالب
    # ═══════════════════════════════════════════════════
    "spam": [
        {
            "id": "spam_01",
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
            "id": "spam_02",
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
            "id": "spam_03",
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
            "id": "spam_04",
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
            "id": "spam_05",
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
        {
            "id": "spam_06",
            "subject": "Spam violation - Number {number}",
            "body": """Dear WhatsApp Team,

I would like to formally report the number {number} for violating WhatsApp's spam policy.

DETAILS:
Reported Number: {number}
Violation Type: Unsolicited bulk messaging
First Message: {days} days ago
Latest Message: {date}
Message Count: 30+
Message Type: Promotional spam + phishing

The messages are clearly automated, sent from a bulk messaging platform. Content includes fake affiliate links, dummy crypto signals, and "work from home" scams.

I have saved all messages and screenshots for your review.

Request you to investigate and take appropriate action.

Sincerely,
{sender_name}
{sender_location}"""
        },
        {
            "id": "spam_07",
            "subject": "EMERGENCY: Mass spam from {number}",
            "body": """URGENT SECURITY REPORT

To: WhatsApp Trust & Safety

I am filing an emergency complaint against WhatsApp account {number}.

THREAT LEVEL: HIGH
ISSUE: Mass spam messaging with malicious intent
REPORT DATE: {date}
REPORT TIME: {time}

This account has been sending bulk messages containing:
- Phishing links targeting banking credentials
- Fake delivery notifications with payment requests
- Malicious APK file links

At least 3 people in my network clicked the links and reported suspicious activity on their bank accounts.

This is a clear coordinated spam campaign. Multiple users are at immediate risk.

IMMEDIATE ACTION REQUIRED:
1. Terminate account {number}
2. Preserve message logs for law enforcement
3. Alert other users who received messages

Regards,
{sender_name}"""
        },
        {
            "id": "spam_08",
            "subject": "Sustained spam from {number}",
            "body": """Dear WhatsApp Support,

I am writing to report a serious case of sustained spam from the number {number}.

REPORTED NUMBER: {number}
SPAM DURATION: {days} days
MESSAGES RECEIVED: 40+
BLOCKS ATTEMPTED: 2

The operator of this account:
- Uses multiple display names
- Sends messages from different but similar numbers
- Targets WhatsApp users in bulk
- Ignores all requests to stop

I have evidence of:
- Message screenshots
- Timestamps showing unusual hours (e.g., {specific_time})
- Pattern analysis showing automated behavior

This account must be terminated to prevent further abuse of WhatsApp users.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "spam_09",
            "subject": "Report: Spam network via {number}",
            "body": """Hello WhatsApp Trust Team,

I am reporting a spam network that includes the number {number}.

REPORTED NUMBER: {number}
NETWORK SIZE: 5+ linked accounts
REPORT DATE: {date}

The network is running a coordinated spam campaign targeting users in {sender_location} and surrounding regions.

Methods used:
- Bulk messaging from multiple numbers
- Rotating spam content to avoid filters
- Aggressive contact harvesting

I have been receiving these messages for {days} days. This account and its network violate:
- WhatsApp Terms of Service (Section 3)
- Community Guidelines on spam
- Regional anti-spam regulations

Request immediate termination of all linked accounts.

Regards,
{sender_name}"""
        },
        {
            "id": "spam_10",
            "subject": "Immediate action: {number} - Verified spam source",
            "body": """To WhatsApp Security Team,

I am submitting this report after verifying that {number} is a dedicated spam account.

VERIFICATION FINDINGS:
- Reported Number: {number}
- Report Date: {date}
- Cross-checked with 3+ users: All confirmed receiving spam
- Message types: 100% promotional/fraudulent
- Legitimate messages: 0

This account has no legitimate purpose. It exists solely for:
- Bulk spam distribution
- Phishing attacks
- Scam promotion

I have documented all interactions with timestamps and screenshots.

Request immediate and permanent termination.

Regards,
{sender_name}
{sender_location}"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # SCAM — 10 قوالب
    # ═══════════════════════════════════════════════════
    "scam": [
        {
            "id": "scam_01",
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
            "id": "scam_02",
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
            "id": "scam_03",
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
            "id": "scam_04",
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
            "id": "scam_05",
            "subject": "Phishing attack via {number} - WhatsApp impersonation",
            "body": """Security Alert - WhatsApp Support Team,

I am reporting a phishing attempt from number {number} where the attacker was impersonating WhatsApp itself.

REPORTED NUMBER: {number}
ATTACK TYPE: Phishing / Credential theft
DATE: {date}
TARGET: WhatsApp account credentials

The attacker:
- Used WhatsApp's official logo as profile picture
- Claimed my account would be banned unless I verified
- Sent a link to a fake WhatsApp login page
- Requested my 6-digit verification code

I recognized this as phishing and did not comply. However, this is a serious security threat to all WhatsApp users.

The fake domain is: whatsapp-verify[dot]com (I can provide full URL)

Please:
1. Terminate this account immediately
2. Report the phishing domain
3. Warn all users who received similar messages

Regards,
{sender_name}"""
        },
        {
            "id": "scam_06",
            "subject": "Crypto scam - Account {number}",
            "body": """Dear WhatsApp Trust & Safety,

URGENT: I am reporting a cryptocurrency scam account operating via WhatsApp number {number}.

NUMBER: {number}
SCAM TYPE: Fake crypto trading platform
REPORT DATE: {date}
LOSSES: {amount}

The scammer:
- Advertised "guaranteed profits" via crypto trading
- Showed photoshopped screenshots of {amount}+ profits
- Asked for deposits in USDT/Bitcoin
- Provided fake trading platform login
- Vanished after receiving {amount}

I have evidence of:
- Chat conversations
- Fake profit screenshots
- Wallet addresses used
- Platform URLs (now defunct)

This is clearly an organized scam targeting crypto users.

Please terminate this account and cooperate with authorities.

Regards,
{sender_name}"""
        },
        {
            "id": "scam_07",
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
        {
            "id": "scam_08",
            "subject": "Prize/lottery scam from {number}",
            "body": """To WhatsApp Trust & Safety,

I am reporting a lottery/prize scam operated from number {number}.

REPORTED NUMBER: {number}
SCAM TYPE: Fake prize notification
REPORT DATE: {date}

The scammer claimed I won:
- {amount} in a fake lottery
- A new iPhone 15 Pro
- A luxury car

To claim the prize, I was asked to:
1. Pay "processing fee" of {amount}
2. Share bank account details
3. Send copies of my ID

I researched and found dozens of similar reports online. This is clearly a widespread scam.

Request immediate account termination.

Regards,
{sender_name}"""
        },
        {
            "id": "scam_09",
            "subject": "Fake charity scam - {number}",
            "body": """Dear WhatsApp Support,

I am reporting a fake charity scam from number {number}.

NUMBER: {number}
SCAM TYPE: Fake charity/relief fund
REPORT DATE: {date}
AMOUNT REQUESTED: {amount}

The scammer:
- Claimed to represent a legitimate NGO
- Requested donations for "refugees" or "orphans"
- Provided fake official-looking documents
- Requested transfers to personal accounts
- Used emotional manipulation

After researching, I found:
- The NGO doesn't exist
- The documents were forged
- Similar accounts from same operator

This exploit exploits people's compassion. Please terminate immediately.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "scam_10",
            "subject": "Extortion via {number} - URGENT",
            "body": """URGENT: EXTORTION REPORT

To: WhatsApp Security Team

I am reporting an extortion attempt via number {number}.

REPORTED NUMBER: {number}
CRIME TYPE: Blackmail/Extortion
REPORT DATE: {date}
THREAT: Sensitive info exposure

The operator claims to have:
- Access to my private photos
- Access to my contacts
- Screenshots of my chats

They are demanding {amount} in Bitcoin to prevent the release of this "material". They have set a deadline of {days} hours.

I have filed a police report (case #{report_id}) and am requesting:
1. Immediate account termination
2. Preservation of all data
3. Full cooperation with law enforcement

This is a criminal act and poses serious risk to my safety.

Regards,
{sender_name}
{sender_location}"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # HARASSMENT — 10 قوالب
    # ═══════════════════════════════════════════════════
    "harassment": [
        {
            "id": "har_01",
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
            "id": "har_02",
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
            "id": "har_03",
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
            "id": "har_04",
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
            "id": "har_05",
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
        {
            "id": "har_06",
            "subject": "Abusive content from {number} - Hate speech",
            "body": """Dear WhatsApp Support,

I am reporting an abusive account on WhatsApp sending hate speech.

REPORTED NUMBER: {number}
DATE: {date}
ABUSE CATEGORY: Hate speech + Offensive content

This account has sent me messages including:
- Racial slurs targeting my ethnicity
- Religious insults
- Hateful content about my nationality
- Offensive memes and images

This is not a personal dispute — this is hate speech that violates WhatsApp's Community Standards and applicable laws.

I have preserved all evidence:
- Message content
- Timestamps
- Screenshots

Request immediate termination and referral to appropriate authorities.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "har_07",
            "subject": "Doxxing attempt via {number}",
            "body": """URGENT: DOXXING REPORT

To WhatsApp Security Team

I am reporting a doxxing attempt via number {number}.

REPORTED NUMBER: {number}
DATE: {date}
SENSITIVE INFO SHARED WITHOUT CONSENT:
- My home address
- My workplace
- Family member names
- Personal photos

The user obtained this information through deception and is threatening to share it publicly on social media.

This is a serious violation of privacy and could lead to physical harm.

I have:
- Filed a police report
- Notified my workplace
- Documented everything

Please suspend this account immediately.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "har_08",
            "subject": "Impersonation harassment: {number}",
            "body": """Dear WhatsApp Trust & Safety,

I am reporting harassment through impersonation from number {number}.

REPORTED NUMBER: {number}
DATE: {date}
IMPERSONATED: A family member / colleague

The user created a fake WhatsApp profile using:
- Photos of someone I trust
- Their name and bio
- Fake relationship claims

The purpose is to trick me and manipulate mutual contacts. They are using this identity to send harassing messages.

Multiple contacts have been fooled already.

I have:
- Verified the real person
- Screenshot of the fake profile
- Messages showing the harassment

Request immediate termination.

Regards,
{sender_name}"""
        },
        {
            "id": "har_09",
            "subject": "Group harassment - {number}",
            "body": """To WhatsApp Support,

I am reporting coordinated group harassment from number {number}.

REPORTED NUMBER: {number}
DATE: {date}
HARASSMENT TYPE: Coordinated by multiple accounts

This account is the leader of a coordinated harassment group. They:
- Add me to groups to send abusive content
- Coordinate mass-messaging campaigns
- Encourage others to contact me with threats
- Organize repeated reporting attacks

Identified accounts involved: 5+
Main operator: {number}

I have documented all communications and can provide full evidence.

Request immediate action against {number} and coordination with WhatsApp Trust & Safety to identify all linked accounts.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "har_10",
            "subject": "Mental health harm via {number}",
            "body": """Dear WhatsApp Support,

I am reporting serious harassment from number {number}.

REPORTED NUMBER: {number}
DATE: {date}
DURATION: {days} days

This person has been targeting my mental health through:
- Constant abusive messages throughout the day
- Threats about my personal life
- Encouraging self-harm
- Spreading lies about me to friends

The impact on my mental health has been severe. I have consulted a professional.

Documented evidence:
- Messages with timestamps
- Screenshots
- Record of abusive behavior patterns

I am requesting immediate account termination as this is causing documented harm.

Regards,
{sender_name}"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # FAKE ACCOUNT — 10 قوالب
    # ═══════════════════════════════════════════════════
    "fake": [
        {
            "id": "fake_01",
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
            "id": "fake_02",
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
            "id": "fake_03",
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
            "id": "fake_04",
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
            "id": "fake_05",
            "subject": "Fake celebrity account - {number}",
            "body": """Dear WhatsApp Team,

I am reporting a fake account impersonating a public figure.

REPORTED NUMBER: {number}
IMPERSONATED: [Celebrity/Influencer name]
DATE: {date}

The account uses:
- Celebrity photos
- Celebrity name
- Fake "verified" claims
- Impersonation of their communications style

The operator is:
- Asking fans for money
- Promoting fake merchandise
- Requesting personal information
- Damaging the celebrity's reputation

Verified with the celebrity's real management team — they confirmed this is NOT their account.

Request immediate termination.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "fake_06",
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
        {
            "id": "fake_07",
            "subject": "Family member impersonation - {number}",
            "body": """URGENT: FAMILY IMPERSONATION

To: WhatsApp Security Team

I am reporting an account impersonating a family member.

REPORTED NUMBER: {number}
IMPERSONATED: My [relationship - brother/sister/parent]
DATE: {date}

The impostor created an account using:
- Photos of my family member
- Their name
- Common conversation patterns

The impostor contacted me claiming my relative was in "an emergency" and needed {amount} urgently.

I verified with my real family member — this was a scam attempt.

This is a targeted scam using personal information. Request immediate action.

Regards,
{sender_name}"""
        },
        {
            "id": "fake_08",
            "subject": "Fake business account - {number}",
            "body": """Dear WhatsApp Business Support,

I am reporting a fake business account.

REPORTED NUMBER: {number}
DATE: {date}
ISSUE: Impersonating a legitimate e-commerce business

This account:
- Uses branding of [Legitimate Business]
- Claims to be their "official" WhatsApp
- Processes fake orders
- Collects payments without delivering goods

Multiple victims have reported losing {amount} each.

We have:
- Verified with the real business
- Collected victim testimonials
- Identified payment methods used

This account is running a large-scale e-commerce scam. Immediate termination required.

Regards,
{sender_name}"""
        },
        {
            "id": "fake_09",
            "subject": "Doctor impersonation - {number}",
            "body": """Dear WhatsApp Support,

I am reporting an account impersonating a medical professional.

REPORTED NUMBER: {number}
IMPERSONATED: Doctor at [Hospital]
DATE: {date}

This account:
- Uses a doctor's name and photo
- Claims to be from a real hospital
- Offers fake medical consultations
- Requests payments for non-existent treatments
- May have caused medical harm to vulnerable patients

This is not only fraud — it's a public health risk.

I have verified with the real hospital that this account does not belong to any of their staff.

Request immediate action.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "fake_10",
            "subject": "Multi-account impersonation: {number}",
            "body": """To WhatsApp Trust & Safety,

I am reporting a coordinated impersonation operation.

MAIN ACCOUNT: {number}
DATE: {date}
LINKED ACCOUNTS: 4+ identified

The operation uses multiple WhatsApp accounts to impersonate different personas:
- One claims to be a bank officer
- Another a government agent
- A third a family friend
- Others used as needed

Purpose: Multi-layer scam to build trust and extract personal information.

This coordinated attack is more sophisticated than typical scams. I have documented all accounts and their interactions.

Request:
1. Immediate termination of all linked accounts
2. Coordination with WhatsApp's security team
3. Possible referral to authorities

Regards,
{sender_name}
{sender_location}"""
        },
    ],

    # ═══════════════════════════════════════════════════
    # ILLEGAL ACTIVITY — 10 قوالب
    # ═══════════════════════════════════════════════════
    "illegal": [
        {
            "id": "ill_01",
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
            "id": "ill_02",
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
            "id": "ill_03",
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
            "id": "ill_04",
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
            "id": "ill_05",
            "subject": "Weapons trafficking via {number}",
            "body": """CONFIDENTIAL: WEAPONS TRAFFICKING

To: WhatsApp Trust & Safety

I am reporting suspected weapons trafficking.

REPORTED NUMBER: {number}
DATE: {date}
SEVERITY: Critical

This account is:
- Offering firearms and ammunition
- Sharing weapon photos with pricing
- Discussing delivery arrangements
- Using coded terminology

Evidence includes:
- Weapon images (including illegal modifications)
- Price lists
- Delivery discussions
- Buyer interactions

This is a serious threat to public safety. I have notified law enforcement.

Request immediate action and cooperation with authorities.

Regards,
{sender_name}"""
        },
        {
            "id": "ill_06",
            "subject": "Money laundering operation - {number}",
            "body": """Dear WhatsApp Support,

I am reporting suspicious financial activity suggesting money laundering.

REPORTED NUMBER: {number}
DATE: {date}

Red flags identified:
- Requests to receive and forward funds
- Offers of commission for using personal bank accounts
- Instructions to avoid detection
- Use of multiple accounts and payment methods
- Large transfers through personal accounts

The operator has approached multiple people I know with similar offers.

I have preserved all communications and reported to financial authorities.

Request WhatsApp terminate this account and cooperate with financial investigation.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "ill_07",
            "subject": "Stolen data selling - {number}",
            "body": """Dear WhatsApp Trust & Safety,

I am reporting an account selling stolen data.

NUMBER: {number}
DATE: {date}
TYPE: Sale of personal databases

This account is offering:
- Leaked user databases
- Credit card information
- Personal identity data
- Bank account details

Sample data provided for verification purposes showed real personal information of {sender_location} residents.

This is a serious data crime.

I have:
- Screenshot all evidence
- Reported to data protection authorities
- Notified potential victims identified in samples

Request immediate termination and coordination with law enforcement.

Regards,
{sender_name}"""
        },
        {
            "id": "ill_08",
            "subject": "Counterfeit goods - {number}",
            "body": """Dear WhatsApp Team,

I am reporting a large-scale counterfeit goods operation.

REPORTED NUMBER: {number}
DATE: {date}
OPERATION SCALE: Multi-vendor network

This account is:
- Selling counterfeit brand-name products
- Using fake "authentic" claims
- Shipping illegal replicas
- Processing payments for fake goods
- Defrauding customers with fake warranties

Documented:
- Product listings
- Fake certificates of authenticity
- Customer complaints
- Transaction amounts

Request immediate termination and referral to trademark authorities.

Regards,
{sender_name}
{sender_location}"""
        },
        {
            "id": "ill_09",
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
        {
            "id": "ill_10",
            "subject": "Wildlife trafficking - {number}",
            "body": """Dear WhatsApp Trust & Safety,

I am reporting suspected wildlife trafficking.

REPORTED NUMBER: {number}
DATE: {date}
SUSPICION: Illegal wildlife trade

This account is:
- Offering protected species for sale
- Sharing photos of endangered animals
- Discussing illegal transport arrangements
- Using coded language to avoid detection
- Pricing rare species

Evidence includes:
- Animal photos
- Pricing
- Shipping discussions
- Buyer communications

This violates international wildlife protection laws and CITES conventions.

I have notified wildlife protection authorities.

Request immediate termination.

Regards,
{sender_name}
{sender_location}"""
        },
    ],
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
    return random.choice(list(WA_REPORT_EMAILS.values()))


# ============================================================
# [5] ★★★ نظام Anti-Repeat ★★★
# ============================================================
def get_used_template_ids(user_id):
    """يجلب الـ IDs اللي استخدمها المستخدم"""
    if not redis_client or not user_id:
        return set()
    try:
        used = redis_client.smembers(f"wa_used_templates:{user_id}")
        return set(used or [])
    except Exception:
        return set()


def mark_template_used(user_id, template_id):
    """يحفظ الـ template ID كمستخدم"""
    if not redis_client or not user_id or not template_id:
        return
    try:
        redis_client.sadd(f"wa_used_templates:{user_id}", template_id)
        redis_client.expire(f"wa_used_templates:{user_id}", 86400 * 90)
    except Exception as e:
        logger.warning(f"mark_template_used error: {e}")


def pick_unique_template(user_id, reason):
    """يختار قالب ما استخدمه المستخدم قبل كده"""
    templates = REPORT_TEMPLATES.get(reason, [])
    if not templates:
        templates = REPORT_TEMPLATES["spam"]

    if not user_id:
        return random.choice(templates)

    used_ids = get_used_template_ids(user_id)

    # فلتر القوالب غير المستخدمة
    available = [t for t in templates if t.get("id") not in used_ids]

    # لو كل القوالب مستخدمة، reset
    if not available:
        try:
            redis_client.delete(f"wa_used_templates:{user_id}")
        except Exception:
            pass
        available = templates
        logger.info(f"Reset template pool for user {user_id}")

    chosen = random.choice(available)
    mark_template_used(user_id, chosen.get("id"))

    logger.info(f"User {user_id} got template {chosen.get('id')} ({len(used_ids)} used before)")
    return chosen


# ============================================================
# [6] Payload Storage
# ============================================================
def save_report_payload(to_email, subject, body):
    """يحفظ البلاغ في Redis ويرجع ID قصير"""
    if not redis_client:
        logger.error("save_report_payload: No Redis")
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
        logger.info(f"Report payload saved: {payload_id}")
        return payload_id
    except Exception as e:
        logger.exception(f"save_report_payload error: {e}")
        return None


def get_report_payload(payload_id):
    """يجلب البلاغ من Redis"""
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
def generate_report(victim_number, reason="spam", user_id=None):
    """
    يولد بلاغ كامل مع قالب فريد لكل مستخدم
    """
    number = normalize_number(victim_number)
    if not number:
        return {"error": "رقم غير صالح"}

    # اختر قالب فريد للمستخدم
    template = pick_unique_template(user_id, reason)
    to_email = pick_random_email()

    # متغيرات ديناميكية
    vars_dict = {
        "number": number,
        "date": time.strftime("%Y-%m-%d"),
        "time": time.strftime("%H:%M"),
        "days": random.randint(3, 30),
        "sender_name": random.choice(SENDER_NAMES),
        "sender_location": random.choice(SENDER_LOCATIONS),
        "device": random.choice(DEVICES),
        "amount": random.choice(LOST_AMOUNTS),
        "specific_time": random.choice(SPECIFIC_TIMES),
        "report_id": f"WR-{random.randint(100000, 999999)}",
    }

    subject = template["subject"].format(**vars_dict)
    body = template["body"].format(**vars_dict)

    # احفظ في Redis
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
    }


# ============================================================
# [8] Session Management
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


def get_template_stats():
    """إحصائيات القوالب"""
    stats = {}
    for reason, templates in REPORT_TEMPLATES.items():
        stats[reason] = len(templates)
    stats["total"] = sum(stats.values())
    return stats
