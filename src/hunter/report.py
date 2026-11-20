"""Mobile-first TaL3D report: group events, separate evidence from hypotheses.

News publication dates are never replaced by discovery dates. Cults search
sampling does not prove absence of competitors. No community access does
not mean zero buying demand.
"""
from __future__ import annotations

from datetime import datetime
from html import escape as h
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .state import now_utc
from .triage import demand_coverage, event_key, group_events, select_news

ZONE = ZoneInfo("Asia/Riyadh")
PURPLE = "#8128cf"
INK = "#1a2639"
MUTED = "#667085"
BORDER = "#e8e4f0"


def local_time(value: str | None) -> str:
    if not value:
        return "غير متحقق"
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(ZONE).strftime("%d-%m-%Y %H:%M")
    except (ValueError, TypeError, AttributeError):
        return "غير متحقق"


def safe_url(value: str | None) -> str | None:
    value = str(value or "")
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        return None
    return value[:900]


def safe_link(url: str | None, text: str = "فتح الخبر الأصلي") -> str:
    value = safe_url(url)
    if not value:
        return "غير متحقق"
    return (
        f'<a href="{h(value, quote=True)}" rel="noopener noreferrer" '
        f'style="color:{PURPLE};font-weight:700;text-decoration:none">'
        f'{h(text)}</a>'
    )


def image_cell(url: str | None) -> str:
    value = safe_url(url)
    if not value:
        return (
            '<div style="width:82px;height:82px;background:#f2ecfa;'
            'border-radius:10px;color:#7854a0;text-align:center;'
            'font-size:24px;line-height:82px">◎</div>'
        )
    return (
        f'<img src="{h(value, quote=True)}" width="82" height="82" '
        'alt="صورة من الخبر المنشور" style="width:82px;height:82px;'
        'object-fit:cover;border-radius:10px;display:block;background:#f2ecfa">'
    )


def card(content: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        f'style="width:100%;background:#fff;border:1px solid {BORDER};'
        'border-radius:14px;margin-bottom:13px">'
        f'<tr><td style="padding:15px">{content}</td></tr></table>'
    )


def heading(value: str) -> str:
    return (
        f'<div style="font-size:18px;font-weight:800;color:{PURPLE};'
        f'padding:12px 3px 9px">{h(value)}</div>'
    )


def media_header(title: str, image: str | None, metadata: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="width:100%"><tr>'
        '<td style="width:89px;vertical-align:top;padding-left:8px">'
        + image_cell(image) + '</td><td style="vertical-align:top">'
        f'<div dir="auto" style="font-size:16px;font-weight:750;'
        f'color:{PURPLE};line-height:1.5;overflow-wrap:anywhere">'
        f'{h(title)}</div><div style="font-size:12px;line-height:1.75;'
        f'color:{MUTED};margin-top:5px">{h(metadata)}</div>'
        '</td></tr></table>'
    )


def competition_text(comp: dict) -> str:
    if comp.get("status") == "sampled" and comp.get("schema_version") in (2, 3):
        size = comp.get("sample_size", 0)
        contextual = comp.get("contextual_name_candidates", 0)
        named = comp.get("name_only_candidates", 0)
        similar = comp.get("similar_name_candidates", 0)
        attempts = comp.get("query_reports") or []
        queries = (f" عبر {len(attempts)} استعلامات" if attempts else "")
        return (
            f"فُحصت عينة من {size} نتيجة{queries}: {contextual} مرشح اسم وسياق، "
            f"{named} اسم مشترك، {similar} اسم مشابه. "
            "لم يُثبت عدد الملفات المطابقة بصريًا، ولا تشبع السوق."
        )
    if comp.get("status") == "sampled":
        return "فحص قديم بمعيار أسماء سابق — يحتاج التحقق مجددًا"
    if comp.get("status") == "failed":
        return "تعذّر فحص Cults3D — المنافسة غير متحققة"
    return "غير مفحوص — لا تعني صفر منافسين"


def next_research_step(op: dict) -> str:
    """A concrete next check, not an invented forecast."""
    comp = op.get("competition") or {}
    if comp.get("status") != "sampled":
        return "فحص منافسة Cults3D باستعلام اسم المنتج الحقيقي وتوثيق العينة"
    if not op.get("demand_evidence"):
        return "البحث عن طلب صريح على STL أو طباعة FDM دون استنتاج من الخبر وحده"
    return "تقييم ملاءمة الفكرة للطباعة FDM بمراجعة هندسية أولية"


def object_detail(op: dict, communities_checked: bool) -> str:
    name = op.get("name", "عنصر دون اسم")
    score = op.get("score") or {}
    comp = op.get("competition") or {}
    demand = op.get("demand_evidence") or []
    if demand:
        demand_text = f"{len(demand)} رابط دليل اهتمام مرصود (لا يثبت شراء STL)"
    elif communities_checked:
        demand_text = "لم تُسجل إشارة مرتبطة بالقطعة ضمن المصادر المجتمعية المفحوصة"
    else:
        demand_text = "غير مفحوص — مصادر النقاش غير مفعّلة"
    dimensions = score.get("dimensions") or {}
    coverage = score.get("coverage") or {}
    hypothesis = op.get("design_hypothesis") or {}
    fdm = op.get("fdm_precheck") or {}
    timing = op.get("timing_precheck") or {}
    external = op.get("external_competition") or []
    release = op.get("release_calendar") or {}
    demand_state = (dimensions.get("demand") or {}).get("status", "not_checked")
    evidence_detail = (
        f'<div style="font-size:12px;line-height:1.85"><b>تغطية الأدلة:</b> '
        f'{h(str(coverage.get("checked", 0)))}/{h(str(coverage.get("total", 5)))} مجالات '
        f'• طلب: {h(demand_state)} '
        f'• قرار: {h(score.get("decision", "WATCH"))}</div>'
        f'<div style="font-size:12px;line-height:1.85"><b>فكرة أصلية للاختبار:</b> '
        f'{h(hypothesis.get("title", "لم تُنشأ بعد"))} '
        f'(فرضية غير مثبتة)</div>'
        f'<div style="font-size:12px;line-height:1.85"><b>FDM:</b> '
        f'{h(fdm.get("risk", "غير مفحوص"))} — تقدير أولي، لم تُختبر الهندسة</div>'
        f'<div style="font-size:12px;line-height:1.85"><b>التوقيت:</b> '
        f'{h(timing.get("status", "غير مفحوص"))}'
        f'{(" • ذروة موسمية تقديرية: " + h(timing["estimated_peak"])) if timing.get("estimated_peak") else ""}'
        f'{(" • موعد إصدار موثق للمراجعة: " + h(release["release_date"])) if release.get("release_date") else ""}'
        '</div>'
        f'<div style="font-size:12px;line-height:1.85"><b>منصات STL الأخرى:</b> '
        f'{len(external)} روابط راجعها مستخدم؛ لا تمثل مسحًا شاملًا</div>'
    )
    body = (
        '<div style="border-top:1px solid #ece8f2;padding:11px 0 4px">'
        '<div style="font-size:12px;color:#81519c">🔎 عنصر مرشح للمراجعة</div>'
        f'<div dir="auto" style="font-size:15px;font-weight:750;'
        f'line-height:1.6;color:{PURPLE}">{h(name)}</div>'
        f'<div style="font-size:12px;line-height:1.8;color:{INK}">'
        f'نوع القطعة: {h(op.get("kind", "غير محدد"))} '
        '• حالة القرار: متابعة الأدلة دون ترتيب رقمي افتراضي'
        '</div><div style="font-size:12px;line-height:1.8">'
        f'<b>الطلب:</b> {h(demand_text)}'
        '</div><div style="font-size:12px;line-height:1.8">'
        f'<b>منافسة Cults3D:</b> {h(competition_text(comp))}'
        '</div>'
        '<div style="font-size:12px;line-height:1.8"><b>الخطوة التالية:</b> '
        + h(next_research_step(op)) + '</div>' + evidence_detail + '</div>'
    )
    listings = [
        l for l in (comp.get("listings") or [])[:3]
        if safe_url(l.get("url"))
    ]
    if listings:
        body += (
            '<div style="font-size:11px;color:#6c7586">'
            'أمثلة نتائج أسماء غير مثبتة بصريًا:</div>'
            '<div style="font-size:11px;line-height:1.8">'
            + ' • '.join(safe_link(item["url"], item.get("name", "مرشح")) for item in listings)
            + '</div>'
        )
    return body


def opportunity_group_card(group: dict, communities_checked: bool) -> str:
    primary = group["primary"]
    evidence = (primary.get("evidence") or [{}])[0]
    kind = group["type"]
    if kind == "exhibition":
        kind_label = "معرض / محتوى متحفي"
        caveat = (
            "المعروض في متحف ليس دليلًا على منتج متاح للبيع؛ "
            "يلزم التحقق من اهتمام الجمهور باقتناء نسخة."
        )
    elif kind == "merchandise":
        kind_label = "مقتنيات رسمية"
        caveat = (
            "التغطية الصحفية رصد أولي؛ تحقّق من إعلان الشركة الأصلي. "
            "ظهور القطعة لا يثبت طلبًا على ملفات STL."
            if primary.get("source_kind") == "press" else
            "الإعلان الرسمي يشير إلى ظهور القطعة فقط؛ "
            "لا يثبت وجود طلب على ملفات STL."
        )
    else:
        kind_label = "عنصر من لعبة أو خبر"
        caveat = (
            "ذكر القطعة في الخبر لا يثبت أن الجمهور يريد شراء مجسم لها."
        )
    meta = (
        f'{kind_label} • {primary.get("region", "غير محدد")} • '
        f'نشر المصدر: {local_time(primary.get("first_signal_date"))} '
        f'• مرشحات مستخرجة: {len(group["members"])}'
    )
    body = media_header(
        primary.get("origin", "خبر أصلي دون عنوان"),
        primary.get("image_url"), meta,
    )
    body += (
        '<div style="font-size:12px;color:#795523;padding:8px 0 9px">'
        + h(caveat) + '</div>'
    )
    for member in group["members"][:3]:
        body += object_detail(member, communities_checked)
    hidden = len(group["members"]) - 3
    if hidden > 0:
        body += (
            f'<div style="font-size:12px;color:{MUTED};padding:5px 0">'
            f'تم اختصار {hidden} مرشحات إضافية في هذا الحدث لتقليل الضجيج.</div>'
        )
    body += (
        '<div style="font-size:12px;margin-top:10px;color:#986532">'
        'القرار: WATCH فقط • الطلب ومناسبة FDM يحتاجان إلى تحقق</div>'
        '<div style="font-size:12px;margin-top:7px">'
        + safe_link(evidence.get("url")) + '</div>'
    )
    return card(body)


def document_watch(state: dict, report_date: str, max_items: int = 3,
                   excluded_event_keys: set[str] | None = None) -> str:
    selected = select_news(
        state, report_date, excluded_event_keys or set(),
        limit=max_items, max_age_days=5,
    )
    if not selected:
        return card(
            '<div style="font-size:13px;line-height:1.8">'
            'لا توجد أخبار إضافية حديثة عالية الصلة بعد استبعاد '
            'الأخبار المعروضة ضمن فرص المتابعة.</div>'
        )
    entries = []
    for doc in selected:
        metadata = (
            f'{doc.get("source", "مصدر غير محدد")} • '
            f'{local_time(doc.get("published_at"))} '
            '• خبر لم يتحول إلى فرصة تصميم مثبتة'
        )
        body = media_header(
            doc.get("title", "خبر بلا عنوان"),
            doc.get("image_url"), metadata,
        )
        body += (
            '<div style="font-size:12px;line-height:1.9;margin-top:8px">'
            'رصد تحريري للمتابعة، وليس دليل شراء أو توصية تصنيع.</div>'
            '<div style="font-size:12px;margin-top:6px">'
            + safe_link(doc.get("url")) + '</div>'
        )
        entries.append(card(body))
    return "".join(entries)


def stat_cell(value: str | int, title: str) -> str:
    return (
        f'<td style="text-align:center;width:25%;padding:9px 2px;'
        f'border-left:1px solid {BORDER}">'
        f'<div style="font-weight:800;font-size:19px;color:{INK}">'
        f'{h(str(value))}</div><div style="font-size:11px;color:{MUTED}">'
        f'{h(title)}</div></td>'
    )


def render(state: dict, date: str, manual: bool = False) -> str:
    docs = state.get("documents") or {}
    ops = [
        op for op in (state.get("opportunities") or {}).values()
        if op.get("status") != "superseded"
    ]
    recent_events = group_events(
        ops, date, max_age_days=7, max_groups=3,
    )
    checked = demand_coverage(state)
    excluded = {g["id"] for g in recent_events}
    news_html = document_watch(
        state, date, max_items=3, excluded_event_keys=excluded,
    )
    health = state.get("source_health") or {}
    news_sources = [
        item for item in health.values()
        if item.get("kind") in ("official", "press")
        and item.get("status") != "disabled"
    ]
    healthy = sum(
        str(item.get("status", "")).startswith("ok") for item in news_sources
    )
    reviewed = sum(bool(d.get("reviewed_at")) for d in docs.values())
    full = sum(d.get("analysis_status") == "full_text" for d in docs.values())
    active_op_count = len(ops)
    if recent_events:
        opportunities = "".join(
            opportunity_group_card(group, checked) for group in recent_events
        )
    else:
        opportunities = card(
            "لا توجد إشارات حديثة مستوفية لشروط العرض ضمن نطاق المصادر. "
            "لا يعني ذلك غياب فرص عالمية."
        )
    covered = (
        "تم الوصول إلى مصادر نقاش مفعلة"
        if checked else "مصادر النقاش غير مفحوصة"
    )
    health_rows = []
    for sid, item in sorted(health.items()):
        if item.get("status") == "disabled":
            continue
        status = (
            "ناجح" if str(item.get("status", "")).startswith("ok")
            else "تعذر الفحص"
        )
        health_rows.append(
            '<div style="padding:5px 0;border-bottom:1px solid #ece8f2">'
            f'<b>{h(item.get("source_name", sid))}</b> — {h(status)} '
            f'• آخر نجاح: {local_time(item.get("last_success"))}</div>'
        )
    ready_count = sum((op.get("score") or {}).get("decision") == "DESIGN NOW"
                      for op in ops)
    validate_count = sum((op.get("score") or {}).get("decision") == "VALIDATE"
                         for op in ops)
    decision = (
        f"توجد {ready_count} فرضيات اجتازت بوابات التحقق المسجلة؛ راجع الأدلة قبل التصميم."
        if ready_count else
        "لا توجد توصية DESIGN NOW مستوفية لأدلة الطلب والمنافسة والجدوى. "
        "الإشارات الحالية للمراقبة أو التحقق؛ غياب دليل الطلب لا يعني عدم وجوده."
    )
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TaL3D Global Hunter — {h(date)}</title></head>
<body style="margin:0;padding:0;background:#f5f4f8;
color:{INK};font-family:Arial,Tahoma,sans-serif;direction:rtl">
<table role="presentation" cellpadding="0" cellspacing="0"
style="width:100%;background:#f5f4f8">
<tr><td align="center" style="padding:16px 8px">
<table role="presentation" cellpadding="0" cellspacing="0"
style="max-width:670px;width:100%">
<tr><td style="background:#fff;border:1px solid {BORDER};
border-radius:14px;padding:19px 12px;text-align:center">
<div style="font-size:12px;color:{PURPLE};font-weight:800">
THE FIRST-MOVER INTELLIGENCE SYSTEM</div>
<div style="font-size:24px;color:{PURPLE};font-weight:800;
padding:4px 0">📡 TaL3D — Global Hunter</div>
<div style="font-size:13px;color:{MUTED}">{"تقرير يدوي جديد" if manual else "التقرير اليومي"} • {h(date)}
• توقيت الرياض</div></td></tr>
<tr><td style="padding:12px 0">
<table role="presentation" cellpadding="0" cellspacing="0"
style="width:100%;background:#fff;border:1px solid {BORDER};
border-radius:12px"><tr>
{stat_cell(len(docs), "أخبار محفوظة")}
{stat_cell(full, "مقالات كاملة")}
{stat_cell(active_op_count, "عناصر في السجل")}
{stat_cell(f"{healthy}/{len(news_sources)}", "مصادر أخبار سليمة")}
</tr></table></td></tr>
<tr><td>
{card(f'<div style="font-size:17px;color:{PURPLE};font-weight:800">🎯 القرار اليوم</div><p style="font-size:13px;line-height:1.85">{h(decision)}</p><div style="font-size:12px;color:{MUTED}">{len(recent_events)} أحداث مرشحة حديثة • {validate_count} فرضيات للتحقق • {reviewed} خبرًا روجع نصيًا • {h(covered)}</div>')}
{heading("📌 إشارات مبكرة — مجمّعة حسب الحدث")}
{opportunities}
{heading("📰 أخبار حديثة تستحق المتابعة")}
{news_html}
{heading("📊 صحة المصادر والتغطية")}
{card('<div style="font-size:12px;line-height:1.9">' + "".join(health_rows) + '</div><div style="font-size:12px;color:#855b24;padding-top:9px">غياب دليل الطلب أو المطابقة البصرية لا يساوي صفرًا في السوق.</div>')}
<div style="text-align:center;color:{MUTED};font-size:11px;
padding:12px;line-height:1.9">
Generated {now_utc()} UTC<br>
الصور من مصادر الأخبار؛ النتائج للاستكشاف فقط، وليست إثبات مبيعات.
</div></td></tr>
</table></td></tr></table>
</body></html>"""


def report_path(date: str) -> Path:
    return Path("reports") / f"{date}.html"
