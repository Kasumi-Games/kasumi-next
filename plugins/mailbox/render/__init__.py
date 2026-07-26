from .mail import mail_page
from .mail import render_mail
from .claim import claim_all_page
from .claim import render_claim_all
from .inbox import inbox_page
from .inbox import render_inbox

__all__ = [
    "claim_all_page",
    "inbox_page",
    "mail_page",
    "render_claim_all",
    "render_inbox",
    "render_mail",
]
