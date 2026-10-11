import json, sys
sys.path.insert(0, "lib")
from snippets import code, close_pre_process
SPEC = json.load(open("out/spec.json"))
B = SPEC["base_url"]
SLOT = "tr-practice"

BODY = r'''
def S(k, v=''):
    x = vars.get(k)
    return v if x is None else x
def I(k):
    try: return int(float(S(k, 0) or 0))
    except Exception: return 0
def T(x):
    return str(x).strip().lower() == 'true'
def fresh(k):
    v = str(S(k, 'none') or 'none').strip()
    return '' if v.lower() in ('none', 'null', '') else v
H = SPEC['holidays']
now = parse_now(S('now') or '2026-10-14T11:00')
today = now.date()
TITLE = SPEC['titles'].get(str(S('title')), '') + ' ' + str(S('last_name'))
BYE = 'Teşekkür eder, iyi günler dilerim.'
TECH = 'Teknik bir sorun oldu, bir kez daha deniyorum.'
def close(key, say):
    o, r = SPEC['outcomes'][key]
    if key in ('refused', 'service_error') and I('promised') > 0:
        o, r = 'promise', ''
    vars['outcome'] = o; vars['reason'] = r; vars['st'] = 'closed'
    vars['say'] = (say + ' ' + BYE).strip(); vars['action'] = 'end'
def ask(say, action='talk'):
    vars['say'] = say; vars['action'] = action
def pname(p):
    t = str(p.get('type'))
    return SPEC['product_names'].get(t, t).replace('{last4}', str(p.get('card_last4') or ''))
def ploc(p):
    t = str(p.get('type'))
    return SPEC['product_names_loc'].get(t, pname(p) + 'nızda').replace('{last4}', str(p.get('card_last4') or ''))
def amt(x):
    try: return say_amount_tr(float(x))
    except Exception: return str(x)
def products():
    ps = items_from_keys(vars, 'products')
    if not ps: ps = items_from_vars(vars, ['product_id','type','card_last4','past_due','days_late','minimum_payment','instalment_amount'])
    return ps
def facts(p):
    b = band_for(int(float(p.get('days_late') or 0)), SPEC['bands']) or SPEC['bands'][-1]
    dl = add_bd(today, b['deadline_bd'], H)
    fl = p.get(SPEC['floor_fields'].get(str(p.get('type')), 'minimum_payment'))
    fl = float(fl) if fl not in (None, '') else float(p.get('past_due') or 0)
    return b, dl, fl
def cur():
    ps = products(); i = I('pi')
    return ps[i] if i < len(ps) else None
def dsay(d):
    return 'bugün' if d == today else say_date_tr(d)
def week_offer():
    d = last_bd_of_week(today, H)
    if d <= today: d = last_bd_of_week(today + datetime.timedelta(days=7), H)
    return d
def dob_parse(txt):
    t = tr_ascii(txt)
    MON = ['ocak','subat','mart','nisan','mayis','haziran','temmuz','agustos','eylul','ekim','kasim','aralik']
    m = None
    for i, n in enumerate(MON):
        if re.search(r'\b' + n, t): m = i + 1
    raw = str(txt)
    mm = re.search(r'(\d{1,2})[./\- ](\d{1,2})[./\- ](\d{4})', raw)
    if mm: return int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
    mm = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', raw)
    if mm: return int(mm.group(3)), int(mm.group(2)), int(mm.group(1))
    mm = re.search(r'\b(\d{2})(\d{2})(\d{4})\b', raw)
    if mm: return int(mm.group(1)), int(mm.group(2)), int(mm.group(3))
    nums = numbers_tr(txt); d = y = None
    for n in nums:
        if n >= 1900 and y is None: y = n
        elif 1 <= n <= 31 and d is None: d = n
        elif m is None and 1 <= n <= 12: m = n
    return d, m, y
def readback(p, a, d):
    vars['c_amount'] = a; vars['c_date'] = d.isoformat(); vars['st'] = 'confirm'
    return pname(p) + ' için ' + amt(a) + ' tutarında, ' + dsay(d) + ' ödeme yapacaksınız. Onaylıyor musunuz?'
def offer_text(a, d):
    return pname(cur()) + ' için ' + amt(a) + ' tutarındaki ödemeyi ' + dsay(d) + ' yapabilir misiniz?'
def set_offer(a, d):
    vars['o_amount'] = a; vars['o_date'] = d.isoformat()
def announce(prefix):
    p = cur(); b, dl, fl = facts(p)
    vars['st'] = 'pay'; vars['ref'] = 0; vars['floor_off'] = 0; vars['too_high'] = 0; vars['vague'] = 0; vars['dl_off'] = 0
    set_offer(float(p.get('past_due') or 0), today)
    return (prefix + ploc(p) + ' ' + amt(p.get('past_due')) + ' vadesi geçmiş tutar var ve ' + str(p.get('days_late')) + ' gündür gecikmiş durumda. Bu ödemeyi bugün yapabilir misiniz?')
def next_product(prefix):
    vars['pi'] = I('pi') + 1
    if cur() is None:
        if I('promised') > 0: return close('promise', prefix)
        return close('refused', prefix)
    return ask(prefix + ' ' + announce('Ayrıca '))
def refusal(prefix=''):
    p = cur(); b, dl, fl = facts(p)
    vars['ref'] = I('ref') + 1; r = I('ref')
    if r > b['attempts']:
        if len(products()) > I('pi') + 1: return next_product((prefix + ' Anlıyorum.').strip())
        return close('refused', (prefix + ' Anlıyorum.').strip())
    if r == 1:
        a = fl if I('too_high') else float(p.get('past_due') or 0); d = week_offer()
    else:
        a = fl; d = dl
    if a == float(S('o_amount') or -1) and d.isoformat() == S('o_date'):
        return close('refused', (prefix + ' Anlıyorum.').strip())
    set_offer(a, d)
    return ask((prefix + ' ' + offer_text(a, d)).strip())
def proposal(prefix, dw, aw):
    p = cur(); b, dl, fl = facts(p); due = float(p.get('past_due') or 0)
    a = amount_tr(aw) if aw else None
    if a is None: a = float(S('o_amount') or due)
    if a > due: a = due
    if a < fl - 0.001:
        if not I('floor_off'):
            vars['floor_off'] = 1; d0 = to_date(S('o_date')) or today; set_offer(fl, d0)
            return ask((prefix + ' Bu tutarı kaydedemiyorum. En az ' + amt(fl) + ' ödemeniz gerekiyor; kalan kısım vadesi geçmiş olarak kalacaktır. ' + offer_text(fl, d0)).strip())
        return refusal(prefix)
    if dw:
        d, kind = resolve_phrase_tr(dw, today)
        if d is None:
            if not I('vague'):
                vars['vague'] = 1; vars['o_amount'] = a
                return ask((prefix + ' Hangi gün ödeme yapabileceğinizi tam olarak söyler misiniz?').strip())
            set_offer(a, dl); vars['dl_off'] = 1
            return ask((prefix + ' ' + offer_text(a, dl)).strip())
    else:
        d = to_date(S('o_date')) or today
    stt = promise_date_state(d, today, dl, H)
    if stt == 'past':
        return ask((prefix + ' Ödeme tarihi bugün veya daha sonra olmalı. Hangi gün ödeme yapabilirsiniz?').strip())
    if stt == 'not_business_day':
        nd = on_or_after_bd(d, H)
        if nd > dl: nd = dl
        set_offer(a, nd)
        return ask((prefix + ' ' + say_date_tr(d) + ' bir iş günü değil. ' + offer_text(a, nd)).strip())
    if stt == 'after_deadline':
        set_offer(a, dl); vars['dl_off'] = 1
        return ask((prefix + ' Kaydedebileceğim en geç tarih ' + say_date_tr(dl) + '. ' + offer_text(a, dl)).strip())
    return ask((prefix + ' ' + readback(p, a, d)).strip())

def main():
    st = S('st', 'start')
    if st == 'closed':
        vars['action'] = 'end'; return
    if st == 'start':
        vars['st'] = 'confirm_id'; vars['outcome'] = ''; vars['reason'] = ''
        return ask('Merhaba, Freya Bank\'tan arayan bir dijital asistanım. Bu görüşme kaydediliyor. ' + TITLE + ' ile mi görüşüyorum?')
''' + "    " + "\n    ".join(__import__('snippets').loop_guard('service_error', 40).splitlines()) + r'''
    pend = S('pending', '')
    vars['pending'] = ''
    # ---------- tool results ----------
    if pend:
        okv = T(S('r_ok')); code_ = str(S('r_status', ''))
        if pend == 'verify':
            ver = str(S('r_verified', 'none')).lower()
            if ver in ('true', 'false'):
                vars['vfail'] = 0
                if ver == 'true':
                    if S('v_field') == 'date_of_birth':
                        vars['st'] = 'phone'; vars['ph'] = ''
                        return ask('Teşekkür ederim. Şimdi kayıtlı telefon numaranızın son dört hanesini alabilir miyim?')
                    vars['st'] = 'account'; vars['pending'] = 'account'; vars['r_ok'] = 'pending'
                    return ask('', 'account')
                if str(S('r_hint', '')) == 'day_month_swapped':
                    vars['dd'] = ''; vars['dm'] = ''; vars['dy'] = ''
                    return ask('Ayı kelimeyle söyler misiniz? Örneğin on dört mart bin dokuz yüz seksen beş gibi.')
                vars['wrong'] = I('wrong') + 1
                left = str(S('r_left', ''))
                if I('wrong') >= SPEC['max_wrong'] or left == '0':
                    return close('failed', 'Kimliğinizi doğrulayamadım. Lütfen mobil uygulamamızı kullanın veya bir şubemize başvurun.')
                if S('v_field') == 'date_of_birth':
                    vars['dd'] = ''; vars['dm'] = ''; vars['dy'] = ''
                    return ask('Bu yanıt kayıtlarımızla eşleşmedi. Doğum tarihinizi tekrar söyler misiniz?')
                vars['ph'] = ''
                return ask('Bu yanıt kayıtlarımızla eşleşmedi. Telefon numaranızın son dört hanesini tekrar söyler misiniz?')
            if code_.startswith('2') and S('v_field') == 'date_of_birth' and str(S('r_ok')).lower() == 'false':
                vars['dd'] = ''; vars['dm'] = ''; vars['dy'] = ''
                return ask('Tarihi anlayamadım. Doğum tarihinizi gün, ay ve yıl olarak söyler misiniz?')
            vars['vfail'] = I('vfail') + 1
            if I('vfail') >= 2: return close('service_error', 'Şu anda sistemimizde bir sorun var, işleminizi tamamlayamıyorum.')
            vars['pending'] = 'verify'; vars['r_ok'] = 'pending'; vars['r_verified'] = 'none'; vars['r_hint'] = 'none'
            return ask(TECH, 'verify')
        if pend == 'account':
            ps = products()
            if okv and ps:
                vars['pi'] = 0
                return ask(announce('Teşekkür ederim, doğrulama tamamlandı. Tahsilat ekibinden, gecikmiş bir ödemeniz nedeniyle arıyorum. '))
            if okv and not ps:
                return close('refused', 'Teşekkür ederim. Hesabınızda gecikmiş bir ödeme görünmüyor.')
            vars['afail'] = I('afail') + 1
            if I('afail') >= 2: return close('service_error', 'Şu anda sistemimizde bir sorun var, hesap bilgilerinize ulaşamıyorum.')
            vars['pending'] = 'account'; vars['r_ok'] = 'pending'
            return ask(TECH, 'account')
        if pend == 'promise':
            if okv:
                vars['promised'] = I('promised') + 1; vars['pfail'] = 0
                msg = 'Ödeme sözünüz kaydedilmiştir. Bu ödeme sözünü doğrulayan bir kısa mesaj alacaksınız.'
                if len(products()) > I('pi') + 1: return next_product(msg)
                return close('promise', msg)
            vars['pfail'] = I('pfail') + 1
            if I('pfail') >= 2:
                return close('service_error', 'Ödeme sözünüzü kaydedemedim.')
            vars['pending'] = 'promise'; vars['r_ok'] = 'pending'
            return ask(TECH, 'promise')
        if pend == 'callback':
            if okv:
                return close('callback', 'Teşekkür ederim, ' + dsay(to_date(S('cb_date'))) + ' saat ' + S('cb_time').replace(':', '.') + ' için geri arama planladım.')
            vars['cfail'] = I('cfail') + 1
            if I('cfail') >= 2: return close('no_callback', 'Geri aramayı planlayamadım.')
            vars['pending'] = 'callback'; vars['r_ok'] = 'pending'
            return ask(TECH, 'callback')
        if pend == 'transfer':
            if okv or I('tfail') >= 1:
                return close(S('t_reason'), 'Sizi ilgili ekibimize bağlıyorum.')
            vars['tfail'] = 1; vars['pending'] = 'transfer'; vars['r_ok'] = 'pending'
            return ask(TECH, 'transfer')
    # ---------- customer turn ----------
    who = fresh('x_who'); rep = fresh('x_reply'); req = fresh('x_request'); q = fresh('x_question')
    dw = fresh('x_date_words'); tw = fresh('x_time_words'); aw = fresh('x_amount_words')
    bw = fresh('x_dob_words'); gw = fresh('x_digits')
    for k in ('x_who','x_reply','x_request','x_question','x_date_words','x_time_words','x_amount_words','x_dob_words','x_digits'):
        vars[k] = 'none'
    pre = ''
    if q == 'robot': pre = 'Ben Freya Bank\'ın dijital asistanıyım.'
    elif q == 'scam': pre = 'Bu aramayı Freya Bank müşteri hizmetleri numarasını arayarak doğrulayabilirsiniz.'
    elif q == 'other': pre = 'Bu bilgiye sahip değilim.'
    def transfer(queue, reason, say=''):
        if I('t_done'): return close(reason, say)
        vars['t_done'] = 1; vars['t_queue'] = queue; vars['t_reason'] = reason
        vars['pending'] = 'transfer'; vars['r_ok'] = 'pending'
        return ask(say, 'transfer')
    # human request (rule 42), every stage
    if req == 'human' and st not in ('tp_when',):
        if I('human_asked'): return transfer('general', 'human', 'Tabii, sizi genel hatta bağlıyorum.')
        vars['human_asked'] = 1
        return ask((pre + ' Size yardımcı olabilir miyim?').strip())
    if st == 'confirm_id':
        if who == 'deceased': return close('deceased', 'Başınız sağ olsun.')
        if who == 'wrong_number': return close('wrong_number', 'Özür dilerim, rahatsız ettim.')
        if who == 'other_person' or rep == 'no':
            vars['st'] = 'tp_when'; st = 'tp_when'
            if not (dw or tw): return ask('Anladım. ' + TITLE + ' ile ne zaman görüşebiliriz?')
        elif who == 'self' or rep == 'yes':
            vars['st'] = 'dob'; vars['dd'] = ''; vars['dm'] = ''; vars['dy'] = ''
            return ask((pre + ' Teşekkür ederim. Güvenliğiniz için iki soru soracağım. Doğum tarihinizi söyler misiniz?').strip())
        else:
            if req in ('refuse', 'refuse_talk'):  # rule 45: the second refusal closes, before verification as declined
                vars['talk_ref'] = I('talk_ref') + 1
                if I('talk_ref') >= 2: return close('declined', 'Anlıyorum.')
                return ask((pre + ' Anlıyorum. ' + TITLE + ' ile mi görüşüyorum?').strip())
            vars['id_asks'] = I('id_asks') + 1
            if I('id_asks') >= 2: return close('unclear', 'Sizi anlayamadım.')
            if q == 'what': pre = 'Size Freya Bank adına ulaşıyorum; ayrıntıları yalnızca kendisiyle paylaşabilirim.'
            return ask((pre + ' ' + TITLE + ' ile mi görüşüyorum?').strip())
    if st == 'tp_when':
        if who == 'deceased': return close('deceased', 'Başınız sağ olsun.')
        if who == 'wrong_number': return close('wrong_number', 'Özür dilerim, rahatsız ettim.')
        if not (dw or tw):
            if rep == 'no' or req == 'refuse':
                return close('no_callback', 'Anlıyorum.')
            vars['tp_asks'] = I('tp_asks') + 1
            if I('tp_asks') >= 3: return close('no_callback', 'Anlıyorum.')
            return ask('Bugün veya bir sonraki iş günü, saat 10.00 ile 18.00 arasında hangi saatte ulaşabiliriz?')
        d, kind = resolve_phrase_tr(dw or tw, today)
        if d is None: d = today
        hh = hhmm_from_words_tr(tw or dw)
        if not hh: return ask('Saat kaçta ulaşabiliriz?')
        cs = callback_state(d, hh, now, SPEC['callback_start'], SPEC['callback_end'], H)
        if cs == 'ok':
            vars['cb_date'] = d.isoformat(); vars['cb_time'] = hh
            vars['pending'] = 'callback'; vars['r_ok'] = 'pending'
            return ask('', 'callback')
        vars['cb_bad'] = I('cb_bad') + 1
        if I('cb_bad') >= 2: return close('no_callback', 'Bu zaman için randevu oluşturamıyorum.')
        return ask('Bu zaman uygun değil. Bugün veya bir sonraki iş günü, saat 10.00 ile 18.00 arasında başka bir zaman söyleyebilir misiniz?')
    if st in ('dob', 'phone'):
        if who == 'wrong_number': return close('wrong_number', 'Özür dilerim, rahatsız ettim.')
        if who == 'deceased': return close('deceased', 'Başınız sağ olsun.')
        if req in ('refuse', 'refuse_talk') or q == 'what':
            vars['decl'] = I('decl') + 1
            if req == 'refuse_talk': vars['talk_ref'] = I('talk_ref') + 1
            if I('decl') >= 2 or I('talk_ref') >= 2: return close('declined', 'Anlıyorum. Kimliğinizi doğrulayamadığım için bilgi paylaşamıyorum.')
            qq = 'Doğum tarihinizi söyler misiniz?' if st == 'dob' else 'Telefon numaranızın son dört hanesini söyler misiniz?'
            return ask((pre + ' Bu sorular hesabınızı korumak içindir. ' + qq).strip())
        if st == 'dob':
            src = bw or dw or gw
            if src:
                d0, m0, y0 = dob_parse(src)
                if d0: vars['dd'] = d0
                if m0: vars['dm'] = m0
                if y0: vars['dy'] = y0
            dd, dm, dy = I('dd'), I('dm'), I('dy')
            if dd and dm and dy:
                vars['v_field'] = 'date_of_birth'; vars['v_answer'] = '%04d-%02d-%02d' % (dy, dm, dd)
                vars['pending'] = 'verify'; vars['r_ok'] = 'pending'; vars['r_verified'] = 'none'; vars['r_hint'] = 'none'
                return ask(pre, 'verify')
            if not (dd or dm or dy): return ask((pre + ' Doğum tarihinizi gün, ay ve yıl olarak söyler misiniz?').strip())
            miss = 'yılı' if not dy else ('ayı' if not dm else 'günü')
            return ask((pre + ' Teşekkürler. Doğum tarihinizin ' + miss + ' nedir?').strip())
        src = gw or bw
        dg = digits_tr(src) if src else ''
        if not dg and src: dg = ''.join(re.findall(r'\d', src))
        ph = (str(S('ph', '')) + dg)[-4:] if len(str(S('ph', '')) + dg) >= 4 else str(S('ph', '')) + dg
        vars['ph'] = ph
        if len(ph) == 4:
            vars['v_field'] = 'phone_last4'; vars['v_answer'] = ph
            vars['pending'] = 'verify'; vars['r_ok'] = 'pending'; vars['r_verified'] = 'none'; vars['r_hint'] = 'none'
            return ask(pre, 'verify')
        if ph: return ask((pre + ' Teşekkürler. Kalan rakamları söyler misiniz?').strip())
        return ask((pre + ' Kayıtlı telefon numaranızın son dört hanesini söyler misiniz?').strip())
    if cur() is None:
        return close('refused', '')
    p = cur(); b, dl, fl = facts(p)
    if st == 'hardship':
        if dw or aw: return proposal(pre, dw, aw)
        if rep == 'yes': return transfer('support', 'support', 'Sizi destek ekibimize bağlıyorum.')
        if rep == 'no' or req == 'refuse': return close('hardship', 'Anlıyorum.')
        return ask((pre + ' Sizi destek ekibimize bağlamamı ister misiniz?').strip())
    # pay / confirm stages
    if req == 'paid':
        return close('paid', 'Ödemelerin hesapta görünmesi bir iş günü sürebilir. Bu nedenle sizden şimdi bir ödeme sözü almayacağım.')
    if req == 'dispute':
        return close('dispute', 'Anlıyorum, bu konuyu sizinle tartışmayacağım ve bir ödeme sözü almayacağım.')
    if req == 'plan':
        return transfer('restructuring', 'restructuring', 'Bunun için sizi yapılandırma ekibimize bağlıyorum.')
    if st == 'confirm':
        if rep == 'yes' and not (dw or aw):
            if I('pdone_%d' % I('pi')): return ask('Bu söz zaten kaydedildi; değişiklik için mobil uygulamamızı kullanabilirsiniz.')
            vars['pdone_%d' % I('pi')] = 1
            vars['product_id'] = p.get('product_id'); vars['amount'] = S('c_amount'); vars['pdate'] = S('c_date')
            vars['pending'] = 'promise'; vars['r_ok'] = 'pending'
            return ask(pre, 'promise')
        if dw or aw:
            set_offer(float(S('c_amount')), to_date(S('c_date')))
            return proposal(pre, dw, aw)
        if rep == 'no' or req in ('refuse', 'cant_today'):
            vars['st'] = 'pay'
            return refusal(pre)
        return ask((pre + ' ' + readback(p, float(S('c_amount')), to_date(S('c_date')))).strip())
    # st == pay
    if dw or aw:
        return proposal(pre, dw, aw)
    if req == 'hardship':
        vars['st'] = 'hardship'
        return ask('Bunu duyduğuma çok üzüldüm. Sizi destek ekibimize bağlamamı ister misiniz?')
    if req == 'too_high':
        vars['too_high'] = 1
        if not I('floor_off'):
            vars['floor_off'] = 1; d0 = to_date(S('o_date')) or today; set_offer(fl, d0)
            return ask((pre + ' Anlıyorum. ' + offer_text(fl, d0) + ' Kalan kısım vadesi geçmiş olarak kalacaktır.').strip())
        return refusal(pre)
    if req == 'discount':
        return ask((pre + ' Politikamızda indirim, borç silme ya da farklı bir şart bulunmuyor. ' + offer_text(float(S('o_amount')), to_date(S('o_date')) or today)).strip())
    if rep == 'yes':
        return ask((pre + ' ' + readback(p, float(S('o_amount')), to_date(S('o_date')) or today)).strip())
    if req == 'refuse_talk':
        vars['talk_ref'] = I('talk_ref') + 1
        if I('talk_ref') >= 2: return close('refused', 'Anlıyorum.')
        return refusal(pre)
    if rep == 'no' or req in ('refuse', 'cant_today'):
        return refusal(pre)
    if q == 'what':
        return ask('Gecikmiş bir ödeme nedeniyle arıyorum. ' + ploc(p) + ' ' + amt(p.get('past_due')) + ' vadesi geçmiş tutar var. ' + offer_text(float(S('o_amount')), to_date(S('o_date')) or today))
    if pre:
        return ask(pre + ' ' + offer_text(float(S('o_amount')), to_date(S('o_date')) or today))
    vars['silent'] = I('silent') + 1
    if I('silent') >= 3: return refusal('')
    return ask('Anlayamadım. ' + offer_text(float(S('o_amount')), to_date(S('o_date')) or today))
try:
    main()
except Exception as e:
    vars['err'] = str(e)[:200]
    if vars.get('st') != 'closed':
        vars['say'] = 'Teknik bir sorun oldu. ' + BYE if False else 'Özür dilerim, tekrar eder misiniz?'
        vars['action'] = 'talk'
'''
STEP = code(BODY, SPEC)

def tool(name, path, body, maxr=0):
    props = {k: ({"type": "number", "default": v} if k == "amount" else {"type": "string", "default": v}) for k, v in body.items()}
    return {"type": "function", "config": {"timeoutMs": 12000, "maxRetries": maxr},
            "function": {"name": name, "handler": "__function__:api_call", "description": name,
                         "parameters": {"type": "object", "properties": {
                             "url": {"type": "string", "default": B + path},
                             "method": {"type": "string", "default": "POST"},
                             "headers": {"type": "object", "properties": {"Content-Type": {"type": "string", "default": "application/json"}}},
                             "body": {"type": "object", "required": list(body), "properties": props}}}}}

def always(t): return {"target_node": t, "description": "always", "condition": {"operator": "always"}}
def eq(t, var, val): return {"target_node": t, "description": var + "=" + val, "condition": {"logic": "or", "conditions": [{"variable": var, "operator": "equals", "operand": val}]}}

ROUTES = [eq("api_verify", "action", "verify"), eq("api_account", "action", "account"), eq("api_promise", "action", "promise"),
          eq("api_callback", "action", "callback"), eq("api_transfer", "action", "transfer"), eq("end", "action", "end"), always("talk")]

def codenode(name, src, trans):
    return {"name": name, "node_type": "code", "passthrough": True, "passthrough_default_transition": trans[-1]["target_node"],
            "on_enter": {"type": "silent"},
            "pre_actions": [{"type": "function", "function": {"name": "code_exec", "handler": "__function__:code_exec",
                             "parameters": {"type": "object", "properties": {"code": {"type": "string", "default": src}, "timeout_ms": {"type": "number", "default": 20000}}}}}],
            "transitions": trans}

MAP = [{"path": "data.ok", "variable": "r_ok"}, {"path": "status_code", "variable": "r_status"}]
def apinode(name, t, extra=()):
    return {"name": name, "node_type": "api_request", "passthrough": True, "passthrough_default_transition": "step",
            "on_enter": {"type": "silent"}, "suppress_tool_results": True, "pre_actions": [t],
            "response_mapping": MAP + list(extra), "transitions": [always("step")]}

def ext(name, desc, enum=None):
    e = {"name": name, "type": "string", "description": desc, "min_confidence": 0.5}
    if enum: e["enum_values"] = enum
    return e

EXT = [
 ext("x_who", "Who is on the line, from the customer's LAST message only. self: they confirm they are the person asked for or say their own name. other_person: someone else (spouse, relative, colleague) says the person is not there or not them. wrong_number: the number does not belong to that person / they don't know them. deceased: the person has died. none: none of these.", ["none","self","other_person","wrong_number","deceased"]),
 ext("x_reply", "The customer's answer to the agent's last yes/no question, LAST message only. yes: evet, benim, buyurun, onaylıyorum, olur, tamam. no: hayır, olmaz, yapamam. 'Alo', 'devam edin', 'kimsiniz' are none. none: no yes/no answer.", ["none","yes","no"]),
 ext("x_request", "What the customer asks for or states in the LAST message. human: wants a human/yetkili/temsilci. paid: says they ALREADY paid this overdue amount (past). dispute: says the debt/product is not theirs, never had it, closed it in the past. plan: explicitly asks for instalments, a payment plan, restructuring or a lower instalment (naming a date they can pay on is NOT a plan). hardship: illness, a death in the family, or job loss. too_high: the full amount is too much for them. discount: asks for a discount or waiver. cant_today: cannot pay today without naming another date. refuse: refuses to pay or refuses to answer a question. refuse_talk: does not want to talk at all. none: otherwise.", ["none","human","paid","dispute","plan","hardship","too_high","discount","cant_today","refuse","refuse_talk"]),
 ext("x_question", "A question the customer asks in the LAST message. robot: asks if this is a robot / AI. scam: asks if this is fraud/scam. what: asks what the call is about or who is calling. other: any other question. none: no question.", ["none","robot","scam","what","other"]),
 ext("x_date_words", "The customer's own words naming a day or date for a payment or callback, copied as said (e.g. 'yarın', 'haftaya cuma', 'ayın yirmisi', '20 Ekim', 'maaşım yatınca'). Not a date of birth. 'none' if the LAST message names no day."),
 ext("x_time_words", "The customer's own words naming a clock time for a callback, as said (e.g. 'öğleden sonra üçte', 'saat 11', '15.30'). 'none' if the LAST message has no time."),
 ext("x_amount_words", "An amount of money the customer says they can pay, copied as said (e.g. '500 lira', 'bin iki yüz elli'). 'none' if the LAST message names no amount."),
 ext("x_dob_words", "Date-of-birth words or digits the customer says in the LAST message, copied as said (e.g. 'on dört mart bin dokuz yüz seksen beş', '14.03.1985', 'seksen beş'). 'none' if none."),
 ext("x_digits", "Digits of a phone number the customer says in the LAST message, copied as said (e.g. '3307', 'üç üç sıfır yedi'). 'none' if none."),
]

nodes = {
 "init": codenode("init", STEP, [always("talk")]),
 "talk": {"name": "talk", "node_type": "conversation", "on_enter": {"type": "tts", "text": "{{say}}"},
          "task_message": "Say exactly this text: \"{{say}}\". Never promise a transfer, a callback or any other action that the text does not state. No tool call is allowed.",
          "extraction_schema": EXT, "max_node_turns": 60, "max_turn_transition": "end", "transitions": [always("step")]},
 "step": codenode("step", STEP, ROUTES),
 "api_verify": apinode("api_verify", tool("verify_identity", "/verify_identity", {"customer_id": "{{customer_id}}", "field": "{{v_field}}", "answer": "{{v_answer}}"}),
                        [{"path": "data.verified", "variable": "r_verified"}, {"path": "data.hint", "variable": "r_hint"}, {"path": "data.wrong_answers_left", "variable": "r_left"}]),
 "api_account": apinode("api_account", tool("get_account", "/get_account", {"customer_id": "{{customer_id}}"}, 2),
                        [{"path": "data.products.%d.%s" % (i, f), "variable": "p%d_%s" % (i, f)} for i in range(4) for f in ["product_id","type","card_last4","past_due","days_late","minimum_payment","instalment_amount"]]),
 "api_promise": apinode("api_promise", tool("create_promise", "/create_promise", {"customer_id": "{{customer_id}}", "product_id": "{{product_id}}", "amount": "{{amount}}", "date": "{{pdate}}"})),
 "api_callback": apinode("api_callback", tool("schedule_callback", "/schedule_callback", {"customer_id": "{{customer_id}}", "date": "{{cb_date}}", "time": "{{cb_time}}"})),
 "api_transfer": apinode("api_transfer", tool("transfer_to_agent", "/transfer_to_agent", {"customer_id": "{{customer_id}}", "queue": "{{t_queue}}"})),
 "end": {"name": "end", "node_type": "end_call", "on_enter": {"type": "silent"}, "disable_inactivity_monitor": True, "transitions": [],
         "terminal": {"type": "function", "function": {"name": "call_closed", "handler": "__function__:end_call",
                      "parameters": {"type": "object", "properties": {"message_mode": {"type": "string", "default": "custom"}, "spoken_message": {"type": "string", "default": "{{say}}"}}}}}},
}
nodes["init"]["passthrough_default_transition"] = "talk"

close = tool("close_call", "/close_call", {"customer_id": "{{customer_id}}", "outcome": "{{outcome}}", "reason": "{{reason}}"}, 2)
close["config"]["alwaysRunsAt"] = ["end_of_call"]
close["function"]["parameters"]["properties"]["body"]["required"] = ["customer_id", "outcome"]
close["function"]["parameters"]["properties"]["body"]["properties"]["outcome"]["enum"] = ["promise","paid","transferred","no_promise","not_verified","not_reached"]
close["pre_process_code"] = close_pre_process(("no_promise", "service_error"), "outcome", "reason", "customer_id")

wf = {"initial_node": "init",
      "system_prompt": "Sen Freya Bank'ın Türkçe konuşan dijital asistanısın. Her zaman yalnızca sana verilen metni aynen söyle; kendi bilgi, söz veya eylem ekleme.",
      "nodes": nodes, "global_nodes": {}, "tools": [close],
      "test_variables": {"customer_id": "c_test", "first_name": "Daniel", "last_name": "Reyes", "title": "Mr", "now": "2026-10-14T11:00"}}
json.dump(wf, open("out/%s.workflow.json" % SLOT, "w"), ensure_ascii=False, indent=1)
print("ok", len(STEP))
