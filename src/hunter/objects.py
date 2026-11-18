"""Conservative text-only object discovery. Vision and multilingual NER are V2."""
import re
from bs4 import BeautifulSoup

KINDS = {
    "figurine": "figurine", "figure": "figurine", "statue": "statue",
    "mascot": "mascot", "replica": "replica", "mask": "mask",
    "plush": "plush", "badge": "badge", "pin": "pin",
    "emblem": "emblem", "keychain": "keychain", "stand": "stand",
    "miniature": "miniature", "sculpture": "sculpture",
    "フィギュア": "figurine", "マスコット": "mascot", "ぬいぐるみ": "plush",
    "手办": "figurine", "模型": "miniature", "피규어": "figurine",
}
OBJECT_WORDS = "|".join(map(re.escape, sorted(KINDS, key=len, reverse=True)))
EN_PHRASE = re.compile(
    rf"\b(?:[a-zA-Z][a-zA-Z0-9'’-]*\s+){{0,4}}(?:{OBJECT_WORDS})\b",
    re.I,
)
JP_PHRASE = re.compile(r"(?:[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9・]{1,30})(?:フィギュア|マスコット|ぬいぐるみ|手办|模型|피규어)")
GENERIC = {"figure", "figurine", "statue", "mascot", "replica", "mask",
           "plush", "pin", "badge", "stand", "miniature", "sculpture"}
SIGNAL = re.compile(
    r"collector.s edition|limited edition|exclusive|bundle|physical edition|"
    r"merchandise|figurine|statue|mascot|replica|plush|フィギュア|マスコット|手办|模型",
    re.I,
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
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def extract_objects(text: str) -> list[dict]:
    clean = plain_text(text)
    if not SIGNAL.search(clean):
        return []
    found = []
    seen = set()
    for pattern in (EN_PHRASE, JP_PHRASE):
        for match in pattern.finditer(clean):
            name = re.sub(r"\s+", " ", match.group(0)).strip(" ,:;.-")
            if name.casefold() in GENERIC or len(name) < 5:
                continue
            if name.casefold() in seen:
                continue
            seen.add(name.casefold())
            kind = next((v for k, v in KINDS.items() if k.casefold() in name.casefold()), "object")
            found.append({
                "name": name[:90],
                "kind": kind,
                "excerpt": clean[max(0, match.start()-85): min(len(clean), match.end()+85)][:260],
                "extraction_method": "text_pattern",
                "extraction_confidence": 0.50,  # candidate, NOT an official object identity
            })
    return found[:25]


def detect_demand(text: str) -> list[str]:
    clean = plain_text(text).casefold()
    return [kind for kind, expression in DEMAND_PATTERNS.items()
            if re.search(expression, clean, re.I)]
