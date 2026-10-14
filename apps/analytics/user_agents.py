"""Coarse user-agent classification: device class, browser family, OS family, and bots.

Deliberately coarse — enough for "how many visits came from phones" without fingerprinting
anyone. The raw user-agent string is never stored.
"""

import re
from dataclasses import dataclass

_BOT = re.compile(
    r"bot|crawl|spider|slurp|facebookexternalhit|embedly|preview|headless|lighthouse|pingdom|"
    r"uptime|monitor|curl|wget|python-requests|httpx|go-http-client|java/|okhttp|axios|node-fetch|"
    r"playwright|puppeteer|phantomjs|selenium",
    re.IGNORECASE,
)
_TABLET = re.compile(r"ipad|tablet|(android(?!.*mobile))", re.IGNORECASE)
_MOBILE = re.compile(r"mobi|iphone|ipod|android.*mobile|windows phone", re.IGNORECASE)

# Order matters: Edge and Opera also say "Chrome"; Chrome also says "Safari".
_BROWSERS = (
    ("Edge", re.compile(r"edg(e|a|ios)?/", re.IGNORECASE)),
    ("Opera", re.compile(r"opr/|opera", re.IGNORECASE)),
    ("Samsung Internet", re.compile(r"samsungbrowser", re.IGNORECASE)),
    ("Firefox", re.compile(r"firefox|fxios", re.IGNORECASE)),
    ("Chrome", re.compile(r"chrome|crios", re.IGNORECASE)),
    ("Safari", re.compile(r"safari", re.IGNORECASE)),
)
_OS = (
    ("iOS", re.compile(r"iphone|ipad|ipod", re.IGNORECASE)),
    ("Android", re.compile(r"android", re.IGNORECASE)),
    ("Windows", re.compile(r"windows", re.IGNORECASE)),
    ("macOS", re.compile(r"mac os x|macintosh", re.IGNORECASE)),
    ("Linux", re.compile(r"linux|x11", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Client:
    is_bot: bool
    device: str
    browser: str
    os: str


def classify(user_agent: str) -> Client:
    ua = user_agent or ""
    if not ua or _BOT.search(ua):
        return Client(is_bot=True, device="desktop", browser="", os="")
    device = "tablet" if _TABLET.search(ua) else "mobile" if _MOBILE.search(ua) else "desktop"
    browser = next((name for name, rx in _BROWSERS if rx.search(ua)), "Other")
    os_name = next((name for name, rx in _OS if rx.search(ua)), "Other")
    return Client(is_bot=False, device=device, browser=browser, os=os_name)
