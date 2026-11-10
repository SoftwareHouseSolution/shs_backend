"""import_clients: a dry run by default, add-only unless --update, never duplicates a shop."""

import io
import json

import pytest
from django.core.management import call_command
from PIL import Image

from apps.clients.models import Client, Region


def _logo(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (40, 20), (12, 34, 56)).save(path, "WEBP")


def _file(tmp_path, rows):
    for row in rows:
        _logo(tmp_path / row["logo"])
    (tmp_path / "clients.json").write_text(json.dumps(rows), encoding="utf-8")
    return str(tmp_path / "clients.json")


def _row(name, location="Cairo", region="greater-cairo", **extra):
    slug = name.lower().replace(" ", "-")
    return {
        "name": name,
        "location": location,
        "region": region,
        "sector": "jewellery",
        "business_types": ["retail"],
        "logo": f"logos/{slug}.webp",
        **extra,
    }


def _run(*args):
    out = io.StringIO()
    call_command("import_clients", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_a_dry_run_reports_and_writes_nothing(tmp_path):
    before = Client.objects.count()
    out = _run(_file(tmp_path, [_row("Brand New Jewels")]))
    assert "1 new" in out and "Brand New Jewels" in out and "Dry run" in out
    assert Client.objects.count() == before


@pytest.mark.django_db
def test_apply_adds_a_published_client_with_its_logo(tmp_path):
    _run(_file(tmp_path, [_row("Brand New Jewels", "Tanta", "delta-canal")]), "--apply")
    c = Client.objects.get(name="Brand New Jewels")
    assert (c.location, c.region.key, c.sector.key, c.is_published) == ("Tanta", "delta-canal", "jewellery", True)
    assert [t.key for t in c.business_types.all()] == ["retail"]
    assert c.logo.name.startswith("clients/brand-new-jewels")


@pytest.mark.django_db
def test_a_branch_with_a_taken_name_gets_a_numbered_slug(tmp_path):
    # A branch is the same name listed again at another address. Alone, a new address for a
    # known name is that client moving, which only --update applies.
    existing = Client.objects.exclude(location="").order_by("slug").first()
    rows = [_row(existing.name, existing.location, existing.region.key), _row(existing.name, "Somewhere Else Entirely")]
    rows[1]["logo"] = "logos/branch.webp"
    _run(_file(tmp_path, rows), "--apply")
    branch = Client.objects.exclude(pk=existing.pk).get(name=existing.name, location="Somewhere Else Entirely")
    assert branch.slug.startswith(existing.slug + "-")


@pytest.mark.django_db
def test_existing_clients_change_only_with_update(tmp_path):
    c = Client.objects.exclude(location="").first()
    path = _file(tmp_path, [_row(c.name, "A New Address", c.region.key)])
    out = _run(path, "--apply")
    assert "A New Address" in out
    c.refresh_from_db()
    assert c.location != "A New Address"
    _run(path, "--apply", "--update")
    c.refresh_from_db()
    assert c.location == "A New Address"


@pytest.mark.django_db
def test_a_blank_location_never_clears_one(tmp_path):
    c = Client.objects.exclude(location="").first()
    kept = c.location
    _run(_file(tmp_path, [_row(c.name, "", c.region.key)]), "--apply", "--update")
    c.refresh_from_db()
    assert c.location == kept


@pytest.mark.django_db
def test_the_same_shop_listed_twice_is_imported_once(tmp_path):
    rows = [_row("Twice Listed Gold", "Sagha"), _row("Twice Listed Gold", "Sagha")]
    out = _run(_file(tmp_path, rows), "--apply")
    assert "1 listed twice" in out
    assert Client.objects.filter(name="Twice Listed Gold").count() == 1


@pytest.mark.django_db
def test_a_name_with_its_location_glued_on_is_matched_not_duplicated(tmp_path):
    region = Region.objects.get(key="greater-cairo")
    glued = Client.objects.first()
    glued.name, glued.region = "Gluey Gold New", region
    glued.save()
    out = _run(_file(tmp_path, [_row("Gluey Gold", "New Cairo")]), "--apply", "--update")
    assert "0 new" in out
    glued.refresh_from_db()
    assert (glued.name, glued.location) == ("Gluey Gold", "New Cairo")


@pytest.mark.django_db
def test_a_row_without_a_logo_or_with_an_unknown_region_is_skipped(tmp_path):
    rows = [_row("No Picture Gold"), _row("Nowhere Gold", region="atlantis")]
    path = _file(tmp_path, rows)
    (tmp_path / rows[0]["logo"]).unlink()
    out = _run(path, "--apply")
    assert "2 skipped" in out and "no logo" in out and "unknown region 'atlantis'" in out
    assert not Client.objects.filter(name__in=["No Picture Gold", "Nowhere Gold"]).exists()
