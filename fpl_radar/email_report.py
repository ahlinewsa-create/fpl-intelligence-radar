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

def transfer_cards(moves, provisional=False):
    """Compact stacked email cards, readable on mobile without horizontal tables."""
    cards=[]
    for move in moves[:3]:
        def player(which):
            return esc(move.get(which))+' <span class="player-meta">('+esc(move.get(which+'_team') or '?')+' · '+esc(move.get(which+'_position') or '?')+' · #'+esc(move.get(which+'_id'))+')</span>'
        metrics='<div class="transfer-metrics"><div>توقع المباع<strong>'+esc(move.get('old_5gw'))+'</strong></div><div>توقع المشترى<strong>'+esc(move.get('new_5gw'))+'</strong></div><div>مكسب أفضل 11<strong>+'+esc(move.get('team_gain_5gw'))+'</strong></div></div>'
        prices=(' <p class="fine">سعر البيع: '+esc(move.get('sell_price'))+' | سعر الشراء: '+esc(move.get('cost'))+' | البنك بعد: '+esc(move.get('bank_after'))+'</p>') if not provisional else ''
        cards.append('<div class="transfer-card"><p class="transfer-label">بيع محتمل</p><p class="transfer-person">'+player('sell')+'</p><p class="transfer-label">⬇ شراء محتمل</p><p class="transfer-person">'+player('buy')+'</p>'+metrics+prices+'</div>')
    return ''.join(cards)

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
        # Transfer watchlist is presented once in the decision desk.
    else:
        parts.append(section('بيانات فريقك', '<p>تعذر الحصول على تفاصيل فريقك في هذا التقرير؛ التحليل العام متاح.</p>'))
    desk = report.get('decision_desk') or {}
    if desk:
        lead = '<p><strong>'+esc(desk.get('action'))+'</strong> — '+esc(desk.get('reason'))+'</p>'
        lead += '<p>الكابتن من فريقك: '+esc(desk.get('captain'))+' | النائب: '+esc(desk.get('vice_captain'))+'</p>'
        if desk.get('captain_comparison'):
            lead += '<p><strong>مقارنة كباتن فريقك:</strong> '+esc(' | '.join(str(x['name'])+': '+str(x['points']) for x in desk['captain_comparison']))+' نقطة متوقعة قبل المضاعفة.</p>'
        lead += '<p>المهلة: '+esc(desk.get('deadline'))+' | درجة الثقة: '+esc(desk.get('confidence'))+'</p>'
        bestmove = desk.get('best_transfer')
        if bestmove:
            lead += '<p><strong>الصفقة المقترحة للمراجعة:</strong> '+esc(bestmove.get('sell'))+' ← '+esc(bestmove.get('buy'))+'، تحسن التشكيلة على خمس جولات: '+esc(bestmove.get('team_gain_5gw'))+'</p>'
        parts.insert(1, section('🎯 قرار فريقك لهذه الجولة', lead))
        parts.insert(2, section('تشكيلتك الأساسية والاحتياط', '<p><strong>الأساسي:</strong> '+esc('، '.join(desk.get('starting') or []))+'</p><p><strong>الاحتياط:</strong> '+esc('، '.join(desk.get('bench') or []))+'</p>'))
        if desk.get('forecast_anomalies'):
            parts.insert(3,section('⚠️ توقعات تحتاج مراجعة',table([(x.get('sell'),x.get('old_5gw'),x.get('reason')) for x in desk['forecast_anomalies']],['اللاعب','توقع 5 جولات','سبب التنبيه'])))
        if desk.get('watchlist'):
            parts.insert(3,section('🔎 فرص انتقال للمراقبة — الأسعار غير مؤكدة',transfer_cards(desk['watchlist'],provisional=True)+'<p class="fine">توقعات تقديرية غير معايرة، وليست نقاطاً مضمونة. تحقق من سعر البيع داخل اللعبة وعدد الانتقالات المجانية.</p>'))
        if desk.get('transfers'):
            parts.insert(3,section('أفضل ثلاث صفقات قابلة للمراجعة',transfer_cards(desk['transfers'])))
    chips = report.get('chip_strategy') or {}
    if chips:
        names = {'wildcard':'وايلد كارد', 'freehit':'فري هيت', 'bboost':'بنش بوست', '3xc':'تريبل كابتن'}
        advice = chips.get('recommendations') or []
        warning = '<p>آخر جولة لاحتساب خواص هذا النصف: '+esc(chips.get('chip_deadline_gameweek'))+'. '+esc(chips.get('decision'))+'</p>'
        if chips.get('urgency_note'):
            warning += '<p><strong>تنبيه المهلة:</strong> '+esc(chips['urgency_note'])+'</p>'
        if not chips.get('history_verified'):
            warning += '<p><strong>تنبيه:</strong> لم يتم التأكد من سجل استخدام الخواص لدى حسابك. راجع اللعبة قبل تطبيق التوصية.</p>'
        if advice:
            warning += table([(x.get('gameweek'), names.get(x.get('chip'), x.get('chip')), x.get('confidence'), x.get('reason')) for x in advice], ['الجولة','الخاصية','الثقة','سبب الترشيح'])
        else:
            warning += '<p>لا توجد إشارة قوية حالياً؛ يفضّل الانتظار ومراقبة تغيّر الجداول.</p>'
        parts.append(section('توقيت الخواص الذكي', warning))
    parts.append(section('أفضل خيارات الكابتن', table([(p.get('name'),p.get('projected_double_points'), str(round(100*p.get('availability',0)))+'%') for p in captain[:5]], ['اللاعب','نقاط مضاعفة تقديرية','احتمال الإتاحة التقريبي'])))
    parts.append(section('أعلى اللاعبين تقييماً', table([(p.get('name'),p.get('team'),p.get('position'),p.get('price'),p.get('estimated_score')) for p in report.get('top_players',[])[:7]], ['اللاعب','الفريق','المركز','السعر','نقاط تقديرية'])))
    parts.append(section('أفضل قيمة مقابل السعر', table([(p.get('name'),p.get('price'),p.get('value')) for p in report.get('value_picks',[])[:5]], ['اللاعب','السعر','مؤشر القيمة'])))
    squad = report.get('suggested_squad') or {}
    if squad.get('status') == 'ok' and not team:
        parts.append(section('تشكيلة افتراضية من الصفر — ليست خطة انتقالات لحسابك', '<p>التكلفة '+esc(squad.get('cost'))+' — النقاط التقديرية لأفضل 11: '+esc((squad.get('lineup') or {}).get('projected_points'))+'</p>'+table([(p.get('name'),p.get('position'),p.get('price')) for p in squad.get('players',[])],['اللاعب','المركز','السعر'])))
    difficulty = report.get('fixture_difficulty_next_5') or {}
    parts.append(section('صعوبة المباريات القادمة', '<p>تم رصد جدول الصعوبة لـ '+esc(len(difficulty))+' فريقاً. الأرقام من 1 (أسهل) إلى 5 (أصعب) وفق FPL.</p>'))
    upcoming = report.get('multiweek_top') or []
    if upcoming:
        parts.append(section('توقعات الخمس جولات القادمة', table([(x.get('name') or x.get('id'), x.get('total'), x.get('minutes_estimate'), x.get('xg_season_total'), x.get('xa_season_total')) for x in upcoming[:6]], ['اللاعب','نقاط 5 جولات','دقائق/مشاركة','xG الموسم','xA الموسم'])))
    differentials = report.get('differentials') or []
    if differentials:
        parts.append(section('فرص قليلة الملكية', table([(x.get('name'),x.get('ownership_pct'),x.get('five_week_estimate')) for x in differentials[:5]], ['اللاعب','الملكية %','تقييم 5 جولات'])))
    watch = report.get('injury_watch') or []
    if watch:
        owned_ids=set((desk.get('starting_ids') or [])+(desk.get('bench_ids') or []))
        target_ids={x.get('buy_id') for x in (desk.get('watchlist') or [])+(desk.get('transfers') or [])}
        watch=[x for x in watch if x.get('player_id') in owned_ids or x.get('player_id') in target_ids]
        if watch: parts.append(section('غيابات فريقك وأهداف الانتقالات', table([(x.get('player'),x.get('status'),x.get('news')) for x in watch[:7]], ['اللاعب','الحالة','الخبر'])))
    blanks = report.get('blank_double') or []
    if blanks:
        parts.append(section('الجولات المزدوجة والفارغة', table([(x.get('gw'),len(x.get('blank_team_ids') or []),len(x.get('double_team_ids') or [])) for x in blanks],['الجولة','فرق بلا مباريات','فرق بمباراتين'])))
    manager = team.get('manager') or {}
    if manager:
        parts.append(section('ميزانية الفريق', '<p>البنك وفق بيانات الجولة السابقة: '+esc(manager.get('bank'))+' مليون. الترتيب العام: '+esc(manager.get('overall_rank'))+'. يجب التحقق من الرصيد الحالي قبل إجراء أي انتقال.</p>'))

    if not desk:
        parts.insert(1,section('القرار الرئيسي', '<p>تعذر استخراج توصية خاصة بالفريق؛ راجع بياناتك المنشورة.</p>'))
    quality = report.get('quality') or {}
    if quality.get('warnings'):
        parts.append(section('ملاحظات جودة البيانات', '<p>'+esc(' | '.join(quality['warnings']))+'</p>'))
    benchmark = report.get('forecast_benchmark') or {}
    if benchmark.get('n'):
        parts.append(section('🔬 فحص التوقعات', '<p>تمت مقارنة توقعاتنا مع تقييم FPL الرسمي لعدد '+esc(benchmark['n'])+' لاعب. متوسط الاختلاف المطلق: '+esc(benchmark.get('mean_absolute_disagreement'))+' نقطة. هذه مقارنة بين نموذجين وليست قياساً لدقة التنبؤ بنتائج المباريات.</p>'))
    parts.append('<p class="fine">هذه مؤشرات تقديرية غير مضمونة، وليست توقعاً إحصائياً معايراً. التشكيلات والانتقالات لا تنفذ تلقائياً، وبيانات الفريق قد تعكس الجولة السابقة فقط.</p>')
    style='''body{margin:0;background:#f1f5f9;font-family:Tahoma,Arial,sans-serif;color:#142439;direction:rtl}.wrap{max-width:740px;margin:24px auto;background:#fff;border-radius:16px;overflow:hidden}.hero{background:#101a39;color:#fff;padding:30px}.hero h1{font-size:28px;margin:0 0 8px}.hero p{color:#cad5ee;margin:0}.inner{padding:20px 24px}.summary{display:flex;gap:8px;flex-wrap:wrap}.summary div{flex:1;min-width:130px;background:#eaf8f3;border-radius:10px;padding:14px;font-size:12px}.summary strong{display:block;font-size:19px;color:#005c4d;margin-top:6px}section{margin:22px 0 0;border:1px solid #e1e8f0;border-radius:10px;overflow:hidden}h2{font-size:17px;background:#f4f7fb;padding:14px;margin:0}section p{padding:0 14px}table{width:100%;border-collapse:collapse;text-align:right;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e6edf3}th{color:#475569;background:#fafcfe}.fine{font-size:12px;color:#64748b;line-height:1.8}.footer{background:#f4f7fb;padding:15px;color:#64748b;font-size:12px}@media(max-width:500px){.inner{padding:10px}th,td{padding:6px;font-size:11px}}'''
    style += '''.transfer-card{padding:14px;margin:12px;border:1px solid #cdd9e5;border-radius:12px;background:#fbfdff}.transfer-card p{padding:0;margin:7px 0;line-height:1.65}.transfer-label{font-size:11px;color:#64748b}.transfer-person{font-size:15px;font-weight:bold;overflow-wrap:anywhere}.player-meta{font-size:11px;color:#65758a;font-weight:normal;white-space:normal}.transfer-metrics{display:flex;gap:6px;margin:12px 0}.transfer-metrics div{flex:1;min-width:0;text-align:center;background:#eaf8f3;border-radius:8px;padding:9px 4px;font-size:10px;color:#475569}.transfer-metrics strong{display:block;font-size:17px;color:#005c4d;margin-top:5px}@media(max-width:500px){.transfer-card{margin:10px 7px;padding:12px}.transfer-person{font-size:14px}.transfer-metrics strong{font-size:15px}}'''
    return '<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>'+style+'</style></head><body><div class="wrap"><div class="hero"><h1>⚽ رادار الفانتسي الذكي</h1><p>تقرير أسبوعي مخصص • الجولة '+esc(gw)+'</p></div><div class="inner">'+''.join(parts)+'</div><div class="footer">FPL Intelligence Radar • تقرير آلي • '+esc(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))+' • نسخة '+esc(report.get('build_sha','unknown'))+'</div></div></body></html>'

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
