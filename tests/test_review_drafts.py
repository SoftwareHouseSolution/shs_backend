"""AI review drafts: POST /api/v1/reviews/draft/ (apps.reviews.drafting). The real API is
never called — a fake client stands in for anthropic.Anthropic."""

import random
from types import SimpleNamespace

import pytest

from apps.core.codes import ResponseCode
from apps.reviews import drafting
from apps.reviews.drafting import DraftRequest, DraftUnavailable, build_prompt, draft
from tests.contract import assert_envelope

URL = "/api/v1/reviews/draft/"
ANSWERS = {
    "author_name": "الحاج طارق",
    "shop_name": "مجوهرات النور",
    "governorate": "القاهرة",
    "area": "الصاغة – الموسكي",
    "duration": "5-10",
    "support": "good",
    "updates": "low",
    "benefits": ["inventory", "invoices"],
    "business_type": "wholesale",
    "branches": "2-3",
    "previous_system": "paper",
    "comment": "التعامل محترم جداً",
}


class FakeClient:
    """Records the request and answers like the Messages API."""

    def __init__(self, text="بقالي سنين على البرنامج والجرد بقى أسهل بكتير.", stop_reason="end_turn", error=None):
        self.calls = []
        self._text, self._stop, self._error = text, stop_reason, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        blocks = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self._text)]
        return SimpleNamespace(content=blocks, stop_reason=self._stop, stop_details=None)


# ── The prompt ───────────────────────────────────────────────────────────────────────


def test_the_prompt_carries_this_clients_facts_and_own_words():
    prompt = build_prompt(DraftRequest(**ANSWERS), "ar", random.Random(1))
    for fact in ("الحاج طارق", "مجوهرات النور", "الصاغة – الموسكي, القاهرة", "التعامل محترم جداً"):
        assert fact in prompt
    assert "Wholesale" in prompt and "Paper ledgers" in prompt and "Needs improvement" in prompt
    assert "<answers>" in prompt and "Angle:" in prompt and "Egyptian" in prompt


def test_asking_again_tells_the_model_to_avoid_the_last_draft():
    prompt = build_prompt(DraftRequest(**ANSWERS, previous_draft="المسودة القديمة"), "ar", random.Random(1))
    assert "<earlier_draft>" in prompt and "المسودة القديمة" in prompt


def test_angles_vary_between_clients():
    angles = {build_prompt(DraftRequest(**ANSWERS), "ar", random.Random(seed)).split("Angle: ")[1][:30] for seed in range(30)}
    assert len(angles) > 3


def test_english_pages_ask_for_english():
    assert "plain, natural English" in build_prompt(DraftRequest(**ANSWERS), "en", random.Random(1))


# ── The call ─────────────────────────────────────────────────────────────────────────


def test_a_draft_uses_the_configured_model_with_fallbacks(settings):
    settings.REVIEW_AI_MODEL = "claude-opus-5-5"
    client = FakeClient(text="  «بقالي سنين على البرنامج والجرد بقى أسهل بكتير.»  ")
    text = draft(DraftRequest(**ANSWERS), language="ar", client=client)
    assert text == "بقالي سنين على البرنامج والجرد بقى أسهل بكتير."
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert call["betas"] == [drafting.FALLBACK_BETA] and call["output_config"] == {"effort": "low"}
    assert "<answers>" in call["messages"][0]["content"]


def test_a_refusal_is_unavailable():
    with pytest.raises(DraftUnavailable):
        draft(DraftRequest(**ANSWERS), language="ar", client=FakeClient(stop_reason="refusal"))


def test_an_empty_answer_is_unavailable():
    with pytest.raises(DraftUnavailable):
        draft(DraftRequest(**ANSWERS), language="ar", client=FakeClient(text="  "))


def test_an_api_error_is_unavailable():
    import anthropic
    import httpx2

    error = anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
    with pytest.raises(DraftUnavailable):
        draft(DraftRequest(**ANSWERS), language="ar", client=FakeClient(error=error))


def test_without_a_key_nothing_is_called():
    with pytest.raises(DraftUnavailable):
        draft(DraftRequest(**ANSWERS), language="ar")


# ── The endpoint ─────────────────────────────────────────────────────────────────────


def test_the_endpoint_returns_the_draft(api, monkeypatch):
    monkeypatch.setattr(drafting, "draft", lambda req, language: f"{req.shop_name} — {language} — {req.style}")
    body = assert_envelope(api.post(f"{URL}?lang=ar", {**ANSWERS, "style": "short"}, format="json"), status=200, code=ResponseCode.REVIEW_DRAFTED)
    assert body["data"]["text"] == "مجوهرات النور — ar — short"


def test_without_ai_the_endpoint_says_unavailable(api):
    assert_envelope(api.post(URL, ANSWERS, format="json"), status=503, code=ResponseCode.SERVICE_UNAVAILABLE)


def test_bad_answers_are_rejected(api):
    body = assert_envelope(api.post(URL, {**ANSWERS, "branches": "100"}, format="json"), status=400, code=ResponseCode.VALIDATION_ERROR)
    assert "branches" in body["errors"]


def test_drafts_are_rate_limited(api, monkeypatch):
    from rest_framework.throttling import SimpleRateThrottle

    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", {**SimpleRateThrottle.THROTTLE_RATES, "review_drafts": "1/hour"})
    monkeypatch.setattr(drafting, "draft", lambda req, language: "draft text long enough")
    assert api.post(URL, ANSWERS, format="json").status_code == 200
    assert_envelope(api.post(URL, ANSWERS, format="json"), status=429, code=ResponseCode.RATE_LIMIT_EXCEEDED)


# ── The review stores the new answers ────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_optional_answers_are_stored_with_the_review(api):
    from apps.reviews.models import Review

    payload = {**ANSWERS, "text": "بقالي أكتر من ٥ سنين شغال على برنامج سوفت وير هاوس، والدعم الفني ممتاز."}
    assert_envelope(api.post("/api/v1/reviews/", payload, format="json"), status=201, code=ResponseCode.REVIEW_CREATED)
    review = Review.objects.get()
    assert (review.business_type, review.branches, review.previous_system) == ("wholesale", "2-3", "paper")
