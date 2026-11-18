from __future__ import annotations
from datetime import datetime
from html import escape as h
from pathlib import Path
from zoneinfo import ZoneInfo
from .state import now_utc

ZONE = ZoneInfo("Asia/Riyadh")


def local_time(value: str | None) -> str:
    if not value:
        return "غير متحقق"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZONE).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return "غير متحقق"


def safe_link(url: str, label: str = "المصدر الأصلي") -> str:
    if not url.startswith(("https://", "http://")):
        return "غير متحقق"
    return '<a href="' + h(url, quote=True) + '" rel="noopener noreferrer">' + h(label) + "</a>"


def render(state: dict, date: str) -> str:
    ops = list(state["opportunities"].values())
    ops.sort(key=lambda x: (x.get("score", {}).get("lower", 0),
                            x.get("discovery_date", "")), reverse=True)
    items = []
    for op in ops[:5]:
        score = op.get("score", {})
        comp = op.get("competition", {})
        source = (op.get("evidence") or [{}])[0]
        competition = (
            f'{comp.get("exact_name_candidates", 0)} اسم مطابق مرشح و'
            f'{comp.get("similar_name_candidates", 0)} اسم مشابه مرشح ضمن '
            f'{comp.get("sample_size", 0)} نتيجة مفحوصة؛ ليست مطابقة بصرية'
            if comp.get("status") == "sampled" else "غير مفحوص — لا يُحسب صفرًا"
        )
        items.append(f"""
        <section class="card">
          <p class="meta">WATCH · {h(op.get('region','unknown'))} · {h(op.get('language','unknown'))}</p>
          <h2 dir="ltr">{h(op.get('name',''))}</h2>
          <p>الخبر الأصلي: {h(op.get('origin',''))}</p>
          <div class="numbers"><span>الحد الأدنى للتقييم <b>{score.get('lower', 0)}/100</b></span>
          <span>الحد الأعلى النظري <b>{score.get('upper', 100)}/100</b></span>
          <span>الثقة <b>{score.get('confidence', 0)}/100</b></span></div>
          <p><strong>أول ظهور موثق:</strong> {local_time(op.get('first_signal_date'))} |
          <strong>اكتشفه النظام:</strong> {local_time(op.get('discovery_date'))}</p>
          <p><strong>المنافسة:</strong> {h(competition)}</p>
          <p><strong>الطلب المرصود:</strong> {len(op.get('demand_evidence', []))} مصدر مستقل مرتبط مباشرة بالعنصر
          (لا تُستنتج مبيعات من هذا العدد)</p>
          <p><strong>FDM:</strong> مرشح أولي؛ تحتاج الأبعاد والثبات والدعامات إلى فحص يدوي.</p>
          <p><strong>الحقوق:</strong> غير متحققة؛ لا توصية بالنشر التجاري.</p>
          <p><strong>نواقص البيانات:</strong> {h(', '.join(score.get('missing_factors', [])) or 'لا شيء')}</p>
          <p>{safe_link(source.get('url',''))}</p>
        </section>""")
    official = [x for x in state["source_health"].values() if x.get("kind") == "official"]
    healthy = sum(x.get("status", "").startswith("ok") for x in official)
    health = "".join(
        "<li>" + h(v.get("source_name", sid)) + ": <b>" + h(v.get("status", "unknown")) +
        "</b> — آخر نجاح: " + local_time(v.get("last_success")) + "</li>"
        for sid, v in sorted(state["source_health"].items())
    )
    new_today = [x for x in ops if local_time(x.get("discovery_date")).startswith(date)]
    intro = ("لا توجد اليوم فرصة مستوفية لشروط توصية DESIGN NOW. "
             "النتائج التالية إشارات أولية للمراقبة وليست دليل طلب تجاري.")
    main = "\n".join(items) or '<div class="card">لم تُكتشف قطع قابلة للتحليل في نطاق المصادر المفحوصة.</div>'
    return f"""<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TaL3D Global Hunter — {date}</title>
<style>
body{{font-family:Arial,Tahoma,sans-serif;margin:0;background:#f4f6f9;color:#182638;line-height:1.75}}
main{{max-width:760px;margin:auto;padding:20px 14px}}
.header,.card{{background:white;padding:22px;border-radius:15px;margin:0 0 14px;border:1px solid #e3e8ef}}
.header{{background:#13263d;color:white}}
.meta{{font-size:12px;color:#687b92;margin:0}}.header .meta{{color:#b4c9e1}}
h1{{font-size:25px;margin:4px 0}}h2{{font-size:19px;margin:5px 0;unicode-bidi:plaintext}}
h3{{margin:14px 0 6px}}p{{margin:6px 0 12px}}a{{color:#136ca7;overflow-wrap:anywhere}}
.numbers{{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}}
.numbers span{{background:#f0f4fa;border-radius:8px;padding:8px 12px;font-size:13px}}
.numbers b{{display:block;font-size:19px}}ul{{padding-right:24px}}
footer{{font-size:12px;color:#687b92;padding:12px}}
</style></head><body><main>
<div class="header"><p class="meta">THE FIRST-MOVER INTELLIGENCE SYSTEM</p>
<h1>TaL3D — GLOBAL OPPORTUNITY HUNTER</h1>
<p>التقرير اليومي · {date} · توقيت الرياض</p>
<p>مصادر رسمية سليمة: {healthy}/{len(official)} · مرشحون جدد: {len(new_today)}</p></div>
<div class="card"><h3>🎯 القرار اليوم</h3><p>{intro}</p></div>
<h3>Today's Top Hunts — إشارات للمراقبة</h3>{main}
<div class="card"><h3>Just Discovered</h3>
<p>{len(new_today)} عنصرًا مرشحًا جديدًا مسجلًا اليوم؛ لا تسمى الفرصة جديدة لمجرد إعادة نشر الخبر.</p>
<h3>Breakout Watch</h3><p>لا يوجد زخم طلب مستقل مثبت من البيانات المتاحة حاليًا.</p>
<h3>Premium & Scarcity Alerts</h3><p>لم يتم إثبات أسعار أو ندرة قابلة للتقييم آليًا في MVP.</p>
<h3>Competitor Intelligence</h3><p>نتائج Cults3D تُعامل عينات بحث فقط؛ حالة كل عنصر موضحة في بطاقته.</p>
<h3>Upcoming Opportunities</h3><p>تقويم الأحداث الموثق ضمن V2؛ لا نخترع مواعيد.</p></div>
<div class="card"><h3>صحة المصادر وتغطية الفحص</h3><ul>{health or '<li>لم يبدأ الفحص بعد</li>'}</ul></div>
<footer>Generated {now_utc()} UTC · تقرير رصد، وليس ضمانًا للطلب أو ترخيصًا لاستنساخ مقتنيات.</footer>
</main></body></html>"""


def report_path(date: str) -> Path:
    return Path("reports") / f"{date}.html"
