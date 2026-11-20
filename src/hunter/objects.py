"""Conservative object extraction from source-backed news.

A candidate is an object mention, not verified buying demand or a licensing grant.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup

KINDS = {
    "figurine": "figurine", "figure": "figurine", "statue": "statue",
    "mascot": "mascot", "replica": "replica", "mask": "mask",
    "plush": "plush", "badge": "badge", "pin": "pin", "emblem": "emblem",
    "keychain": "keychain", "stand": "stand", "miniature": "miniature",
    "sculpture": "sculpture", "amiibo": "figurine", "lamp": "lamp",
    "bookend": "bookend", "ornament": "ornament", "medallion": "medallion",
    "フィギュア": "figurine", "マスコット": "mascot",
    "ぬいぐるみ": "plush", "アミーボ": "figurine",
    "手办": "figurine", "模型": "miniature", "피규어": "figurine",
}
EN_TERMS = [key for key in KINDS if key.isascii()]
NOUNS = "|".join(re.escape(x) for x in sorted(EN_TERMS, key=len, reverse=True))
EN_PHRASE = re.compile(
    rf"\b(?:[a-zA-Z][a-zA-Z0-9'’\-]*\s+){{1,5}}(?:{NOUNS})s?\b",
    re.I,
)
JP_QUOTE = re.compile(r"[「『]([^」』]{2,70})[」』]")
JP_KEYWORDS = re.compile(
    r"amiibo|アミーボ|フィギュア|マスコット|ぬいぐるみ|手办|模型|피규어", re.I,
)
JP_COMPOUND = re.compile(
    r"([\u3040-\u30ff\u3400-\u9fffA-Za-z0-9・ー&＋\-\s]{2,36})"
    r"(フィギュア|マスコット|ぬいぐるみ|手办|模型|피규어)"
)
GENERIC = set(KINDS)
SIGNAL = re.compile(
    r"collector.?s? edition|limited edition|exclusive|bundle|"
    r"merchandise|figurine|statue|mascot|replica|plush|amiibo|"
    r"badge|keychain|medallion|ornament|bookend|"
    r"フィギュア|マスコット|ぬいぐるみ|手办|模型|피규어|"
    r"限定特典|数量限定|グッズ", re.I,
)
DEMAND_PATTERNS = {
    "want_to_own": r"\b(i want (?:one|this|it)|i need this|would buy|take my money)\b",
    "separate_purchase": r"\b(sold separately|only want the (?:figure|statue)|buy it separately)\b",
    "price_objection": r"\b(too expensive|cheaper alternative|why so expensive)\b",
    "availability": r"\b(where can i buy|sold out everywhere|where to get)\b",
    "direct_miniature": r"\b(someone should make|wish they sold a miniature|need a figurine)\b",
}


def plain_text(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


# Reject partial sentence windows before treating an English phrase as a product.
# Keep the original matched span as auditable evidence in each candidate.
_DISCARD_PREFIX = {
    "the", "a", "an", "all", "any", "some", "many", "more", "new",
    "this", "that", "these", "those", "its", "their", "his", "her",
    "since", "because", "for", "from", "in", "on", "at", "to", "as",
    "of", "by", "with", "without", "and", "or", "but", "also",
    "is", "are", "was", "were", "be", "been", "will", "would",
    "can", "could", "may", "might", "than", "like", "other",
}
_CLAUSE_VERBS = {
    "includes", "include", "features", "feature", "offers", "offer",
    "contains", "contain", "shows", "show", "reveals", "reveal",
    "appears", "appear", "becomes", "become", "helps", "help",
    "using", "used", "seen", "find", "found", "called",
}
_WEAK_LABEL = {"prize", "new", "official", "other", "generic", "many"}


def english_entity_name(window: str) -> str:
    """Return a source-backed noun phrase, or '' for a dangling clause.

    This is a high-precision *filter*, not semantic entity recognition. It
    deliberately abstains rather than inventing a cleaned-up product name.
    """
    words = window.split()
    if not words:
        return ""
    # Phrases like 'all Sanrio mascots' refer to a broad collection, not an
    # independently identified product. They remain in the source article.
    if words[0].casefold() in {"all", "every", "various"}:
        return ""
    for i, word in enumerate(words[:-1]):
        if word.casefold() in _CLAUSE_VERBS:
            words = words[i + 1:]
    while words and (words[0].casefold() in _DISCARD_PREFIX or
                     not words[0][0].isupper()):
        words.pop(0)
    if len(words) < 2:
        return ""
    # Explanatory clauses and comparative references are not product names.
    if any(word.casefold() in {"like", "other", "such", "as", "because", "since"}
           for word in words[:-1]):
        return ""
    if any(word.casefold() in _CLAUSE_VERBS for word in words[:-1]):
        return ""
    if len(words) == 2 and words[0].casefold() in _WEAK_LABEL:
        return ""
    return " ".join(words)


def extract_objects(text: str) -> list[dict]:
    clean = plain_text(text)[:16000]
    if not SIGNAL.search(clean):
        return []
    found: list[dict] = []
    seen: set[str] = set()

    def add(name: str, kind: str, index: int, confidence: float,
            source_span: str | None = None) -> None:
        name = re.sub(r"\s+", " ", name).strip(" ,.:;–-")
        if len(name) < 5 or len(name) > 100 or name.casefold() in GENERIC:
            return
        if name.casefold() in seen:
            return
        seen.add(name.casefold())
        found.append({
            "name": name, "kind": kind,
            "source_span": source_span or name,
            "excerpt": clean[max(0, index-85):index+max(100, len(name)+60)][:280],
            "extraction_method": "named_object_in_source",
            "extraction_confidence": confidence,
        })

    # Handles paired quoted figures like Nintendo's Japanese amiibo announcements.
    for keyword in JP_KEYWORDS.finditer(clean):
        prefix = clean[max(0, keyword.start()-125):keyword.start()]
        # Do not associate a character in an earlier headline with an
        # unrelated "amiibo" mention (e.g. gift wrapping *can hold* amiibo).
        # Only quotes adjacent to the merchandise noun in the SAME sentence
        # are an object claim; otherwise they are background context.
        clause = re.split(r"[。！？.!?]", prefix)[-1]
        quoted_names = list(JP_QUOTE.finditer(clause))
        if not quoted_names:
            continue
        gap = clause[quoted_names[-1].end():]
        if not re.fullmatch(r"[\sの、と、・&＋-]{0,8}", gap):
            continue
        for quoted in quoted_names[-3:]:
            name = quoted.group(1).strip()
            if len(name) > 55 or any(x in name for x in ("オンライン", "ニュース", "発売日")):
                continue
            add(f"{name} {keyword.group(0)}", "figurine", keyword.start(), 0.72)

    for match in EN_PHRASE.finditer(clean):
        raw_span = match.group(0).strip()
        # 'Aurora Mascot figurine' can stop at 'Mascot' because both words
        # are object nouns. Keep the complete adjacent noun compound.
        extension = re.match(
            rf"\s+(?:{NOUNS})s?\b", clean[match.end():], re.I
        )
        if extension:
            raw_span += extension.group(0)
        name = english_entity_name(raw_span)
        if not name:
            continue
        noun = name.split()[-1].lower().rstrip("s")
        add(name, KINDS.get(noun, "object"), match.start(), 0.60,
            source_span=raw_span)

    for match in JP_COMPOUND.finditer(clean):
        add(match.group(0), KINDS.get(match.group(2), "figurine"),
            match.start(), 0.55)

    return consolidate_objects(found, clean)[:25]


OBJECT_SUFFIX = re.compile(
    r"(?:\s*(?:amiibo|figurine|figure|statue|mascot|plush|"
    r"miniature|フィギュア|マスコット|ぬいぐるみ|手办|模型|피규어))\s*$",
    re.I,
)
GENERIC_JAPANESE = re.compile(
    r"(?:シリーズ|育成可能|対応可能|追加機能|予約受付|最新情報|数量限定特典)"
)


def object_core(name: str) -> str:
    base = OBJECT_SUFFIX.sub("", name).strip()
    return re.sub(r"[\s\-_・]+", "", base).casefold()


def consolidate_objects(items: list[dict], text: str) -> list[dict]:
    """Merge same-article aliases while preserving distinct named components.

    Names of a *series* or generic adjective are not an individual physical
    product. Quote-backed long names are prioritized over short fragments.
    """
    explicit = set(
        m.group(1).strip()
        for m in JP_QUOTE.finditer(text[:240])
        if len(m.group(1)) >= 4
    )
    candidates = []
    for item in items:
        core = object_core(item["name"])
        if len(core) < 3 or GENERIC_JAPANESE.search(core):
            continue
        item = dict(item)
        item.setdefault("aliases", [])
        item["_priority"] = (
            10 if any(q == core or object_core(q) == core for q in explicit)
            else 0
        )
        candidates.append(item)
    candidates.sort(
        key=lambda x: (x["_priority"], x["extraction_confidence"],
                       len(object_core(x["name"]))),
        reverse=True,
    )
    accepted = []
    for candidate in candidates:
        core = object_core(candidate["name"])
        duplicate = None
        for existing in accepted:
            current = object_core(existing["name"])
            if (core == current or
                (len(core) >= 4 and len(current) >= 4 and
                 (core in current or current in core))):
                duplicate = existing
                break
        if duplicate is not None:
            if candidate["name"] != duplicate["name"]:
                duplicate["aliases"].append(candidate["name"])
        else:
            accepted.append(candidate)
    for item in accepted:
        item.pop("_priority", None)
    return accepted


def detect_demand(text: str) -> list[str]:
    clean = plain_text(text).casefold()
    return [
        kind for kind, expression in DEMAND_PATTERNS.items()
        if re.search(expression, clean, re.I)
    ]
