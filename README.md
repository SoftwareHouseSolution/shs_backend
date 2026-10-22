# SWH Backend — Django REST API and bilingual CMS

The content API and editing interface for the Software House Solutions website
(`../shs_frontend`). Every page, menu, hero slide, figure, client, event, image and video
on the site is managed here, in English and Arabic, through the Django admin, and served to
the Next.js frontend through a versioned REST API with one consistent response envelope.

- **Admin (CMS):** `http://localhost:8000/admin/`
- **API:** `http://localhost:8000/api/v1/`
- **API docs:** Swagger UI at `/api/v1/docs/`, ReDoc at `/api/v1/redoc/`, raw OpenAPI 3 at `/api/v1/schema/`

---

## Contents

1. [Stack](#stack)
2. [Quick start](#quick-start)
3. [Environment variables](#environment-variables)
4. [Project structure](#project-structure)
5. [Managing content in the admin](#managing-content-in-the-admin)
6. [API reference](#api-reference)
7. [Architecture](#architecture)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Known limitations](#known-limitations)

---

## Stack

Tested with these exact versions (`requirements.lock.txt`); `pyproject.toml` /
`requirements.txt` hold the compatible ranges.

| Package | Version | Role |
| --- | --- | --- |
| Python | 3.12 | |
| Django | 5.2 (LTS) | |
| djangorestframework | 3.16 | API |
| drf-spectacular | 0.30 | OpenAPI 3 schema, Swagger/ReDoc |
| django-modeltranslation | 0.20 | `title_en` / `title_ar` columns, fallback |
| django-unfold | 0.110 | admin theme: tabs, drag-to-reorder, conditional fields |
| django-filter | 26 | list filtering |
| django-cors-headers | 4.9 | browser access from the site |
| django-environ | 0.14 | settings from the environment |
| psycopg (binary) | 3.3 | PostgreSQL driver |
| Pillow | 12 | image validation |
| whitenoise | 6.12 | static files in production |
| gunicorn | 26 | WSGI server (Linux) |
| pytest / pytest-django / ruff | 9 / 4.14 / 0.14 | tests, lint (dev) |

PostgreSQL 14+ (developed against 18).

---

## Quick start

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate      macOS/Linux: source venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
# Edit .env: set DJANGO_SECRET_KEY, DJANGO_DEBUG=true and DATABASE_URL, e.g.
#   DATABASE_URL=postgres://postgres:password@localhost:5432/shs_backend

createdb shs_backend                 # or CREATE DATABASE shs_backend; in psql
python manage.py migrate
python manage.py seed_content        # loads the site's bilingual content + 400 media files
python manage.py createsuperuser     # your admin login
python manage.py runserver 8000
```

`manage.py` uses `config.settings.dev` by default. Then start the frontend
(`../shs_frontend`, see its README) with `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1`.

> **Windows tip:** use `127.0.0.1` rather than `localhost` in the frontend's API URL.
> Node resolves `localhost` to IPv6 first and the dev server listens on IPv4 only.

### Seeding

`python manage.py seed_content` loads `seed/content.json` (every page, menu, slide, figure,
client and event in both languages, exported from the original site) and copies
`seed/media/` into media storage. It is **idempotent**: records are matched on natural keys
(slug, key, position) and updated in place, so re-running never duplicates anything and
never re-copies files that are already attached. `--replace-media` re-copies files.

### Creating an admin account

```bash
python manage.py createsuperuser
```

For editors who should not manage users, create a normal staff user in **Access → Users**,
tick *Staff status*, and give them a group with the content permissions they need
(e.g. all `pages`, `home`, `content`, `events`, `clients` permissions plus *view/change
enquiry*).

### Translations (API messages and the admin interface)

All Arabic strings — API messages, admin labels and help texts, and the Unfold admin
theme's own interface (it ships no Arabic) — live in
`apps/core/locale/ar/LC_MESSAGES/django.po`; the compiled `.mo` is committed. Django's own
admin strings come from Django's Arabic catalogue.

```bash
python scripts/extract_messages.py      # lists strings with no Arabic yet (JSON); empty = complete
# add msgid/msgstr pairs for them to the .po, then:
python scripts/compile_messages.py      # no GNU gettext needed
# or, with GNU gettext installed: python manage.py makemessages -l ar && python manage.py compilemessages
```

`extract_messages.py` is a gettext-free stand-in for `makemessages`: it scans `apps/`,
`config/`, `templates/` and the installed parts of Unfold, and skips strings that Django's
catalogues for installed apps already translate. One developer-only Unfold warning is
intentionally left in English.

---

## Environment variables

All settings are read from the environment (or `.env` in development). Only the first two
are required. Full annotated list: `.env.example`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | — (required) | Cryptographic signing |
| `DATABASE_URL` | — (required) | `postgres://user:pass@host:5432/db` |
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` (manage.py), `config.settings.prod` (wsgi/asgi) | |
| `DJANGO_DEBUG` | `false` (`true` in dev settings) | |
| `DJANGO_ALLOWED_HOSTS` | `[]` (localhost in dev) | Comma-separated |
| `DJANGO_ADMIN_URL` | `admin/` | Move the admin off the default path in production |
| `CORS_ALLOWED_ORIGINS` | localhost:3000/3001 in dev | The website's origin(s) — the contact form posts from there |
| `CSRF_TRUSTED_ORIGINS` | `[]` | Admin origin when behind HTTPS proxies |
| `FRONTEND_URL` | `http://localhost:3000` | "View site" link in the admin |
| `CACHE_URL` | local memory | `redis://…` in production (shared cache + rate limits) |
| `CONTENT_CACHE_TIMEOUT` | `300` | Seconds an API payload is cached (edits invalidate immediately anyway) |
| `DJANGO_MEDIA_ROOT` / `DJANGO_MEDIA_URL` | `./media`, `/media/` | Upload storage |
| `DJANGO_MEDIA_TRASH_ROOT` | `<media root>/.trash` | Where the media clean-up sets unused files aside; keep it outside the served folder |
| `MEDIA_PUBLIC_BASE_URL` | empty | Public origin for media URLs in API responses — **set in production** |
| `MAX_IMAGE_UPLOAD_MB` / `MAX_VIDEO_UPLOAD_MB` | `8` / `60` | Upload limits |
| `API_THROTTLE_ANON` | `600/min` | Global per-IP rate limit |
| `API_THROTTLE_ENQUIRIES` | `5/hour` | Per-IP contact-form submissions |
| `API_THROTTLE_REVIEWS` | `5/hour` | Per-IP client-review submissions |
| `API_THROTTLE_REVIEW_DRAFTS` | `30/hour` | Per-IP AI review drafts (each is a paid model call) |
| `ANTHROPIC_API_KEY` | — | Turns on AI-written review drafts; empty = the page's own templates |
| `REVIEW_AI_MODEL` | `claude-opus-5-5` | Model that writes the drafts |
| `REVIEW_NOTIFIER` | `…EmailReviewNotifier` | Who hears about new reviews (`NullReviewNotifier` disables) |
| `API_THROTTLE_ANALYTICS` | `120/min` | Per-IP page-view reports |
| `ANALYTICS_RETENTION_DAYS` | `180` | Visits older than this are removed by `prune_analytics` |
| `NUM_PROXIES` | `0` | Reverse proxies in front (for client IPs in rate limiting) |
| `ENQUIRY_NOTIFIER` | `…EmailEnquiryNotifier` | Or `…NullEnquiryNotifier` to disable e-mail |
| `ENQUIRY_NOTIFICATION_EMAIL` | empty | Fallback recipient (admin setting wins) |
| `ENQUIRY_DUPLICATE_WINDOW_MINUTES` | `10` | Same message from same e-mail inside this → 409 |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | console backend | SMTP for enquiry notifications |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `text` (`json` in prod) | |

---

## Project structure

```text
backend/
├── manage.py
├── pyproject.toml            # dependencies (ranges), pytest + ruff config
├── requirements*.txt         # pip install -r …; requirements.lock.txt = exact tested versions
├── .env.example
├── config/
│   ├── settings/{base,dev,test,prod}.py
│   ├── urls.py               # /admin/, /api/v1/…, envelope 404 catch-all for /api/
│   ├── api_responses.py      # THE response envelope (ApiResponse factory, json_error)
│   └── api_exceptions.py     # exception hierarchy + global DRF exception handler
├── apps/
│   ├── core/                 # shared infrastructure, no content of its own
│   │   ├── codes.py          # stable ResponseCode enum + localised default messages
│   │   ├── i18n.py           # language resolution chain (?lang → Accept-Language → en)
│   │   ├── middleware.py     # request id, API language, JSON safety net
│   │   ├── pagination.py     # envelope pagination (meta.pagination)
│   │   ├── views.py          # base views: cached object / list / retrieve, health, 404
│   │   ├── schema.py         # OpenAPI envelope + standard error responses
│   │   ├── cache.py          # versioned content cache, signal invalidation
│   │   ├── models.py         # TimeStamped / Ordered / Publishable / Singleton bases
│   │   ├── validators.py     # upload type/size/content, site-link validation
│   │   ├── media.py          # upload naming, absolute media URLs, LinkField
│   │   ├── storage.py        # media storage that reuses identical uploads (+ index_media)
│   │   ├── media_cleanup.py  # unused media → restorable trash (Admin → System status)
│   │   ├── system_status.py  # health checks behind Admin → System status (+ system_status)
│   │   ├── admin_utils.py    # ContentAdmin base, language tabs, RTL, previews, dashboard
│   │   ├── seeding.py + management/commands/seed_content.py
│   │   └── locale/ar/        # Arabic API messages
│   ├── site_config/          # Site settings, navigation, footer columns, social links, badges
│   ├── home/                 # Home page singleton, hero slides, figures, section items
│   ├── pages/                # Pages → content blocks → items; blocks.py = block strategies
│   ├── content/              # shared: comparison tables, testimonials, partners
│   ├── clients/              # clients, regions (map pins), sectors, business types
│   ├── events/               # news & events with photos
│   ├── enquiries/            # contact-form submissions: service, notifiers (adapters)
│   ├── reviews/              # client reviews from /<lang>/review: inbox, publish → testimonial
│   └── analytics/            # anonymous visits: page flow and time on page; dashboard reports
├── templates/admin/index.html  # admin dashboard
├── seed/content.json + seed/media/
├── scripts/compile_messages.py
├── tests/                    # API contract, exception handling, i18n, domain, admin, schema
└── conftest.py
```

Each domain app follows the same layout: `models.py`, `translation.py` (which fields are
bilingual), `selectors.py` (read queries), `serializers.py`, `views.py`, `admin.py`, and —
where there are business rules — `services.py`.

---

## Managing content in the admin

Log in at `/admin/`. The sidebar is grouped by what an editor is looking for.

**Admin language.** The admin is available in English and Arabic (right-to-left). It opens
in the browser's language; switch any time from the user menu at the bottom of the sidebar
(*English / العربيّة*) — the choice is remembered in a cookie. It only changes the admin's
interface: which content language you edit is chosen by the English/Arabic tabs on each
form, and the API's language is never affected by it. English inputs, links, e-mails and
slugs stay left-to-right inside the Arabic admin.

**Bilingual editing.** Every translatable record has **English** and **Arabic — العربية**
tabs. Arabic inputs are right-to-left. English is required; Arabic is optional — if it is
left empty the site shows the English text (see *Fallback* below). The **Translation**
column in list views flags records whose Arabic is incomplete, and the dashboard lists
pages with missing Arabic.

**Ordering.** Lists with a drag handle (navigation, slides, figures, blocks, events,
partners…) are reordered by dragging rows; the order is saved with the list.

**Publishing.** Pages, slides, figures, events, testimonials and clients have a *Published*
switch and *Publish / Unpublish selected* bulk actions. Unpublished items are kept but
hidden from the site — nothing is lost.

| To change… | Go to |
| --- | --- |
| Company name, phone, e-mail, WhatsApp, address, logo, favicon, "Book a demo" button, footer text, contact-section copy, default SEO, where enquiries are e-mailed | **Site → Site settings** |
| The menu (labels, links, dropdown groups) | **Site → Navigation** (a group's links are edited inside the group) |
| Footer link columns | **Site → Footer columns** (each lists the links of the menu groups you pick) |
| Social icons / certification badges | **Site → Social links**, **Badges** |
| Home page copy, hero slides, figures, services/modules/steps cards | **Pages → Home page** (tabs: General, Hero slides, Figures, Section items) |
| Any interior page's title, header image, SEO, blocks | **Pages → Interior pages** → the page |
| A page's content | On the page, **Content blocks** tab → *change* a block, or **+ Add a content block** |
| "Why choose SWH?" tables | **Shared content → Comparison tables** (columns inline; rows → cells) |
| Testimonials (one can be featured on the home page) | **Shared content → Testimonials** |
| Partner logos | **Shared content → Partners** |
| News & events and their photos | **Shared content → Events** |
| Clients, their logos, where they appear (home highlight, home strip, Customers strip) | **Clients → Clients** |
| Map regions and their pin coordinates | **Clients → Regions** |
| Contact-form messages | **Inbox → Enquiries** (badge = unread) |
| Who visited, which pages in what order, how long on each | **Dashboard → Visitors**, **Visitors → Visits / Page views** |

**Content blocks.** A page is an ordered list of blocks. Pick a *Type* and the form shows
only that type's fields: *Introduction*, *Cards*, *Numbered list*, *Steps*, *Partner
logos*, *Hardware tiles*, *Comparison table*, *Events timeline*, *Photo gallery* (from an
event), *Testimonials*, *Call to action*. Cards, list entries, steps and tiles are the
block's *items*. Missing required fields for the chosen type are reported on save.

**Links.** Internal links are written without the language: `/customers`, `/#contact`,
`#contact`. The site adds `/en` or `/ar` itself (`/en/...` is rejected). External links
(`https://…`), `mailto:` and `tel:` links are accepted.

**Images and video.** Uploads are checked for type (JPG/PNG/WebP/GIF; SVG for logos; MP4
and WebM for video), size (8 MB images, 60 MB video by default) and content (a renamed
non-image or an SVG with scripts is rejected). Hero slides accept an optional Arabic-only
image for artwork with baked-in text.

**Visitor analytics.** The dashboard's *Visitors* section shows the last 7 days (visitors,
visits, page views, average time on site, pages per visit), visits per day, the most-viewed
pages and the latest visits, each as a flow such as *Home 4s → Our Clients 7s → About
Company 12s*. **Visitors → Visits** lists every visit with its flow, device, language and
total time, filterable by date, device, language, browser and OS; open one for its
step-by-step timeline. **Visitors → Page views** lists individual page views by page.
Time on page counts only while the page is visible. Visits are anonymous — a random id per
browser and per tab, no cookies, no IP addresses — and browsers that send Do-Not-Track or
Global Privacy Control are not counted, nor are bots. Schedule
`python manage.py prune_analytics` daily to delete visits older than
`ANALYTICS_RETENTION_DAYS`.

**Client reviews.** Clients review the system at `/ar/review` (or `/en/review`) on the
website — share it as e.g. `https://softwarehouse-sol.com/ar/review?src=facebook`; the
`src` tag is recorded so you can see which channel brought each review. Three short steps
(who they are, four tapped answers plus three optional ones — business type, branches, what
they used before — and a drafted review they can edit) and the review lands in
**Inbox → Client reviews**, with a badge for new ones and an e-mail to the enquiries address
(subject prefixed `FOLLOW UP:` when support or updates were rated "needs improvement").
You decide what the website shows: open a review and click **Publish as testimonial** at
the top to put it on the Testimonials page (`/ar/testimonials`, newest first), and
**Remove from website** to take it off again (its testimonial is hidden, not deleted, so
publishing again restores any wording you polished). The same two actions work on several
reviews at once from the list. The status follows those buttons and is not edited by hand.
**Archive** keeps a new review private. The dashboard's *Client reviews* section
counts reviews, those waiting for you and those needing follow-up, and breaks down the
support and update ratings and what the system helped clients with. After sending, a client
is offered to also post the review on Facebook: set the post in **Site settings → Client
reviews** (empty hides that step).

**Review drafts.** With `ANTHROPIC_API_KEY` set, each draft is written by Claude
(`REVIEW_AI_MODEL`) from that client's own answers and words, in Egyptian Arabic on the Arabic
page, from a randomly chosen opening angle, so two clients with the same answers still get
different reviews; "write it another way" sends the previous draft so the next one avoids it.
It uses only the facts the client gave and keeps low ratings honest. Without a key, or if a
call fails, the page drafts from its own template engine (`shs_frontend/content/reviewDrafts.ts`)
— the form never depends on the AI. A draft costs roughly one cent at Claude Opus 5.5 prices;
`API_THROTTLE_REVIEW_DRAFTS` caps it per visitor. System status shows which mode is on.

**System status** (superusers only, **System → System status**) checks the application
(environment, uptime, memory, unapplied migrations), the server (CPU load, memory and disk
where the OS reports them), PostgreSQL (latency, size, connections, long-running queries,
cache hit ratio, deadlocks, largest tables), the cache, the media folder (files content
points at that are missing from disk, duplicate and unused files), configuration (Django's
system checks, including the production security checks) and the latest logged errors.
It costs nothing on public requests: checks run only when the page is opened, results are
reused for 30 seconds (the media scan for 10 minutes; **Check again** forces a fresh run),
and database probes run under a 3-second statement timeout. The same report is available
as `python manage.py system_status`, which exits with status 1 when a check fails
(`--strict`: also on warnings), for cron or CI alerting.

**Duplicate uploads.** Uploading an image or video that is already stored, to any record,
reuses the stored file instead of writing a copy; both records then show the same URL.
Files are matched by content (SHA-256), not by name. After deploying this or copying media
in by hand, run `python manage.py index_media` once so files already on disk are recognised.

**Cleaning up unused media** (System status → **Clean up unused files**). Lists files that
no content uses — checked against every file field and any `/media/…` path mentioned in
text — and that have not changed in the last hour, then moves them to `MEDIA_ROOT/.trash/`
in one batch. Nothing is deleted: each batch can be restored from the same page, or deleted
permanently once you are sure.

**When changes appear.** The API reflects a save immediately. A frontend running on
`next start` shows it within `CMS_REVALIDATE_SECONDS` (60 s by default). A static-export
frontend shows it after the next `pnpm build:static` and upload. A brand-new page needs a
frontend rebuild in both cases (routes are generated at build time).

---

## API reference

Base URL: `/api/v1/`. Public, anonymous, JSON only.

| Method | Path | Returns | Notes |
| --- | --- | --- | --- |
| GET | `/health/` | `{status, database}` | 503 when the database is down; not rate-limited |
| GET | `/site/` | settings, navigation, footer columns, social links, badges, language | One request for everything every page needs |
| GET | `/home/` | hero, figures, client band, services, big picture, comparison table, testimonial, how-to, events, closing band, SEO | |
| GET | `/pages/` | published pages `{slug, template, title, updated_at}` | paginated; `?template=`, `?search=`, `?ordering=` |
| GET | `/pages/{slug}/` | header, SEO, breadcrumb parent, intro video, ordered `blocks` | 404 if unpublished |
| GET | `/clients/` | `{slug, name, location, region, sector, business_types, logo, featured_order}` | paginated (100, max 500); `?region= &sector= &business_type= &featured=true &search= &ordering=name\|-name\|featured_order` |
| GET | `/clients/taxonomy/` | regions (with published counts and map pins), sectors, business types, total | |
| GET | `/events/` | `{slug, year, title, paras[], photos[]}` | paginated; `?search=` |
| GET | `/events/{slug}/` | one event | |
| GET | `/testimonials/` | published testimonials | paginated |
| GET | `/partners/` | `{name, logo, website, category}` | paginated; `?category=technology\|business` |
| POST | `/enquiries/` | `{reference, created_at}` (201) | contact form; JSON body; rate-limited |
| POST | `/reviews/` | `{reference, created_at}` (201) | client review page; multipart (optional `photo`), `benefits` repeated; rate-limited |
| POST | `/reviews/draft/` | `{text}` | the client's answers → a review in their voice (AI); 503 when AI is off, and the page drafts locally |
| POST | `/analytics/collect/` | `null` (202) | page-view report from the site's tracker; JSON or `text/plain` (sendBeacon); idempotent per `view_id`; bots dropped; rate-limited |

Media fields are absolute URLs. Internal link fields are locale-free paths (see *Links*).

### Language

Every endpoint resolves the response language the same way:

1. `?lang=en` / `?lang=ar` — explicit; any other value → **400 `UNSUPPORTED_LANGUAGE`**
2. the `Accept-Language` header — first supported language
3. English

The resolved language is returned in `Content-Language` (and `X-Content-Direction:
ltr|rtl`), and the response varies on `Accept-Language`. Content, our messages and DRF's
field-validation messages all follow it.

**Fallback policy:** a translated field left empty in Arabic is served in English; one
left empty in English is served in Arabic. The API never returns an empty string for
content that exists in the other language. Client names and locations are proper nouns and
are not translated.

### The response envelope

**Every** response the application controls — success or error, any endpoint, any status
— has exactly these six keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `success` | boolean | `true` for 2xx |
| `message` | string | Human-readable, localised, safe to show |
| `code` | string | Stable machine-readable code (below) — branch on this |
| `data` | any \| null | The payload; `null` on errors |
| `errors` | object \| null | `{field: [messages]}` on validation errors (`non_field_errors` for the rest) |
| `meta` | object \| null | `pagination` on lists, `retry_after` on 429, `request_id` on 5xx |

Every response also carries an `X-Request-ID` header (an inbound well-formed
`X-Request-ID` is honoured). The same id prefixes the server's log lines for that request,
so a user-reported reference leads straight to the traceback.

Success — `GET /api/v1/pages/our-team/?lang=ar` (abridged):

```json
{
  "success": true,
  "message": "تم جلب المحتوى بنجاح.",
  "code": "CONTENT_RETRIEVED",
  "data": {
    "slug": "our-team",
    "template": "standard",
    "title": "فريق العمل",
    "breadcrumb_parent": "من نحن",
    "header_image": "http://localhost:8000/media/pages/slider_01-e4d564f8.jpg",
    "blocks": [{ "kind": "intro", "eyebrow": "فريق العمل", "heading": "…", "body": "…" }]
  },
  "errors": null,
  "meta": null
}
```

Paginated list — `GET /api/v1/pages/?page_size=2`:

```json
{
  "success": true,
  "message": "Content retrieved successfully.",
  "code": "CONTENT_LIST_RETRIEVED",
  "data": [
    { "slug": "about-company", "template": "standard", "title": "About Company", "updated_at": "2026-10-14T12:39:50+03:00" },
    { "slug": "background-capabilities", "template": "standard", "title": "Background & Capabilities", "updated_at": "2026-10-14T12:39:50+03:00" }
  ],
  "errors": null,
  "meta": {
    "pagination": {
      "count": 16, "page": 1, "page_size": 2, "total_pages": 8,
      "next": "http://localhost:8000/api/v1/pages/?page=2&page_size=2", "previous": null
    }
  }
}
```

Created — `POST /api/v1/enquiries/` → **201**:

```json
{
  "success": true,
  "message": "Thank you — your message has been received. We will be in touch soon.",
  "code": "ENQUIRY_CREATED",
  "data": { "reference": "ENQ-000001", "created_at": "2026-10-14T12:41:16+03:00" },
  "errors": null,
  "meta": null
}
```

Validation error — `POST /api/v1/enquiries/?lang=ar` with `{"email": "bad"}` → **400**:

```json
{
  "success": false,
  "message": "البيانات المُرسلة غير صحيحة.",
  "code": "VALIDATION_ERROR",
  "data": null,
  "errors": {
    "full_name": ["هذا الحقل مطلوب."],
    "email": ["يرجى إدخال عنوان بريد إلكتروني صحيح."],
    "message": ["هذا الحقل مطلوب."]
  },
  "meta": null
}
```

Not found → **404**:

```json
{ "success": false, "message": "The requested resource was not found.", "code": "RESOURCE_NOT_FOUND", "data": null, "errors": null, "meta": null }
```

Unexpected failure → **500** (nothing about the cause is exposed):

```json
{ "success": false, "message": "An unexpected error occurred.", "code": "INTERNAL_SERVER_ERROR", "data": null, "errors": null, "meta": { "request_id": "dc2624c06a234b578b6d3068ec4ffc80" } }
```

### Application codes

| Code | HTTP | When |
| --- | --- | --- |
| `CONTENT_RETRIEVED` | 200 | Single object / composed payload |
| `CONTENT_LIST_RETRIEVED` | 200 | List (paginated) |
| `HEALTH_OK` | 200 | `/health/` |
| `ENQUIRY_CREATED` | 201 | Enquiry stored |
| `REVIEW_CREATED` | 201 | Client review stored |
| `REVIEW_DRAFTED` | 200 | AI review draft returned |
| `ANALYTICS_EVENT_ACCEPTED` | 202 | Page-view report accepted (also for dropped bot traffic) |
| `VALIDATION_ERROR` | 400 | Field validation failed — see `errors` |
| `MALFORMED_REQUEST` | 400 | Body is not valid JSON |
| `UNSUPPORTED_LANGUAGE` | 400 | `?lang=` is not `en`/`ar` |
| `AUTHENTICATION_REQUIRED` | 401 | (no public endpoint requires auth today) |
| `AUTHENTICATION_FAILED` | 401 | Bad credentials |
| `PERMISSION_DENIED` | 403 | |
| `RESOURCE_NOT_FOUND` | 404 | Unknown/unpublished resource, unknown `/api/` path, page out of range |
| `METHOD_NOT_ALLOWED` | 405 | |
| `NOT_ACCEPTABLE` | 406 | |
| `RESOURCE_CONFLICT` | 409 | Conflicting state (database integrity) |
| `DUPLICATE_ENQUIRY` | 409 | Same message from the same e-mail inside the window |
| `DUPLICATE_REVIEW` | 409 | Same review text from the same shop inside the window |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Body not JSON |
| `BUSINESS_RULE_VIOLATION` | 422 | Well-formed request breaking a domain rule |
| `RATE_LIMIT_EXCEEDED` | 429 | `meta.retry_after` + `Retry-After` header |
| `INTERNAL_SERVER_ERROR` | 500 | `meta.request_id` |
| `EXTERNAL_SERVICE_ERROR` | 502 | A dependency (e.g. mail server) failed |
| `SERVICE_UNAVAILABLE` | 503 | Database unreachable |

Codes are part of the contract: they are never renamed or reused. Messages may be reworded.

---

## Architecture

**Layers.** Views handle HTTP only — they call a *selector* (read queries,
`selectors.py`) or a *service* (business rules, `services.py`), serialise, and return
through `ApiResponse`. No view builds JSON by hand or catches exceptions. Models carry
constraints and model-level invariants; serializers validate request fields; services
enforce cross-record rules inside transactions.

**One response path.** `config/api_responses.py` is the only code that builds the
envelope. `config/api_exceptions.py` defines the application exceptions
(`ApplicationException` → `BusinessRuleException`, `ResourceNotFoundException`,
`ResourceConflictException`, `PermissionDeniedException`, `ExternalServiceException`,
`ServiceUnavailableException`) and the global `EXCEPTION_HANDLER`, which also translates
`Http404`/`ObjectDoesNotExist`, Django `PermissionDenied`/`ValidationError`,
`IntegrityError` (→ 409, without the SQL) and `OperationalError` (→ 503), and turns
anything unrecognised into a logged, generic 500. Outside DRF, a catch-all `/api/` route,
`ApiExceptionMiddleware` and `handler404/500` keep even unrouted or non-DRF failures in the
envelope, while the admin keeps its HTML pages.

**Design patterns, where they earn their place:**

- **Strategy + registry** — `apps/pages/blocks.py`: each block type validates and
  serialises itself; adding a type is one decorated class (open/closed).
- **Chain of responsibility** — `apps/core/i18n.py`: language resolvers tried in order.
- **Observer** — `apps/core/cache.py`: content models' save/delete signals bump a cache
  version after commit, invalidating every cached API payload at once.
- **Facade** — `apps/home/composer.py` assembles the home payload from five apps.
- **Adapter + dependency injection** — `apps/enquiries/notifiers.py`:
  `EnquiryService` depends on an `EnquiryNotifier` protocol; the e-mail adapter is chosen in
  settings and injected, and tests pass a fake.
- **Template method** — `apps/core/views.py`: base views own caching and the envelope;
  subclasses supply only the query or `build()`.

**Data integrity.** Database constraints back the important rules: singletons are
enforced with a check constraint, menu children must have links and cannot parent
themselves, a figure is a number *or* a text value, a region pin has both coordinates or
neither, only one testimonial can be featured, comparison cells are unique per row/column.
Lookups referenced by clients and blocks use `PROTECT`, so deleting a region in use, or a
table a page shows, is refused rather than cascading.

**Performance.** Every list and composed payload is built with `select_related` /
`prefetch_related` (the 367-client list is 3 queries), indexed on the filter columns, and
cached per language/query/host with signal-driven invalidation.

---

## Testing

```bash
pytest                 # 199 tests against PostgreSQL (test DB created automatically)
pytest --create-db     # after adding migrations (the test DB is reused between runs)
ruff check .
python manage.py spectacular --validate --fail-on-warn --file /dev/null   # schema check
```

The test database is migrated and loaded with the real seed content once per session.

| Area | File |
| --- | --- |
| Envelope on **every** endpoint in both languages; a guard that fails when a new route is not added to the sweep | `tests/test_api_contract.py` |
| Exception normalisation: 401/403/404/409/422/429/500/502/503, no leaked detail, request-id ↔ log correlation, localised errors | `tests/test_exception_handling.py` |
| Language resolution chain, Accept-Language, Arabic↔English fallback | `tests/test_i18n.py` |
| Site payload, navigation constraints, link validation, singleton | `tests/test_site.py` |
| Pages, every block kind's shape, block validation, unpublished/hidden content | `tests/test_pages.py` |
| Home sections, constraints, clients filters/ordering/pagination, taxonomy, events, partners | `tests/test_home_and_collections.py` |
| Enquiry service (no HTTP), notifier adapter, 201/400/409/415/429, honeypot | `tests/test_enquiries.py` |
| Upload validation (fake images, unsafe SVG, size), media URLs, cache invalidation | `tests/test_media_and_cache.py` |
| Every admin page renders, RTL inputs, admin edit → API, OpenAPI validity, seed idempotency | `tests/test_admin_schema_seed.py` |
| Visit analytics: UA/bot classification, ordered flows, monotonic durations, beacon bodies, path scrubbing, reports, dashboard/admin, retention | `tests/test_analytics.py` |

`tests/contract.py::assert_envelope` is the reusable contract assertion — use it in tests
for any new endpoint.

---

## Deployment

### Database

PostgreSQL with a dedicated user:

```sql
CREATE USER shs_user WITH PASSWORD '…';
CREATE DATABASE shs_backend OWNER shs_user;
```

Set `DATABASE_URL=postgres://shs_user:…@db-host:5432/shs_backend`. Back it up with
`pg_dump` on a schedule — together with the media folder it is the whole CMS.

### Application server (Linux)

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod   # also the wsgi default
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_content        # first deploy only
python manage.py index_media         # once, so existing media is de-duplicated against
# cron/systemd timer, daily: python manage.py prune_analytics
# optional, every few minutes, alert on non-zero exit: python manage.py system_status
python manage.py createsuperuser     # first deploy only
gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
```

Run gunicorn under systemd (or a container) behind nginx/Apache with HTTPS. Production
settings turn on HTTPS redirect, HSTS, secure cookies and JSON logs. Required env in
production: `DJANGO_SECRET_KEY`, `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS` (the website), `CSRF_TRUSTED_ORIGINS` (the admin's HTTPS origin),
`MEDIA_PUBLIC_BASE_URL`, `NUM_PROXIES`, SMTP settings, and ideally `CACHE_URL` (Redis —
`pip install redis`) so the cache and rate limits are shared across workers.

### Docker

`compose.yml` runs three containers: `db` (PostgreSQL), `web` (gunicorn) and `scheduler`.

```bash
docker compose up -d --build        # first deploy and every update
docker compose exec web python manage.py createsuperuser      # first deploy only
docker compose exec web python manage.py seed_content         # first deploy only
docker compose exec web python manage.py system_status        # full health report
```

On every start `web` applies migrations, indexes existing media for upload
de-duplication the first time (`index_media --if-empty`), then starts gunicorn. Its
`HEALTHCHECK` (`scripts/healthcheck.py`) calls `/api/v1/health/` every 30 s, so
`docker compose ps` shows `healthy` or `unhealthy`. `scheduler` runs `prune_analytics`
once a day. Files set aside by the media clean-up go to the `media_trash` volume, outside
`./media`, so nginx never serves them.

### Media

Uploads go to `DJANGO_MEDIA_ROOT`. Serve that folder directly from the web server at
`/media/` (it is not served by Django when `DEBUG` is off), e.g. nginx:

```nginx
location /media/.trash/ { deny all; }   # files set aside by the media clean-up
location /media/ { alias /var/www/shs/media/; expires 30d; add_header X-Content-Type-Options nosniff; }
location /static/ { alias /var/www/shs/backend/staticfiles/; }
location / { proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }
```

Upload file names are unique, so media can be cached aggressively or put behind a CDN; set
`MEDIA_PUBLIC_BASE_URL` to the CDN origin. For object storage (S3 and compatible), install
`django-storages` and point `STORAGES["default"]` at it — no model changes are needed, but
upload de-duplication (`apps.core.storage`) is built on the file-system storage and would
need porting to the new backend.

### Frontend

See `../README.md` and `../shs_frontend/DEPLOY-BLUEHOST.md`. In short: build with
`NEXT_PUBLIC_API_URL` pointing at this API, and either run `next start` (content refreshes
automatically) or upload the static export (rebuild after content changes).

---

## Known limitations

- **Static hosting needs rebuilds.** A static-export frontend cannot pick up CMS edits by
  itself; it must be rebuilt and re-uploaded. Node hosting avoids this.
- **New pages need a frontend build** on any hosting, because routes are generated at build
  time (`dynamicParams = false`, required for the static export).
- **Arabic copy is machine-authored** (carried over from the original site) and should be
  reviewed by a native speaker; it is all editable in the admin.
- **The local-memory cache is per process.** With several workers, configure Redis
  (`CACHE_URL`) so edits invalidate every worker's cache and rate limits are shared.
- **Interface strings** (button labels, aria text, form messages) live with the frontend
  code in `shs_frontend/content/ui.ts`, like a gettext catalogue — they are not
  admin-editable. Everything that is content is.
