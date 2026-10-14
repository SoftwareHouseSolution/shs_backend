"""Loads seed/content.json — the website's original bilingual content — into the database.

Idempotent: every record is matched on a natural key (slug, key, order within a parent)
and updated in place, so re-running after editing the JSON refreshes the content without
duplicating it. Files are copied into media storage only when the field is empty, unless
`replace_media` is set, so re-seeding never churns uploaded files.

Translated values arrive as {"en": ..., "ar": ...} and are written to the `<field>_en` /
`<field>_ar` columns directly.
"""

from pathlib import Path
from typing import Any

from django.core.files import File
from django.db import models

from apps.clients.models import BusinessType, Client, Region, Sector
from apps.content.models import ComparisonCell, ComparisonColumn, ComparisonRow, ComparisonTable, Partner, Testimonial
from apps.events.models import Event, EventPhoto
from apps.home.models import HeroSlide, HomePage, HomeSectionItem, HomeStat
from apps.pages.models import BlockItem, Page, PageBlock
from apps.site_config.models import Badge, FooterColumn, NavigationItem, SiteSettings, SocialLink


def tx(**fields: Any) -> dict:
    """{"title": {"en": "A", "ar": "ب"}} → {"title_en": "A", "title_ar": "ب"}. None → ''."""
    out = {}
    for name, value in fields.items():
        value = value or {}
        out[f"{name}_en"] = value.get("en") or ""
        out[f"{name}_ar"] = value.get("ar") or ""
    return out


class ContentSeeder:
    def __init__(self, data: dict, media_dir: Path, *, replace_media: bool = False, log=print):
        self.data = data
        self.media_dir = Path(media_dir)
        self.replace_media = replace_media
        self.log = log
        self.files_copied = 0

    # ── helpers ──────────────────────────────────────────────────────────────────────

    def attach(self, obj: models.Model, field: str, rel_path: str | None) -> None:
        if not rel_path:
            return
        current = getattr(obj, field)
        if current and current.name and not self.replace_media:
            return
        source = self.media_dir / rel_path
        if not source.exists():
            raise FileNotFoundError(f"Seed media missing: {source}")
        with source.open("rb") as fh:
            current.save(source.name, File(fh), save=False)
        self.files_copied += 1

    @staticmethod
    def upsert(model: type[models.Model], lookup: dict, values: dict) -> models.Model:
        obj = model.objects.filter(**lookup).first() or model(**lookup)
        for key, value in values.items():
            setattr(obj, key, value)
        return obj

    # ── sections ─────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.site()
        self.navigation()
        tables = self.comparison_tables()
        self.testimonials()
        self.partners()
        events = self.events()
        self.clients()
        self.home(tables)
        self.pages(tables, events)
        self.log(f"Seed complete ({self.files_copied} files copied).")

    def site(self) -> None:
        s = self.data["site"]
        obj = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first() or SiteSettings()
        for key in ("short_name", "since_year", "phone_display", "phone_link", "whatsapp_url", "sales_email",
                    "careers_email", "primary_cta_url", "copyright_year"):
            setattr(obj, key, s[key])
        for key, value in tx(
            site_name=s["site_name"], address=s["address"], primary_cta_label=s["primary_cta_label"],
            footer_blurb=s["footer_blurb"], rights_text=s["rights_text"],
            contact_heading=s["contact_heading"], contact_body=s["contact_body"], contact_cta_label=s["contact_cta_label"],
            default_meta_title=s["default_meta_title"], default_meta_description=s["default_meta_description"],
        ).items():
            setattr(obj, key, value)
        obj.save()

        for item in self.data["social"]:
            self.upsert(SocialLink, {"platform": item["platform"]}, {
                "url": item["url"], "is_placeholder": item["is_placeholder"], "order": item["order"],
            }).save()

        for i, badge in enumerate(self.data.get("badges", [])):
            obj = self.upsert(Badge, {"order": i}, tx(alt=badge["alt"]) | {"url": badge.get("url", "")})
            self.attach(obj, "image", badge["image"])
            obj.save()
        self.log("Site settings, social links and badges loaded.")

    def navigation(self) -> None:
        for entry in self.data["navigation"]:
            parent = self.upsert(NavigationItem, {"key": entry["key"]}, {
                **tx(label=entry["label"]), "url": entry["url"], "order": entry["order"], "parent": None,
            })
            parent.full_clean()
            parent.save()
            for child in entry["children"]:
                obj = self.upsert(NavigationItem, {"key": child["key"]}, {
                    **tx(label=child["label"]), "url": child["url"], "order": child["order"], "parent": parent,
                })
                obj.full_clean()
                obj.save()

        for col in self.data["footer_columns"]:
            obj = self.upsert(FooterColumn, {"key": col["key"]}, {**tx(title=col["title"]), "order": col["order"]})
            obj.save()
            obj.groups.set(NavigationItem.objects.filter(key__in=col["groups"]))
        self.log(f"Navigation loaded ({NavigationItem.objects.count()} items).")

    def comparison_tables(self) -> dict[str, ComparisonTable]:
        tables = {}
        for t in self.data["comparison_tables"]:
            table = self.upsert(ComparisonTable, {"key": t["key"]}, {"name": t["title"]})
            table.save()
            columns = []
            for col in t["columns"]:
                c = self.upsert(ComparisonColumn, {"table": table, "order": col["order"]}, {
                    **tx(label=col["label"]), "highlight": col["highlight"],
                })
                c.save()
                columns.append(c)
            for row in t["rows"]:
                r = self.upsert(ComparisonRow, {"table": table, "order": row["order"]}, {})
                r.save()
                for column, cell in zip(columns, row["cells"], strict=True):
                    self.upsert(ComparisonCell, {"row": r, "column": column}, {
                        **tx(text=cell["text"]), "ok": cell["ok"],
                    }).save()
            tables[t["key"]] = table
        self.log(f"{len(tables)} comparison tables loaded.")
        return tables

    def testimonials(self) -> None:
        for t in self.data["testimonials"]:
            obj = self.upsert(Testimonial, {"order": t["order"]}, {
                **tx(quote=t["quote"], author_name=t["author_name"], author_company=t["author_company"]),
                "is_featured": t["is_featured"],
            })
            self.attach(obj, "avatar", t.get("avatar"))
            obj.save()

    def partners(self) -> None:
        for p in self.data["partners"]:
            obj = self.upsert(Partner, {"name": p["name"], "category": p["category"]}, {"order": p["order"]})
            self.attach(obj, "logo", p["logo"])
            obj.save()

    def events(self) -> dict[str, Event]:
        events = {}
        for e in self.data["events"]:
            event = self.upsert(Event, {"slug": e["slug"]}, {
                **tx(title=e["title"], body=e["body"]), "year": e["year"], "order": e["order"],
            })
            event.save()
            for photo in e["photos"]:
                p = self.upsert(EventPhoto, {"event": event, "order": photo["order"]}, tx(alt=photo["alt"]))
                self.attach(p, "image", photo["image"])
                p.save()
            events[e["slug"]] = event
        self.log(f"{len(events)} events loaded.")
        return events

    def clients(self) -> None:
        regions = {}
        for r in self.data["regions"]:
            obj = self.upsert(Region, {"key": r["key"]}, {
                **tx(name=r["name"]), "order": r["order"],
                "map_latitude": r["map_latitude"], "map_longitude": r["map_longitude"],
            })
            obj.save()
            regions[r["key"]] = obj
        sectors = {}
        for s in self.data["sectors"]:
            obj = self.upsert(Sector, {"key": s["key"]}, {**tx(name=s["name"]), "order": s["order"]})
            obj.save()
            sectors[s["key"]] = obj
        types = {}
        for b in self.data["business_types"]:
            obj = self.upsert(BusinessType, {"key": b["key"]}, {**tx(name=b["name"]), "order": b["order"]})
            obj.save()
            types[b["key"]] = obj

        for c in self.data["clients"]:
            obj = self.upsert(Client, {"slug": c["slug"]}, {
                "name": c["name"],
                "location": c["location"],
                "region": regions[c["region"]],
                "sector": sectors[c["sector"]],
                "home_highlight_order": c["home_highlight_order"],
                "show_in_home_strip": c["show_in_home_strip"],
                "featured_order": c["featured_order"],
            })
            self.attach(obj, "logo", c["logo"])
            obj.save()
            obj.business_types.set([types[k] for k in c["business_types"]])
        self.log(f"{len(self.data['clients'])} clients loaded.")

    def home(self, tables: dict[str, ComparisonTable]) -> None:
        h = self.data["home"]
        home = HomePage.objects.filter(pk=HomePage.SINGLETON_PK).first() or HomePage()
        translated = {k: v for k, v in h.items() if isinstance(v, dict) and set(v) == {"en", "ar"}}
        for key, value in tx(**translated).items():
            setattr(home, key, value)
        for key in ("proof_cta_url", "events_cta_url", "band_cta_url"):
            setattr(home, key, h[key])
        home.specs_table = tables.get(h["specs_table"])
        self.attach(home, "services_image", h["services_image"])
        self.attach(home, "big_picture_image", h["big_picture_image"])
        home.save()

        for slide in self.data["hero_slides"]:
            obj = self.upsert(HeroSlide, {"home": home, "order": slide["order"]}, {
                **tx(eyebrow=slide["eyebrow"], title=slide["title"], body=slide["body"], cta_label=slide["cta_label"]),
                "cta_url": slide["cta_url"],
            })
            self.attach(obj, "image", slide["image"])
            self.attach(obj, "video_webm", slide["video_webm"])
            self.attach(obj, "video_mp4", slide["video_mp4"])
            obj.save()

        for stat in self.data["stats"]:
            self.upsert(HomeStat, {"home": home, "order": stat["order"]}, {
                **tx(label=stat["label"]), "value": stat["value"], "prefix": stat["prefix"],
                "suffix": stat["suffix"], "text": stat["text"],
            }).save()

        for section, items in h["section_items"].items():
            for item in items:
                self.upsert(HomeSectionItem, {"home": home, "section": section, "order": item["order"]}, {
                    **tx(title=item["title"], body=item["body"]), "number": item["number"],
                }).save()
        self.log("Home page loaded.")

    def pages(self, tables: dict[str, ComparisonTable], events: dict[str, Event]) -> None:
        for p in self.data["pages"]:
            page = self.upsert(Page, {"slug": p["slug"]}, {
                **tx(title=p["title"], eyebrow=p["eyebrow"], lede=p["lede"], meta_description=p["meta_description"]),
                "template": p["template"],
                "order": p["order"],
            })
            self.attach(page, "header_image", p["header_image"])
            for field in ("video_desktop", "video_mobile", "video_poster_desktop", "video_poster_mobile"):
                self.attach(page, field, p.get(field))
            page.save()

            kept = []
            for b in p["blocks"]:
                block = self.upsert(PageBlock, {"page": page, "order": b["order"]}, {
                    "kind": b["kind"],
                    **tx(eyebrow=b.get("eyebrow"), heading=b.get("heading"), body=b.get("body"), label=b.get("label")),
                    "url": b.get("url", ""),
                    "comparison_table": tables.get(b.get("comparison_table")),
                    "event": events.get(b.get("event")),
                    "partner_category": b.get("partner_category", ""),
                })
                block.full_clean()
                block.save()
                kept.append(block.pk)
                for item in b.get("items", []):
                    obj = self.upsert(BlockItem, {"block": block, "order": item["order"]}, {
                        **tx(title=item["title"], body=item.get("body")), "number": item.get("number", ""),
                    })
                    self.attach(obj, "image", item.get("image"))
                    obj.save()
            page.blocks.exclude(pk__in=kept).delete()
        self.log(f"{len(self.data['pages'])} pages loaded.")
