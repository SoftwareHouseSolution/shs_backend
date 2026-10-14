"""Language resolution for the API.

Precedence, applied identically on every endpoint:

    1. `?lang=` query parameter   — explicit; an unsupported value is a 400
    2. `Accept-Language` header   — best supported match; unsupported values are skipped
    3. settings.LANGUAGE_CODE     — English

Each step is a resolver with one method, so the chain can be reordered or extended (a
`X-Language` header, a cookie) without touching the middleware that runs it.
"""

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.http import HttpRequest
from django.utils.translation.trans_real import parse_accept_lang_header

LANG_QUERY_PARAM = "lang"


def supported_languages() -> tuple[str, ...]:
    return tuple(code for code, _ in settings.LANGUAGES)


def direction(language: str) -> str:
    return settings.LANGUAGE_DIRECTIONS.get(language, "ltr")


class UnsupportedLanguage(Exception):
    def __init__(self, requested: str):
        self.requested = requested
        super().__init__(requested)


@dataclass(frozen=True)
class Resolution:
    language: str
    source: str  # "query" | "header" | "default"


class LanguageResolver(Protocol):
    def resolve(self, request: HttpRequest) -> Resolution | None: ...


class QueryParamResolver:
    def resolve(self, request: HttpRequest) -> Resolution | None:
        raw = request.GET.get(LANG_QUERY_PARAM)
        if raw is None or raw == "":
            return None
        code = raw.strip().lower()
        if code not in supported_languages():
            raise UnsupportedLanguage(raw)
        return Resolution(code, "query")


class AcceptLanguageResolver:
    def resolve(self, request: HttpRequest) -> Resolution | None:
        header = request.headers.get("Accept-Language", "")
        supported = supported_languages()
        for lang, _q in parse_accept_lang_header(header):
            base = lang.split("-")[0].lower()
            if base in supported:
                return Resolution(base, "header")
        return None


class DefaultResolver:
    def resolve(self, request: HttpRequest) -> Resolution | None:
        return Resolution(settings.LANGUAGE_CODE, "default")


DEFAULT_CHAIN: tuple[LanguageResolver, ...] = (
    QueryParamResolver(),
    AcceptLanguageResolver(),
    DefaultResolver(),
)


def resolve_language(request: HttpRequest, chain=DEFAULT_CHAIN) -> Resolution:
    for resolver in chain:
        found = resolver.resolve(request)
        if found is not None:
            return found
    raise RuntimeError("Language resolver chain must end with a resolver that always answers.")
