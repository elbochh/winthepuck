"""Two small defences the website did not have: response headers and throttling.

Neither is exotic, and neither costs anything. They are here because a login
form with no limit on how fast somebody can guess is the single easiest thing
to attack on a site like this, and because a browser will happily do dangerous
things unless it is told not to.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

# Response headers
#
# Team crests are loaded from the NHL's own asset host, so images have to be
# allowed from there. Everything else is locked to our own origin, which is
# what makes the policy worth having: an injected <script src="..."> pointing
# anywhere else simply will not run.
#
# The one relaxation is `style-src 'unsafe-inline'`, and it is deliberate.
# Half the interface is coloured from the database - each club's own shade on
# its badge, the width of a probability bar, the hue of a member's avatar -
# and those arrive as style attributes because the value is different for
# every row. A stricter policy silently refused to apply them and the site
# rendered with every bar collapsed to nothing.
#
# It is a much smaller concession than it sounds. The dangerous half of CSP is
# `script-src`, which stays strict: no inline scripts, no scripts from anywhere
# but our own origin. A style attribute cannot execute anything, the values
# going into these are numbers and hex colours from our own tables, and Jinja2
# escapes them on the way out.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "img-src 'self' https://assets.nhle.com data:",
    "style-src 'self' 'unsafe-inline'",
    "script-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
])

SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    # Stop a browser guessing that a .json file is really HTML and running it.
    "X-Content-Type-Options": "nosniff",
    # Nobody may put the site in an iframe, so it cannot be used for clickjacking.
    "X-Frame-Options": "DENY",
    # Do not leak the page somebody came from to other sites.
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # We ask for no camera, microphone or location, so switch them all off.
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# Only sent once the site is on https, because promising HSTS over plain http
# is meaningless and browsers ignore it.
HSTS_HEADER = "max-age=31536000; includeSubDomains"


def apply_headers(response, https: bool):
    """
    Attach the security headers to a response on its way out.

    setdefault rather than assignment, so a view that has deliberately set its
    own value for one of these keeps it. HSTS is only sent over https, because
    sending it from a plain http response tells the browser nothing useful and
    would lock out local development.
    """
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if https:
        response.headers.setdefault("Strict-Transport-Security", HSTS_HEADER)
    return response


# Rate limiting

class RateLimiter:
    """
    Allow so many attempts from one address in a window, then start refusing.

    This keeps a deque of timestamps per caller and drops the ones that have
    aged out, so memory stays proportional to recent traffic rather than to
    total traffic.

    Worth being honest about the limit: gunicorn runs two worker processes on
    Azure and each has its own copy of this, so the real ceiling is roughly
    double what is configured. Stopping somebody grinding through a password
    list does not need to be exact, and the alternative - Redis - is not free.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, caller: str, now: float | None = None) -> bool:
        """True if this caller may proceed; records the attempt when it does."""
        now = time.monotonic() if now is None else now
        hits = self._hits[caller]

        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= self.limit:
            return False

        hits.append(now)
        return True

    def retry_after(self, caller: str, now: float | None = None) -> int:
        """Roughly how many seconds until this caller gets another go."""
        now = time.monotonic() if now is None else now
        hits = self._hits.get(caller)
        if not hits:
            return 0
        return max(0, int(self.window - (now - hits[0])) + 1)

    def reset(self, caller: str) -> None:
        """Clear somebody's record - used after a successful sign-in."""
        self._hits.pop(caller, None)


def client_address(request) -> str:
    """
    Who is asking.

    Azure App Service sits behind a load balancer, so request.remote_addr is
    the balancer, not the visitor. The real address is the first entry in
    X-Forwarded-For. That header can be forged by anyone talking to the site
    directly, which is fine here: the worst a forger achieves is throttling
    themselves under a name they made up.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first.rsplit(":", 1)[0] if first.count(":") == 1 else first
    return request.remote_addr or "unknown"
