"""Compact, mobile-first Arabic daily HTML, with verified evidence only."""
from __future__ import annotations

from datetime import datetime
from html import escape as h
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .collect import news_rank
from .state import now_utc

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
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username:
        return None
    return value[:900]


def safe_link(url: str | None, label: str = "المصدر الرسمي") -> str:
    accepted = safe_url(url)
    if not accepted:
        return "غير متحقق"
    return (
        f'<a href="{h(accepted, quote=True)}" '
        f'style="color:{PURPLE};font-weight:700;text-decoration:none">'
        f'{h(label)}</a>'
    )


def image_cell(value: str | None) -> str:
    accepted = safe_url(value)
    if not accepted:
        return (
            '<div style="width:88px;height:88px;background:#f2ecfa;'
            'border-radius:10px;text-align:center;color:#715393;'
            'line-height:88px;font-size:31px">◎</div>'
        )
    return (
        f'<img src="{h(accepted, quote=True)}" width="88" height="88" '
        'alt="صورة من الخبر الرسمي وليست صورة مجسم STL" '
        'style="width:88px;height:88px;border-radius:10px;'
        'object-fit:cover;display:block;background:#f2ecfa;border:0">'
    )


def shell_card(content: str) -> str:
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="width:100%;background:#ffffff;border:1px solid '
        f'{BORDER};border-radius:14px;margin:0 0 14px 0">'
        f'<tr><td style="padding:16px 15px">{content}</td></tr></table>'
    )


def label(text: str) -> str:
    return (
        f'<span style="color:{PURPLE};font-size:12px;'
        'font-weight:700">' + h(text) + "</span>"
    )


def badge(value: str, color: str = "#637083") -> str:
    return (
        f'<span style="color:{color};font-size:12px;'
        'background:#f5f5f8;border-radius:8px;'
        'padding:3px 8px;font-weight:700">' + h(value) + "</span>"
    )


def row_card(title: str, image_url: str | None, detail: str, meta: str,
             link: str | None, status: str, issue: str = "") -> str:
    img = image_cell(image_url)
    title = h(title)
    body = (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="width:100%;border-collapse:collapse"><tr>'
        f'<td style="width:96px;vertical-align:top;padding:2px 0 0 9px">{img}</td>'
        '<td style="vertical-align:top;padding:0 4px;word-break:break-word">'
        f'<div dir="auto" style="color:{PURPLE};font-size:16px;'
        f'font-weight:700;line-height:1.45">{title}</div>'
        f'<div style="color:{MUTED};font-size:12px;line-height:1.7;'
        f'margin-top:5px">{h(meta)}</div></td></tr></table>'
        f'<div style="font-size:13px;margin-top:10px;line-height:1.8">'
        f'{badge(status)} {h(detail)}</div>'
    )
    if issue:
        body += (
            f'<div style="color:#935b16;font-size:12px;'
            f'margin-top:7px">{h(issue)}</div>'
        )
    body += (
        '<div style="font-size:12px;margin-top:8px">'
        + safe_link(link, "فتح الخبر الأصلي ↗")
        + "</div>"
    )
    return shell_card(body)


def document_watch(state: dict, date: str, max_items: int = 6) -> str:
    """Show relevant original news even with zero extracted objects."""
    docs = [
        doc for doc in state.get("documents", {}).values()
        if doc.get("kind") != "community" and doc.get("url")
    ]
    for doc in docs:
        rank, category = news_rank(doc.get("title", ""), doc.get("summary", ""))
        doc["_render_rank"] = int(doc.get("news_interest", rank))
        doc["_render_category"] = doc.get("news_category", category)
    docs.sort(
        key=lambda d: (
            d["_render_rank"],
            d.get("published_at") or d.get("first_seen") or "",
        ),
        reverse=True,
    )
    chosen = []
    counts = {}
    for doc in docs:
        if doc["_render_rank"] < 2:
            continue
        sid = doc.get("source", "")
        if counts.get(sid, 0) >= 2:
            continue
        chosen.append(doc)
        counts[sid] = counts.get(sid, 0) + 1
        if len(chosen) >= max_items:
            break
    if not chosen:
        return shell_card(
            "لم تُسجَّل أخبار مرتبطة بالمقتنيات أو عناصر الألعاب "
            "في نطاق المصادر التي اكتمل فحصها."
        )
    items = []
    for doc in chosen:
        category = (
            "مقتنيات / إصدار خاص"
            if doc["_render_category"] == "collector"
            else "أخبار ألعاب وشخصيات"
        )
        analysis = doc.get("analysis_status")
        status = (
            "خبر راجعناه نصيًا" if analysis == "full_text"
            else "تم فحص المقتطف" if analysis
            else "بانتظار تحليل المقال"
        )
        meta = (
            f'{doc.get("source", "مصدر غير معروف")} • '
            f'{local_time(doc.get("published_at"))} • {category}'
        )
        extra = (
            "لم يُثبت طلب شراء أو غياب منافسين؛ هذا خبر للمتابعة وليس قرار إنتاج."
        )
        items.append(row_card(
            doc.get("title", "خبر دون عنوان"),
            doc.get("image_url"),
            "رصد أولي من مصدر إخباري؛ لم يثبت بعد أنه منتج STL مطلوب.",
            meta, doc.get("url"), status, extra,
        ))
    return "".join(items)


def opportunity_card(op: dict) -> str:
    score = op.get("score") or {}
    comp = op.get("competition") or {}
    source = (op.get("evidence") or [{}])[0]
    if comp.get("status") == "sampled":
        competition = (
            f'{comp.get("exact_name_candidates", 0)} مطابق اسمًا محتمل، '
            f'{comp.get("similar_name_candidates", 0)} مشابه اسمًا؛ '
            'غير متحقق بصريًا'
        )
    else:
        competition = "غير مفحوص — لا تعني صفر منافسين"
    name = op.get("name", "عنصر غير مسمى")
    demand_count = len(op.get("demand_evidence") or [])
    meta = (
        f'{op.get("region", "غير محدد")} • '
        f'{local_time(op.get("first_signal_date"))} • '
        f'نوع القطعة: {op.get("kind", "غير محدد")}'
    )
    details = (
        f'مؤشر مبدئي {score.get("lower", "؟")}/100، '
        f'الثقة {score.get("confidence", "؟")}/100؛ '
        f'إشارات طلب مرصودة: {demand_count}؛ '
        f'منافسة Cults3D: {competition}.'
    )
    note = (
        "WATCH فقط: الحقوق والطباعة FDM والطلب التجاري تحتاج تحققًا. "
        "الصورة من الخبر الأصلي، وليست ملف STL."
    )
    return row_card(
        name, op.get("image_url"), details, meta,
        source.get("url"), "🔎 عنصر مرشح", note,
    )


def stat_cell(value: str | int, name: str) -> str:
    return (
        '<td style="width:25%;text-align:center;padding:10px 2px;'
        f'border-left:1px solid {BORDER}">'
        f'<div style="font-size:21px;font-weight:800;color:{INK}">'
        f'{h(str(value))}</div><div style="font-size:11px;'
        f'color:{MUTED}">{h(name)}</div></td>'
    )


def render(state: dict, date: str) -> str:
    documents = state.get("documents") or {}
    ops = list((state.get("opportunities") or {}).values())
    ops.sort(
        key=lambda o: (
            o.get("score", {}).get("lower", 0),
            o.get("discovery_date", ""),
        ),
        reverse=True,
    )
    health = state.get("source_health") or {}
    official = [s for s in health.values() if s.get("kind") == "official"]
    healthy = sum(str(s.get("status", "")).startswith("ok") for s in official)
    reviewed = sum(bool(d.get("reviewed_at")) for d in documents.values())
    full = sum(d.get("analysis_status") == "full_text" for d in documents.values())
    new_today = sum(
        local_time(o.get("discovery_date", "")).startswith(
            f'{date[8:10]}-{date[5:7]}-{date[0:4]}'
        )
        for o in ops
    )
    watched = sum(
        o.get("score", {}).get("decision") == "WATCH" for o in ops
    )
    op_html = (
        "".join(opportunity_card(op) for op in ops[:5])
        if ops else shell_card(
            "لم يُستخرج عنصر مادي موثوق من الأخبار التي جرى تحليلها بعد. "
            "يظهر أسفل ذلك رصد الأخبار المهمة بأدلتها الأصلية."
        )
    )
    health_lines = []
    for sid, info in sorted(health.items()):
        if info.get("status") == "disabled":
            continue
        status = str(info.get("status", "غير معروف"))
        display_status = (
            "ناجح" if status.startswith("ok") else "تعذر الفحص"
        )
        health_lines.append(
            f'<div style="padding:5px 0;border-bottom:1px solid {BORDER}">'
            f'<b>{h(info.get("source_name", sid))}</b> — '
            f'{h(display_status)} · آخر نجاح: '
            f'{local_time(info.get("last_success"))}</div>'
        )
    intro = (
        "حتى الآن لا توجد توصية DESIGN NOW مدعومة بطلب مرصود "
        "ومنافسة متحققة ومراجعة حقوق. هذه نتائج البحث الجاري "
        "وليست حكمًا على غياب الفرص عالميًا."
    )
    content = f"""<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TaL3D Global Hunter — {h(date)}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f7;color:{INK};
font-family:Arial,Tahoma,sans-serif;direction:rtl">
<table role="presentation" cellpadding="0" cellspacing="0"
style="width:100%;background:#f4f4f7">
<tr><td align="center" style="padding:18px 8px">
<table role="presentation" cellpadding="0" cellspacing="0"
style="width:100%;max-width:670px">
<tr><td style="background:#ffffff;border:1px solid {BORDER};
border-radius:14px;text-align:center;padding:22px 16px">
<div style="color:{PURPLE};font-size:13px;font-weight:700">
THE FIRST-MOVER INTELLIGENCE SYSTEM</div>
<div style="color:{PURPLE};font-size:26px;font-weight:800;
padding:6px 0">📡 TaL3D — Global Hunter</div>
<div style="color:{MUTED};font-size:14px">
التقرير اليومي • {h(date)} • توقيت الرياض</div></td></tr>
<tr><td style="padding:14px 0">
<table role="presentation" style="width:100%;background:#fff;
border:1px solid {BORDER};border-radius:12px" cellpadding="0"
cellspacing="0"><tr>
{stat_cell(len(documents), "أخبار محفوظة")}
{stat_cell(reviewed, "مقالات روجعت")}
{stat_cell(len(ops), "قطع مرشحة")}
{stat_cell(f"{healthy}/{len(official)}", "مصادر سليمة")}
</tr></table>
</td></tr>
<tr><td>
{shell_card(f'<div style="font-size:17px;color:{PURPLE};font-weight:700">🎯 القرار اليوم</div><p style="font-size:13px;line-height:1.9">{h(intro)}</p><div style="font-size:12px;color:{MUTED}">مراجعة النص الكامل: {full} | عناصر للمراقبة: {watched} | اكتشافات اليوم: {new_today}</div>')}
<div style="font-size:18px;font-weight:800;color:{PURPLE};
padding:2px 2px 12px">📌 فرص التصميم المرشحة</div>
{op_html}
<div style="font-size:18px;font-weight:800;color:{PURPLE};
padding:8px 2px 12px">📰 أهم الأخبار والإشارات</div>
{document_watch(state, date)}
<div style="font-size:17px;font-weight:800;color:{PURPLE};
padding:8px 2px 12px">📊 جودة التغطية وحالة المصادر</div>
{shell_card('<div style="font-size:13px;line-height:2">' + "".join(health_lines) + '</div><p style="color:#80500d;font-size:12px">تحليل الأخبار ومنافسة STL مرحلتان مستقلتان. فشل أي مصدر لا يُسجَّل بوصفه صفرًا.</p>')}
<div style="text-align:center;color:{MUTED};font-size:11px;
line-height:1.8;padding:12px">
Generated {now_utc()} UTC<br>
المعلومات من مصادر منشورة، ولا تمثل إثبات طلب تجاري أو ترخيص نسخ.
</div>
</td></tr>
</table>
</td></tr></table></body></html>"""
    return content


def report_path(date: str) -> Path:
    return Path("reports") / f"{date}.html"
