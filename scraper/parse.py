"""Company-specific parsing logic for FLOWX.AI (Workable API)."""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

from .config import scraper
from . import fetch

log = logging.getLogger("scraper.parse")

WORKABLE_SLUG = "flowxai"

_SEL = scraper["selectors"]

_DIACRITICS = str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t"})
_NONWORD = re.compile(r"[^a-z0-9]+")
_DMY_RX = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_ISO_RX = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+Z?)?")


def slugify(text: str) -> str:
    lowered = str(text).lower().translate(_DIACRITICS)
    stripped = "".join(c for c in unicodedata.normalize("NFD", lowered) if unicodedata.category(c) != "Mn")
    return _NONWORD.sub("-", stripped).strip("-")


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_deadline(text: str | None) -> str | None:
    if not text:
        return None
    s = str(text)
    m = _DMY_RX.search(s)
    if m:
        dd, mm, yyyy = (int(x) for x in m.groups())
        try:
            return iso_z(datetime(yyyy, mm, dd, 23, 59, 59, tzinfo=timezone.utc))
        except ValueError:
            return None
    m = _ISO_RX.search(s)
    if m:
        try:
            dt = datetime.fromisoformat(m.group(0).replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return iso_z(dt)
    return None


def location_from_title(title: str, default_location: list[str]) -> list[str]:
    return default_location


def validate_ro_locations(locations: list[str] | None) -> list[str]:
    return locations or ["România"]


def normalize_workmode(workmode: str | None) -> str | None:
    if not workmode:
        return None
    lower = workmode.lower()
    if "remote" in lower:
        return "remote"
    if "office" in lower or "on-site" in lower or "site" in lower:
        return "on-site"
    return "hybrid"


def parse_listing(html: str, selectors: dict | None = None) -> list[dict]:
    """Fetch jobs directly from the Workable API and filter for Romania."""
    api_url = f"https://apply.workable.com/api/v1/widget/accounts/{WORKABLE_SLUG}?details=true"
    
    response = fetch.get(api_url, label="workable api")
    if not response.ok:
        log.error("Failed to fetch Workable API: %s", response.status_code)
        return []
        
    data = response.json()
    jobs = []
    
    for job in data.get("jobs", []):
        country = str(job.get("country", "")).lower()
        if "romania" in country or country == "ro":
            title = job.get("title", "").strip()
            job_url = job.get("url", "").strip()
            city = job.get("city", "București").strip() or "București"
            
            if title and job_url:
                jobs.append({
                    "title": title,
                    "url": job_url,
                    "city": [city],
                })
                
    log.info("parse_listing: found %d jobs via Workable API", len(jobs))
    return jobs
