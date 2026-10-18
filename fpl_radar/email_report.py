"""RTL Arabic HTML email report. Standard-library only."""
import argparse
import html
import json
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

def esc(value):
    return html.escape(str(value if value is not None else '—'))

def table(rows, headings):
    head = ''.join('<th>'+esc(h)+'</th>' for h in headings)
    body = ''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)
    return '<table role="presentation"><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table>'

def section(title, content):
    return '<section><h2>'+esc(title)+'</h2>'+content+'</section>'

def render(report):
    gw = report.get('gameweek') or 'غير محددة'
    captain = report.get('captain_candidates') or []
    best = captain[0] if captain else {}
    cards = '<div class="summary"><div>الجولة <strong>'+esc(gw)+'</strong></div><div>الكابتن المرشح <strong>'+esc(best.get('name', 'لا يوجد'))+'</strong></div><div>التقييم المضاعف <strong>'+esc(best.get('projected_double_points', '—'))+'</strong></div></div>'
    parts = [cards]
    team = report.get('team') or {}
    if team:
        details = '<p>عدد اللاعبين المعروفين: '+esc(team.get('matched_players', '—'))+'</p>'
        lineup = team.get('starting_eleven') or {}
        if lineup:
            details += '<p>التقدير الأساسي للتشكيلة: '+esc(lineup.get('projected_points'))+' نقطة تقريبية — مبني على لاعبي الجولة السابقة.</p>'
        parts.append(section('فريقك الشخصي', details))
        moves = team.get('transfer_ideas') or []
        parts.append(section('اقتراحات الانتقالات', table([(m.get('sell'),m.get('buy'),m.get('estimated_gain_next_week')) for m in moves[:8]], ['بيع','شراء','فرق نقاط تقديري']) if moves else '<p>لا توجد اقتراحات موثوقة حالياً.</p>'))
    else:
        parts.append(section('بيانات فريقك', '<p>تعذر الحصول على تفاصيل فريقك في هذا التقرير؛ التحليل العام متاح.</p>'))
    parts.append(section('أفضل خيارات الكابتن', table([(p.get('name'),p.get('projected_double_points'), str(round(100*p.get('availability',0)))+'%') for p in captain[:5]], ['اللاعب','نقاط مضاعفة تقديرية','احتمال الإتاحة التقريبي'])))
    parts.append(section('أعلى اللاعبين تقييماً', table([(p.get('name'),p.get('team'),p.get('position'),p.get('price'),p.get('estimated_score')) for p in report.get('top_players',[])[:12]], ['اللاعب','الفريق','المركز','السعر','نقاط تقديرية'])))
    parts.append(section('أفضل قيمة مقابل السعر', table([(p.get('name'),p.get('price'),p.get('value')) for p in report.get('value_picks',[])[:8]], ['اللاعب','السعر','مؤشر القيمة'])))
    squad = report.get('suggested_squad') or {}
    if squad.get('status') == 'ok':
        parts.append(section('تشكيلة مقترحة جديدة', '<p>التكلفة '+esc(squad.get('cost'))+' — النقاط التقديرية لأفضل 11: '+esc((squad.get('lineup') or {}).get('projected_points'))+'</p>'+table([(p.get('name'),p.get('position'),p.get('price')) for p in squad.get('players',[])],['اللاعب','المركز','السعر'])))
    difficulty = report.get('fixture_difficulty_next_5') or {}
    parts.append(section('صعوبة المباريات القادمة', '<p>تم رصد جدول الصعوبة لـ '+esc(len(difficulty))+' فريقاً. الأرقام من 1 (أسهل) إلى 5 (أصعب) وفق FPL.</p>'))
    parts.append('<p class="fine">هذه مؤشرات تقديرية غير مضمونة، وليست توقعاً إحصائياً معايراً. التشكيلات والانتقالات لا تنفذ تلقائياً، وبيانات الفريق قد تعكس الجولة السابقة فقط.</p>')
    style='''body{margin:0;background:#f1f5f9;font-family:Tahoma,Arial,sans-serif;color:#142439;direction:rtl}.wrap{max-width:740px;margin:24px auto;background:#fff;border-radius:16px;overflow:hidden}.hero{background:#101a39;color:#fff;padding:30px}.hero h1{font-size:28px;margin:0 0 8px}.hero p{color:#cad5ee;margin:0}.inner{padding:20px 24px}.summary{display:flex;gap:8px;flex-wrap:wrap}.summary div{flex:1;min-width:130px;background:#eaf8f3;border-radius:10px;padding:14px;font-size:12px}.summary strong{display:block;font-size:19px;color:#005c4d;margin-top:6px}section{margin:22px 0 0;border:1px solid #e1e8f0;border-radius:10px;overflow:hidden}h2{font-size:17px;background:#f4f7fb;padding:14px;margin:0}section p{padding:0 14px}table{width:100%;border-collapse:collapse;text-align:right;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e6edf3}th{color:#475569;background:#fafcfe}.fine{font-size:12px;color:#64748b;line-height:1.8}.footer{background:#f4f7fb;padding:15px;color:#64748b;font-size:12px}@media(max-width:500px){.inner{padding:10px}th,td{padding:6px;font-size:11px}}'''
    return '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>'+style+'</style></head><body><div class="wrap"><div class="hero"><h1>⚽ رادار الفانتسي الذكي</h1><p>تقرير أسبوعي مخصص • الجولة '+esc(gw)+'</p></div><div class="inner">'+''.join(parts)+'</div><div class="footer">FPL Intelligence Radar • تقرير آلي • '+esc(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+'</div></div></body></html>'

def send(report, *, smtp_host, smtp_port, username, password, recipient):
    if not all((smtp_host, username, password, recipient)):
        raise ValueError('Missing SMTP configuration')
    message = EmailMessage()
    message['Subject'] = '⚽ تقرير FPL الأسبوعي | الجولة '+str(report.get('gameweek') or '—')
    message['From'] = username
    message['To'] = recipient
    message.set_content('تقرير رادار الفانتسي للجولة '+str(report.get('gameweek'))+'. افتح الرسالة بنمط HTML للاطلاع على الجداول.')
    message.add_alternative(render(report), subtype='html')
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context(), timeout=25) as client:
            client.login(username,password)
            client.send_message(message)
    elif smtp_port == 587:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=25) as client:
            client.ehlo()
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
            client.login(username,password)
            client.send_message(message)
    else:
        raise ValueError('SMTP_PORT must be 465 or 587')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='reports/latest.json')
    parser.add_argument('--preview', default=None, help='Write HTML preview, do not send')
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text(encoding='utf-8'))
    if args.preview:
        Path(args.preview).write_text(render(report), encoding='utf-8')
        print('HTML preview written')
    else:
        send(report, smtp_host=os.getenv('SMTP_HOST') or 'smtp.gmail.com',
             smtp_port=int(os.getenv('SMTP_PORT') or '465'),
             username=os.getenv('GMAIL_USER',''), password=os.getenv('GMAIL_PASS',''),
             recipient=os.getenv('TO_EMAIL',''))
        print('Report email sent to configured recipient')

if __name__ == '__main__':
    main()
