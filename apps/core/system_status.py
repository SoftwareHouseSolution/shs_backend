"""System status: health checks for the server, database, cache, media and configuration.

Read by Admin → System → System status and `manage.py system_status`. Nothing here runs on
public requests: every probe runs only when someone opens that page or the command, the
full report is cached for REPORT_TTL seconds, the media scan (the one probe that touches
every file) for MEDIA_SCAN_TTL, and database probes run under a statement timeout — so
monitoring can never become the thing that slows the site down.

Each section is built independently; a probe that fails shows up as an error in its own
section instead of breaking the page.
"""

import hashlib
import logging
import os
import platform
import shutil
import sys
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import django
from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext as _

OK, INFO, WARNING, ERROR = "ok", "info", "warning", "error"
_SEVERITY = {OK: 0, INFO: 0, WARNING: 1, ERROR: 2}
_TONES = {OK: "success", INFO: "neutral", WARNING: "warning", ERROR: "danger"}


def _worst(statuses) -> str:
    """The most severe status; informational checks count as healthy."""
    worst = max(statuses, key=_SEVERITY.__getitem__, default=OK)
    return OK if worst == INFO else worst


def status_label(status: str) -> str:
    return {OK: _("Healthy"), INFO: _("Info"), WARNING: _("Warning"), ERROR: _("Problem")}[status]

REPORT_KEY = "system-status:report"
REPORT_TTL = 30
MEDIA_SCAN_KEY = "system-status:media-scan"
MEDIA_SCAN_TTL = 600
ERRORS_KEY = "system-status:recent-errors"
ERRORS_KEPT = 50
DB_STATEMENT_TIMEOUT_MS = 3000

# Set when the process imports this module (at startup, from CoreConfig.ready).
PROCESS_STARTED = time.time()


@dataclass
class Check:
    label: str
    status: str
    value: str = ""
    detail: str = ""

    @property
    def tone(self) -> str:
        return _TONES[self.status]


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[str]]
    empty: str = ""


@dataclass
class Section:
    key: str
    title: str
    icon: str
    checks: list[Check] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)

    @property
    def status(self) -> str:
        return _worst(c.status for c in self.checks)

    @property
    def tone(self) -> str:
        return _TONES[self.status]

    @property
    def status_label(self) -> str:
        return status_label(self.status)


@dataclass
class Report:
    sections: list[Section]
    generated_at: object
    duration_ms: int

    @property
    def status(self) -> str:
        return _worst(s.status for s in self.sections)

    @property
    def tone(self) -> str:
        return _TONES[self.status]

    @property
    def headline(self) -> str:
        errors, warnings = self.count(ERROR), self.count(WARNING)
        if errors:
            return _("%(n)d problem(s) need attention") % {"n": errors}
        if warnings:
            return _("Running, with %(n)d warning(s)") % {"n": warnings}
        return _("All systems healthy")

    def count(self, status: str) -> int:
        return sum(1 for s in self.sections for c in s.checks if c.status == status)

    @property
    def problems(self) -> list[tuple[Section, Check]]:
        found = [(s, c) for s in self.sections for c in s.checks if c.status in (WARNING, ERROR)]
        return sorted(found, key=lambda sc: -_SEVERITY[sc[1].status])


# ── Formatting ───────────────────────────────────────────────────────────────────────


def human_bytes(n: float | None) -> str:
    if n is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""  # pragma: no cover


def human_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m" if minutes else f"{seconds}s"


def _pct(part: float, whole: float) -> float:
    return 100 * part / whole if whole else 0


def _level(value: float, *, warn: float, error: float) -> str:
    """OK below `warn`, WARNING from it, ERROR from `error` (higher is worse)."""
    if value >= error:
        return ERROR
    if value >= warn:
        return WARNING
    return OK


# ── Sections ─────────────────────────────────────────────────────────────────────────


def _application() -> Section:
    s = Section("app", _("Application"), "deployed_code")
    mode = _("Development (DEBUG on)") if settings.DEBUG else _("Production")
    s.checks.append(Check(_("Environment"), INFO, mode, os.environ.get("DJANGO_SETTINGS_MODULE", "")))
    s.checks.append(Check(_("Versions"), INFO, f"Django {django.get_version()} · Python {platform.python_version()}"))
    s.checks.append(Check(_("Process uptime"), INFO, human_duration(time.time() - PROCESS_STARTED), f"PID {os.getpid()}"))
    rss = _process_memory()
    if rss is not None:
        s.checks.append(Check(_("Process memory"), _level(rss, warn=768 * 2**20, error=1536 * 2**20), human_bytes(rss)))

    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    if pending:
        names = ", ".join(f"{m.app_label}.{m.name}" for m, _backwards in pending[:5])
        s.checks.append(Check(_("Database migrations"), ERROR, _("%(n)d not applied") % {"n": len(pending)},
                              _("Run `manage.py migrate`: %(names)s") % {"names": names}))
    else:
        s.checks.append(Check(_("Database migrations"), OK, _("All applied")))
    return s


def _server() -> Section:
    s = Section("server", _("Server"), "dns")
    cpus = os.cpu_count() or 1
    s.checks.append(Check(_("Host"), INFO, platform.node() or "—", f"{platform.system()} {platform.release()} · {cpus} CPU"))
    if hasattr(os, "getloadavg"):
        load1, load5, load15 = os.getloadavg()
        s.checks.append(Check(
            _("CPU load (1 / 5 / 15 min)"),
            _level(load5 / cpus, warn=1.0, error=2.0),
            f"{load1:.2f} / {load5:.2f} / {load15:.2f}",
            _("Sustained load above the CPU count (%(n)d) means requests queue.") % {"n": cpus},
        ))
    mem = _host_memory()
    if mem:
        total, available = mem
        used = _pct(total - available, total)
        s.checks.append(Check(_("Memory"), _level(used, warn=85, error=95), f"{used:.0f}%",
                              _("%(free)s free of %(total)s") % {"free": human_bytes(available), "total": human_bytes(total)}))
    root = Path(settings.MEDIA_ROOT)
    usage = shutil.disk_usage(root if root.exists() else settings.BASE_DIR)
    used = _pct(usage.used, usage.total)
    s.checks.append(Check(_("Disk (media volume)"), _level(used, warn=85, error=95), f"{used:.0f}%",
                          _("%(free)s free of %(total)s") % {"free": human_bytes(usage.free), "total": human_bytes(usage.total)}))
    return s


def _database() -> Section:
    s = Section("database", _("Database"), "database")
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    latency = (time.perf_counter() - started) * 1000
    s.checks.append(Check(_("Connection"), _level(latency, warn=100, error=1000), f"{latency:.1f} ms",
                          _("Round trip of SELECT 1")))
    if connection.vendor != "postgresql":
        s.checks.append(Check(_("Engine"), INFO, connection.vendor))
        return s

    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL statement_timeout = {DB_STATEMENT_TIMEOUT_MS}")

        def one(sql: str):
            cursor.execute(sql)
            return cursor.fetchone()

        version = one("SHOW server_version")[0]
        size = one("SELECT pg_database_size(current_database())")[0]
        s.checks.append(Check(_("Server"), INFO, f"PostgreSQL {version.split()[0]}", connection.settings_dict.get("NAME", "")))
        s.checks.append(Check(_("Database size"), INFO, human_bytes(size)))

        used, limit = one(
            "SELECT (SELECT count(*) FROM pg_stat_activity), current_setting('max_connections')::int"
        )
        s.checks.append(Check(_("Connections"), _level(_pct(used, limit), warn=80, error=95), f"{used} / {limit}",
                              _("Open connections against the server's limit")))

        longest = one(
            "SELECT coalesce(extract(epoch FROM max(now() - query_start)), 0) FROM pg_stat_activity "
            "WHERE state = 'active' AND pid <> pg_backend_pid() AND datname = current_database()"
        )[0]
        s.checks.append(Check(_("Longest running query"), _level(float(longest), warn=30, error=300),
                              human_duration(float(longest)) if longest else _("None running")))

        hit, read, deadlocks = one(
            "SELECT blks_hit, blks_read, deadlocks FROM pg_stat_database WHERE datname = current_database()"
        )
        if hit + read > 10_000:
            ratio = _pct(hit, hit + read)
            s.checks.append(Check(_("Cache hit ratio"), WARNING if ratio < 90 else OK, f"{ratio:.1f}%",
                                  _("Share of reads served from memory; below 90% the database needs more RAM.")))
        s.checks.append(Check(_("Deadlocks"), WARNING if deadlocks else OK, str(deadlocks), _("Since statistics were last reset")))

        cursor.execute(
            "SELECT relname, n_live_tup, n_dead_tup, pg_total_relation_size(relid) FROM pg_stat_user_tables "
            "ORDER BY pg_total_relation_size(relid) DESC LIMIT 6"
        )
        s.tables.append(Table(
            _("Largest tables"),
            [_("Table"), _("Rows"), _("Dead rows"), _("Size")],
            [[name, f"{live:,}", f"{dead:,}", human_bytes(total)] for name, live, dead, total in cursor.fetchall()],
        ))
    return s


def _cache() -> Section:
    s = Section("cache", _("Cache"), "bolt")
    backend = settings.CACHES["default"]["BACKEND"].rsplit(".", 1)[-1]
    key, value = "system-status:probe", str(time.time())
    started = time.perf_counter()
    cache.set(key, value, 10)
    readback = cache.get(key)
    cache.delete(key)
    latency = (time.perf_counter() - started) * 1000
    if readback != value:
        s.checks.append(Check(_("Read / write"), ERROR, _("Failed"), _("A value written to the cache could not be read back.")))
    else:
        s.checks.append(Check(_("Read / write"), _level(latency, warn=50, error=500), f"{latency:.1f} ms", backend))
    return s


def _media() -> Section:
    s = Section("media", _("Media files"), "perm_media")
    root = Path(settings.MEDIA_ROOT)
    if not root.is_dir():
        s.checks.append(Check(_("Media folder"), ERROR, _("Missing"), str(root)))
        return s
    writable = os.access(root, os.W_OK)
    s.checks.append(Check(_("Media folder"), OK if writable else ERROR,
                          _("Writable") if writable else _("Not writable"), str(root)))

    scan = cache.get(MEDIA_SCAN_KEY)
    if scan is None:
        scan = scan_media(root)
        cache.set(MEDIA_SCAN_KEY, scan, MEDIA_SCAN_TTL)
    scanned = timezone.localtime(scan["at"]).strftime("%H:%M")
    s.checks.append(Check(_("Stored files"), INFO, f"{scan['files']:,}",
                          _("%(size)s · scanned at %(t)s") % {"size": human_bytes(scan["bytes"]), "t": scanned}))

    missing = scan["missing"]
    s.checks.append(Check(
        _("Files used by content"),
        ERROR if missing else OK,
        _("%(n)d missing") % {"n": len(missing)} if missing else _("All present"),
        _("Content points at files that are not on disk; the site shows broken images.") if missing
        else _("%(n)d files referenced") % {"n": scan["referenced"]},
    ))
    if missing:
        s.tables.append(Table(_("Missing files"), [_("File")], [[name] for name in missing[:15]]))

    s.checks.append(Check(
        _("Duplicate copies"),
        INFO,
        f"{scan['duplicates']:,}",
        _("%(size)s in identical copies of other files; new uploads never add more.") % {"size": human_bytes(scan["duplicate_bytes"])}
        if scan["duplicates"] else _("No file is stored twice."),
    ))
    unused = scan["unused"]
    s.checks.append(Check(_("Unused files"), INFO, f"{unused:,}",
                          _("%(size)s on disk that no content uses") % {"size": human_bytes(scan["unused_bytes"])}))

    trash = scan["trash"]
    if trash["files"]:
        s.checks.append(Check(_("Trash"), INFO, f"{trash['files']:,}",
                              _("%(size)s set aside by clean-ups; restore or delete them on the clean-up page.") % {"size": human_bytes(trash["bytes"])}))

    from .models import StoredFile

    indexed = StoredFile.objects.count()
    s.checks.append(Check(
        _("Duplicate-upload index"),
        WARNING if scan["files"] and not indexed else OK,
        f"{indexed:,}",
        _("Run `manage.py index_media` so re-uploads of existing files are recognised.") if scan["files"] and not indexed
        else _("Distinct files known to the upload de-duplication"),
    ))
    return s


def scan_media(root: Path) -> dict:
    """Walk the media folder once: totals, referenced files missing from disk, files no
    content uses, and identical copies (hashing only files that share a size)."""
    from .media import media_files, referenced_media

    referenced = referenced_media()
    by_size: dict[int, list[Path]] = defaultdict(list)
    names: set[str] = set()
    total = unused = unused_bytes = 0
    for name, path in media_files(root):
        size = path.stat().st_size
        names.add(name)
        total += size
        by_size[size].append(path)
        if name not in referenced:
            unused += 1
            unused_bytes += size

    duplicates = duplicate_bytes = 0
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        digests = defaultdict(int)
        for path in paths:
            digests[_file_sha256(path)] += 1
        extra = sum(n - 1 for n in digests.values())
        duplicates += extra
        duplicate_bytes += extra * size

    from .media_cleanup import trash_batches

    batches = trash_batches()
    return {
        "at": timezone.now(),
        "trash": {"files": sum(b.count for b in batches), "bytes": sum(b.size for b in batches)},
        "files": len(names),
        "bytes": total,
        "referenced": len(referenced),
        "missing": sorted(referenced - names),
        "unused": unused,
        "unused_bytes": unused_bytes,
        "duplicates": duplicates,
        "duplicate_bytes": duplicate_bytes,
    }


def _configuration() -> Section:
    s = Section("config", _("Configuration"), "tune")
    from django.core import checks

    messages = checks.run_checks(include_deployment_checks=not settings.DEBUG)
    serious = [m for m in messages if m.level >= checks.WARNING and not m.is_silenced()]
    errors = [m for m in serious if m.level >= checks.ERROR]
    s.checks.append(Check(
        _("Django system checks"),
        ERROR if errors else WARNING if serious else OK,
        _("%(n)d issue(s)") % {"n": len(serious)} if serious else _("No issues"),
        _("Including the production security checks") if not settings.DEBUG else "",
    ))
    if serious:
        s.tables.append(Table(_("System check findings"), [_("Check"), _("Message")],
                              [[m.id or "", str(m.msg)] for m in serious[:15]]))

    if not settings.DEBUG:
        backend = settings.EMAIL_BACKEND.rsplit(".", 2)[-2]  # smtp, console, dummy, …
        sends = backend not in {"console", "dummy", "locmem", "filebased"}
        s.checks.append(Check(_("E-mail"), OK if sends else WARNING, backend,
                              "" if sends else _("Enquiry notifications are not being sent.")))
        s.checks.append(Check(
            _("Public media URL"),
            OK if settings.MEDIA_PUBLIC_BASE_URL else WARNING,
            settings.MEDIA_PUBLIC_BASE_URL or _("Not set"),
            "" if settings.MEDIA_PUBLIC_BASE_URL else _("Set MEDIA_PUBLIC_BASE_URL so image links use the public address."),
        ))

    from apps.analytics.models import VisitSession

    oldest = VisitSession.objects.order_by("started_at").values_list("started_at", flat=True).first()
    keep = settings.ANALYTICS_RETENTION_DAYS
    if oldest and timezone.now() - oldest > timedelta(days=keep + 7):
        s.checks.append(Check(_("Analytics clean-up"), WARNING, _("Overdue"),
                              _("Visits older than %(n)d days remain; schedule `manage.py prune_analytics` daily.") % {"n": keep}))
    else:
        s.checks.append(Check(_("Analytics clean-up"), OK, _("Up to date"),
                              _("Visits are kept for %(n)d days") % {"n": keep}))
    return s


def _errors() -> Section:
    s = Section("errors", _("Recent errors"), "bug_report")
    entries = recent_errors()
    day_ago = time.time() - 86400
    last_day = [e for e in entries if e["at"] >= day_ago]
    s.checks.append(Check(
        _("Errors in the last 24 hours"),
        _level(len(last_day), warn=1, error=20),
        str(len(last_day)),
        _("Logged since this process started; the full log is on the server."),
    ))
    s.tables.append(Table(
        _("Latest errors"),
        [_("Time"), _("Source"), _("Message"), _("Request")],
        [
            [datetime.fromtimestamp(e["at"], tz=timezone.get_current_timezone()).strftime("%d %b %H:%M:%S"),
             e["logger"], e["message"], e["request_id"]]
            for e in entries[:12]
        ],
        empty=_("No errors logged."),
    ))
    return s


SECTIONS: list[Callable[[], Section]] = [_application, _server, _database, _cache, _media, _configuration, _errors]


def build_report(*, use_cache: bool = True) -> Report:
    key = f"{REPORT_KEY}:{get_language()}"  # labels are translated when the report is built
    if use_cache and (cached := cache.get(key)) is not None:
        return cached
    if not use_cache:
        cache.delete(MEDIA_SCAN_KEY)
    started = time.perf_counter()
    sections = [_safely(builder) for builder in SECTIONS]
    report = Report(sections, timezone.now(), round((time.perf_counter() - started) * 1000))
    cache.set(key, report, REPORT_TTL)
    return report


def _safely(builder: Callable[[], Section]) -> Section:
    try:
        return builder()
    except Exception as exc:  # one broken probe must not take the page down
        logging.getLogger(__name__).warning("System status probe %s failed: %s", builder.__name__, exc)
        title = builder.__name__.strip("_").replace("_", " ").capitalize()
        return Section(builder.__name__.strip("_"), title, "error",
                       [Check(_("Check could not run"), ERROR, type(exc).__name__, str(exc)[:300])])


# ── Probes ───────────────────────────────────────────────────────────────────────────


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _process_memory() -> int | None:
    """Resident memory of this process in bytes: /proc on Linux, else the peak from
    getrusage on other Unixes, else None (Windows development)."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    try:
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak if sys.platform == "darwin" else peak * 1024
    except (ImportError, AttributeError):
        return None


def _host_memory() -> tuple[int, int] | None:
    """(total, available) bytes from /proc/meminfo; None where it does not exist."""
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _sep, rest = line.partition(":")
            info[key] = int(rest.split()[0]) * 1024
        return info["MemTotal"], info["MemAvailable"]
    except (OSError, KeyError, ValueError, IndexError):
        return None


# ── Recent errors ────────────────────────────────────────────────────────────────────


def recent_errors() -> list[dict]:
    return cache.get(ERRORS_KEY) or []


class RecentErrorsHandler(logging.Handler):
    """Keeps the last ERRORS_KEPT error records in the cache for the status page.

    Only ERROR and above reach it, so it costs nothing on healthy requests. It must never
    raise or log itself: a failure here is dropped, and re-entry (the cache logging an
    error while we write to it) is ignored.
    """

    _local = threading.local()

    def __init__(self, level=logging.ERROR):
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._local, "busy", False) or record.name.startswith(__name__):
            return
        self._local.busy = True
        try:
            message = record.getMessage().splitlines()[0][:300] if record.msg else ""
            if record.exc_info and record.exc_info[1] is not None and not message:
                message = repr(record.exc_info[1])[:300]
            entry = {
                "at": record.created,
                "level": record.levelname,
                "logger": record.name,
                "message": message,
                "request_id": getattr(record, "request_id", "-"),
            }
            cache.set(ERRORS_KEY, [entry, *recent_errors()][:ERRORS_KEPT], 7 * 86400)
        except Exception:  # noqa: BLE001 - logging must never break the request
            pass
        finally:
            self._local.busy = False
