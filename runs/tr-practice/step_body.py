def B(x):
    return str(x).strip().lower() == 'true'

def close(key, say):
    o, r = SPEC['outcomes'][key]
    vars['outcome'] = o; vars['reason'] = r
    vars['say'] = say; vars['act'] = 'end'; vars['st'] = 'closed'
    return True

BYE = ' Teşekkür eder, iyi günler dilerim.'
TECH = 'Teknik bir sorun nedeniyle işleminizi tamamlayamadım.'

def talk(s):
    vars['say'] = s; vars['act'] = 'talk'
    return True

def tool(name):
    for k in ('r_ok', 'r_verified', 'r_all', 'r_hint', 'r_left', 'r_error'):
        vars[k] = ''
    vars['act'] = name; vars['pending'] = name
    return True

def num(x):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return None

def amt(x):
    x = float(x)
    return say_amount_tr(int(x) if x == int(x) else x)

def dsay(d):
    return say_date_tr(d)

def title_tr():
    return ('Bayan ' if str(vars.get('title') or '').lower().startswith('m') and str(vars.get('title') or '').lower() in ('ms', 'mrs', 'miss', 'ms.') else 'Bay ') + str(vars.get('last_name') or '')

def cb_end():
    t = to_date(vars.get('now')) or datetime.date.today()
    return SPEC['callback']['end_new'] if t >= to_date(SPEC['callback']['new_from']) else SPEC['callback']['end_old']

def product_name(p):
    ty = p.get('type')
    if ty == 'credit_card':
        return str(p.get('card_last4') or '') + ' ile biten kredi kartı'
    if ty == 'car_loan':
        return 'taşıt kredisi'
    return 'bireysel kredi'

def q_for(st):
    if st == 'confirm': return title_tr() + ' ile mi görüşüyorum?'
    if st == 'dob': return 'Doğum tarihinizi söyler misiniz?'
    if st == 'phone': return 'Kayıtlı telefon numaranızın son dört hanesini alabilir miyim?'
    if st == 'tp_when': return title_tr() + ' beye/hanıma ne zaman ulaşabiliriz?'
    if st == 'pay': return SPEC['today_question']
    if st in ('offer', 'readback', 'support_offer', 'human_offer', 'ask_day', 'ask_date_for_amount'):
        return vars.get('last_q') or ''
    return ''

def ask(prefix, st=None, q=None):
    if st: vars['st'] = st
    qq = q if q is not None else q_for(vars.get('st'))
    if q is not None: vars['last_q'] = q
    return talk((prefix + ' ' + qq).strip())

def side_answer(it):
    if it == 'robot': return 'Freya Bank\'ın dijital asistanıyım.'
    if it == 'scam': return 'Bu aramayı Freya Bank müşteri hizmetleri numarasını arayarak doğrulayabilirsiniz.'
    if it == 'other_question': return 'Bu bilgiye sahip değilim.'
    return ''

def today():
    return (parse_now(vars.get('now')) if vars.get('now') else datetime.datetime.now()).date()

def hol():
    return list(SPEC['holidays'])

def product():
    items = []
    try: items = items_from_keys(vars, 'products')
    except Exception: items = []
    if not items:
        try: items = items_from_vars(vars, ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'])
        except Exception: items = []
    return items[0] if items else None

def facts():
    p = product()
    if not p: return None
    dl = int(float(p.get('days_late') or 0))
    b = band_for(dl, SPEC['bands']) or (SPEC['bands'][0] if dl < 1 else SPEC['bands'][-1])
    t = today()
    vars['pid'] = str(p.get('product_id') or '')
    vars['past_due'] = float(p.get('past_due') or 0)
    fl = p.get(SPEC['floor_fields'].get(p.get('type'), 'instalment_amount'))
    vars['floor'] = float(fl) if fl not in (None, '') else vars['past_due']
    vars['deadline'] = add_bd(t, b['deadline_bd'], hol()).isoformat()
    vars['attempts_max'] = b['attempts']
    vars['band'] = b['name']
    vars['pname'] = product_name(p)
    vars['days_late'] = dl
    return p

def offer_amount():
    return vars['floor'] if vars.get('too_much') == 'yes' else vars['past_due']

def readback(a, d, prefix=''):
    vars['pa'] = a; vars['pdte'] = d.isoformat()
    q = vars['pname'] + ' için ' + amt(a) + ' tutarında, ' + dsay(d) + ' günü ödeme yapacaksınız. Onaylıyor musunuz?'
    return ask(prefix, 'readback', q)

def attempt(prefix=''):
    used = int(vars.get('attempts_used') or 0) + 1
    vars['attempts_used'] = used
    if used > int(vars.get('attempts_max') or 1):
        return close('refused', (prefix + ' Anlıyorum.' + BYE).strip())
    t = today(); H = hol()
    if used == 1:
        d = last_bd_of_week(t, H)
        if d <= t:
            d = last_bd_of_week(t + datetime.timedelta(days=7 - t.weekday()), H)
        a = offer_amount()
        if d > to_date(vars['deadline']): d = to_date(vars['deadline'])
    else:
        d = to_date(vars['deadline']); a = vars['floor']
        vars['floor_offered'] = 'yes'
    vars['oa'] = a; vars['od'] = d.isoformat()
    q = amt(a) + ' tutarını ' + dsay(d) + ' günü ödeyebilir misiniz?'
    if used == 2 or a == vars['floor'] and a < vars['past_due']:
        q = q + ' Kalan kısım vadesi geçmiş olarak kalacaktır.'
    return ask(prefix, 'offer', q)

def proposal(dw, aw, prefix=''):
    t = today(); H = hol(); dl = to_date(vars['deadline'])
    a = None
    if aw:
        a = amount_tr(aw)
    if a is None:
        a = vars.get('cur_amount') or offer_amount()
    a = float(a)
    if a > vars['past_due']: a = vars['past_due']
    if a < vars['floor']:
        if vars.get('floor_offered') == 'yes':
            return attempt(prefix + ' Bu tutarı kaydedemiyorum.')
        vars['floor_offered'] = 'yes'; vars['too_much'] = 'yes'
        vars['oa'] = vars['floor']; vars['od'] = (vars.get('cur_date') or '')
        return ask(prefix + ' Bu tutarı kaydedemiyorum. Kaydedebileceğim en düşük tutar ' + amt(vars['floor']) + '; kalan kısım vadesi geçmiş olarak kalacaktır.', 'offer',
                   'Bu tutarı ödeyebilir misiniz?')
    vars['cur_amount'] = a
    if not dw:
        if vars.get('cur_date'):
            return readback(a, to_date(vars['cur_date']), prefix)
        return ask(prefix, 'ask_day', 'Bu ödemeyi hangi gün yapabilirsiniz?')
    d, kind = resolve_phrase_tr(dw, t, 'following_week')
    if d is None:
        if vars.get('vague_asked') == 'yes':
            vars['oa'] = a; vars['od'] = dl.isoformat()
            return ask(prefix, 'offer', 'Bu durumda son tarih olan ' + dsay(dl) + ' gününü önerebilirim. ' + amt(a) + ' tutarını o gün ödeyebilir misiniz?')
        vars['vague_asked'] = 'yes'
        return ask(prefix, 'ask_day', 'Ödemeyi tam olarak hangi gün yapabilirsiniz?')
    s = promise_date_state(d, t, dl, H)
    if s == 'past':
        return ask(prefix + ' Geçmiş bir tarih için söz kaydedemiyorum.', 'ask_day', 'Ödemeyi hangi gün yapabilirsiniz?')
    if s == 'after_deadline':
        vars['oa'] = a; vars['od'] = dl.isoformat(); vars['deadline_offer'] = 'yes'
        return ask(prefix + ' Kaydedebileceğim en geç tarih ' + dsay(dl) + '.', 'offer', amt(a) + ' tutarını ' + dsay(dl) + ' günü ödeyebilir misiniz?')
    if s == 'not_business_day':
        nd = on_or_after_bd(d, H)
        vars['oa'] = a; vars['od'] = nd.isoformat()
        return ask(prefix + ' ' + dsay(d) + ' bir iş günü değil.', 'offer', 'Bir sonraki iş günü olan ' + dsay(nd) + ' günü ' + amt(a) + ' ödeyebilir misiniz?')
    vars['cur_date'] = d.isoformat()
    return readback(a, d, prefix)

def common(it, prefix):
    # requests the brief answers in every stage (rules 39-45, 32)
    verified = vars.get('verified') == 'yes'
    if it == 'human':
        n = int(vars.get('human_n') or 0) + 1; vars['human_n'] = n
        if n >= 2:
            vars['queue'] = SPEC['queues']['human']; vars['tkey'] = 'human'
            vars['tsay'] = 'Tabii, sizi genel hatta bağlıyorum.' + BYE
            return tool('transfer')
        return talk((prefix + ' Size yardımcı olabilir miyim?').strip())
    if it == 'refuse_talk':
        n = int(vars.get('notalk_n') or 0) + 1; vars['notalk_n'] = n
        if n >= 2:
            return close('refused' if verified else 'declined', 'Anlıyorum.' + BYE)
        return None
    return None

def main():
    st = vars.get('st') or 'confirm'
    pend = vars.get('pending') or ''
    if pend:
        vars['pending'] = ''
        return after_tool(pend)
    vars['loops'] = int(vars.get('loops') or 0) + 1
    if vars['loops'] > 40 and st != 'closed':
        return close('service_error', 'Üzgünüm, görüşmeye devam edemiyorum.' + BYE)
    it = str(vars.get('intent') or 'none')
    dw = str(vars.get('date_words') or '').strip()
    tw = str(vars.get('time_words') or '').strip()
    aw = str(vars.get('amount_words') or '').strip()
    sw = str(vars.get('answer_words') or '').strip()
    # consume the fields
    vars['intent'] = 'none'
    for k in ('date_words', 'time_words', 'amount_words', 'answer_words'):
        vars[k] = ''
    pre = side_answer(it) if it in ('robot', 'scam', 'other_question') else ''
    if st == 'confirm':
        if it == 'deceased':
            return close('deceased', 'Başınız sağ olsun. İyi günler dilerim.')
        if it == 'wrong_number':
            return close('wrong_number', 'Özür dilerim, iyi günler dilerim.')
        if it in ('third_party',):
            vars['st'] = 'tp_when'
            if dw or tw:
                return callback(dw, tw, 'Anladım.')
            return ask('Anladım.', 'tp_when', title_tr() + ' ile ne zaman görüşebiliriz?')
        if it == 'yes':
            vars['st'] = 'dob'
            return ask('Teşekkür ederim. Güvenliğiniz için iki soru soracağım.', 'dob')
        r = common(it, pre)
        if r: return r
        n = int(vars.get('confirm_n') or 1) + 1; vars['confirm_n'] = n
        if n > SPEC['confirm_asks_max'] and not pre:
            return close('unclear', 'Teşekkür eder, iyi günler dilerim.')
        if n > SPEC['confirm_asks_max'] + 1:
            return close('unclear', 'Teşekkür eder, iyi günler dilerim.')
        if it == 'what_about':
            pre = 'Bunu yalnızca ' + title_tr() + ' ile paylaşabilirim.'
        return ask(pre, 'confirm')
    if st == 'tp_when':
        if it == 'deceased':
            return close('deceased', 'Başınız sağ olsun. İyi günler dilerim.')
        if it == 'wrong_number':
            return close('wrong_number', 'Özür dilerim, iyi günler dilerim.')
        if dw or tw:
            return callback(dw, tw, pre)
        n = int(vars.get('cb_tries') or 0) + 1; vars['cb_tries'] = n
        if n >= 2 or it in ('no', 'refuse_talk'):
            return close('no_callback', 'Anlıyorum.' + BYE)
        return ask(pre, 'tp_when', 'Hangi gün ve saatte ulaşabiliriz?')
    if st in ('dob', 'phone'):
        r = common(it, pre)
        if r: return r
        if it in ('refuse', 'refuse_talk', 'what_about') and not sw:
            n = int(vars.get('decline_n') or 0) + 1; vars['decline_n'] = n
            if n >= 2:
                return close('declined', 'Anlıyorum. Kimliğinizi doğrulayamadığım için bilgi paylaşamıyorum.' + BYE)
            return ask('Bu sorular hesabınızı korumak içindir.', st)
        if not sw:
            return ask(pre, st)
        if st == 'dob':
            return dob_piece(sw, pre)
        dg = digits_tr(sw)
        sofar = str(vars.get('ph_sofar') or '') + dg
        if len(sofar) >= 4:
            vars['ph_sofar'] = ''
            vars['v_field'] = 'phone_last4'; vars['v_answer'] = sofar[-4:]
            return tool('verify')
        vars['ph_sofar'] = sofar
        if sofar:
            return ask(pre + ' Devamını alabilir miyim?', st, '')
        return ask(pre, st)
    # verified stages
    if it == 'hardship' and not (dw or aw) and vars.get('hardship') != 'yes':
        vars['hardship'] = 'yes'
        return ask(pre + ' Bunu duyduğuma çok üzüldüm.', 'support_offer', 'Sizi destek ekibimize bağlamamı ister misiniz?')
    if st == 'support_offer' and not (dw or aw):
        if it in ('yes', 'human'):
            vars['queue'] = SPEC['queues']['support']; vars['tkey'] = 'support'
            vars['tsay'] = 'Sizi destek ekibimize bağlıyorum.' + BYE
            return tool('transfer')
        if it in ('no', 'refuse', 'refuse_talk'):
            return close('hardship', 'Anlıyorum.' + BYE)
        return ask(pre, 'support_offer')
    if it == 'paid' and not dw.startswith('x'):
        return close('paid', 'Ödemelerin hesapta görünmesi bir iş günü sürebilir. Bu nedenle sizden şimdi bir ödeme sözü almayacağım.' + BYE)
    if it == 'dispute':
        return close('dispute', 'Anlıyorum, bu konuyu sizinle tartışmayacağım.' + BYE)
    if it == 'plan':
        vars['queue'] = SPEC['queues']['restructuring']; vars['tkey'] = 'restructuring'
        vars['tsay'] = 'Sizi yapılandırma ekibimize bağlıyorum.' + BYE
        return tool('transfer')
    if st == 'readback':
        if it == 'yes' and not (dw or aw):
            vars['v_product_id'] = vars['pid']; vars['v_amount'] = vars['pa']; vars['v_date'] = vars['pdte']
            return tool('promise')
        if dw or aw:
            if not dw: vars['cur_date'] = vars['pdte']
            return proposal(dw, aw, pre)
    if st == 'offer' and it == 'yes' and not (dw or aw):
        vars['cur_amount'] = vars['oa']
        return readback(vars['oa'], to_date(vars['od']) or today(), pre)
    if dw or aw:
        if st == 'pay' and not dw and aw: vars['cur_date'] = ''
        return proposal(dw, aw, pre)
    if st == 'pay' and it == 'yes':
        vars['cur_amount'] = offer_amount()
        return readback(offer_amount(), today(), pre)
    r = common(it, pre)
    if r: return r
    if it == 'too_much':
        if vars.get('floor_offered') != 'yes':
            vars['too_much'] = 'yes'; vars['floor_offered'] = 'yes'
            vars['oa'] = vars['floor']; vars['od'] = (vars.get('od') or today().isoformat()) if st == 'offer' else today().isoformat()
            return ask(pre + ' Anlıyorum. Asgari olarak ' + amt(vars['floor']) + ' ödemeniz mümkün; kalan kısım vadesi geçmiş olarak kalacaktır.', 'offer',
                       amt(vars['floor']) + ' tutarını ' + dsay(to_date(vars['od'])) + ' günü ödeyebilir misiniz?')
        return attempt(pre)
    if it == 'discount':
        return ask(pre + ' Size indirim veya farklı bir şart sunamıyorum.', st if st != 'pay' else 'pay', vars.get('last_q') if st != 'pay' else None)
    if it in ('no', 'refuse', 'refuse_talk') or (it == 'none' and not pre and st in ('pay', 'offer', 'readback')):
        if it == 'none' and st == 'readback':
            return ask('', 'readback', vars.get('last_q'))
        if st == 'ask_day' and vars.get('vague_asked') == 'yes':
            return proposal('', '', pre) if False else attempt(pre)
        return attempt(pre)
    if st == 'ask_day':
        return proposal('', '', pre) if vars.get('cur_date') else ask(pre, 'ask_day', vars.get('last_q'))
    if it == 'what_about':
        pre = (pre + ' Gecikmiş bir ödemeniz nedeniyle arıyorum.').strip()
    return ask(pre, st, None if st == 'pay' else vars.get('last_q'))

def callback(dw, tw, pre):
    t = today(); now = parse_now(vars.get('now')) if vars.get('now') else datetime.datetime.now()
    d = None
    if dw:
        d, k = resolve_phrase_tr(dw, t)
    hh = hhmm_from_words_tr(tw or dw)
    if not hh:
        HW = {'bir':1,'iki':2,'uc':3,'dort':4,'bes':5,'alti':6,'yedi':7,'sekiz':8,'dokuz':9,'on':10}
        tt = tr_ascii(tw or dw).split()
        for i, tok in enumerate(tt):
            for w in sorted(HW, key=len, reverse=True):
                if tok.startswith(w) and len(tok) - len(w) <= 3:
                    h = HW[w]
                    if w == 'on' and i + 1 < len(tt) and tt[i+1][:3] in ('bir', 'iki'):
                        h = 11 if tt[i+1].startswith('bir') else 12
                    if re.search('ogleden sonra|aksam', ' '.join(tt)) and h < 12: h += 12
                    hh = '%02d:%02d' % (h, 30 if 'bucuk' in tt else 0)
                    break
            if hh: break
    if hh and int(hh[:2]) < 8 and not re.search('sabah|gece', tr_ascii(tw or dw)):
        hh = '%02d:%s' % (int(hh[:2]) + 12, hh[3:])
    if d is None: d = t
    if not hh:
        n = int(vars.get('cb_tries') or 0) + 1; vars['cb_tries'] = n
        if n >= 3: return close('no_callback', 'Anlıyorum.' + BYE)
        return ask(pre, 'tp_when', 'Saat kaçta ulaşabiliriz?')
    s = callback_state(d, hh, now, SPEC['callback']['start'], cb_end(), hol())
    if s == 'ok':
        vars['v_cb_date'] = d.isoformat(); vars['v_cb_time'] = hh
        vars['cb_say'] = 'Teşekkür ederim, ' + dsay(d) + ' saat ' + hh.replace(':', '.') + ' için geri arama planladım. İyi günler dilerim.'
        return tool('callback')
    n = int(vars.get('cb_out') or 0) + 1; vars['cb_out'] = n
    if n >= 2:
        return close('no_callback', 'Anlıyorum, o zaman için randevu oluşturamıyorum.' + BYE)
    return ask(pre + ' O zaman için arayamıyoruz.', 'tp_when', 'Bugün ya da bir sonraki iş günü, saat ' + SPEC['callback']['start'].replace(':', '.') + ' ile ' + cb_end().replace(':', '.') + ' arasında bir zaman söyleyebilir misiniz?')

def dob_piece(sw, pre):
    raw = sw; t = tr_ascii(sw)
    mon = None
    for i, n in enumerate(_MON_TR):
        if re.search(r'\b' + n, t): mon = i + 1; break
    nums = [int(x) for x in re.findall(r'\d+', raw)]
    if not nums:
        nums = numbers_tr(sw)
    d = vars.get('dob_d'); m = vars.get('dob_m'); y = vars.get('dob_y')
    if vars.get('swap') == 'yes' and mon:
        vars['swap'] = ''
        d = vars.get('dob_m'); m = mon
    else:
        if mon: m = mon
        rest = []
        for n in nums:
            if n >= 1900 and n <= 2030: y = n
            elif 30 <= n <= 99 and y in (None, ''): y = 1900 + n
            else: rest.append(n)
        for n in rest:
            if (d in (None, '')) and 1 <= n <= 31: d = n
            elif (m in (None, '')) and 1 <= n <= 12: m = n
    vars['dob_d'] = d if d is not None else ''; vars['dob_m'] = m if m is not None else ''; vars['dob_y'] = y if y is not None else ''
    if d in (None, ''): return ask(pre + ' Doğduğunuz günü de söyler misiniz?', 'dob', '')
    if m in (None, ''): return ask(pre + ' Hangi ay?', 'dob', '')
    if y in (None, ''): return ask(pre + ' Ve doğum yılınız?', 'dob', '')
    try:
        dd = datetime.date(int(y), int(m), int(d))
    except Exception:
        vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''
        return ask(pre + ' Tarihi anlayamadım.', 'dob')
    vars['v_field'] = 'date_of_birth'; vars['v_answer'] = dd.isoformat()
    return tool('verify')

def after_tool(p):
    ok = B(vars.get('r_ok'))
    if p == 'verify':
        if vars.get('r_ok') in ('', None):
            n = int(vars.get('verify_fail') or 0) + 1; vars['verify_fail'] = n
            if n >= 2: return close('service_error', TECH + BYE)
            return tool('verify')
        if B(vars.get('r_all')):
            vars['verified'] = 'yes'
            return tool('account')
        if B(vars.get('r_verified')):
            if vars.get('v_field') == 'date_of_birth':
                return ask('Teşekkür ederim.', 'phone')
            return tool('account') if vars.get('dob_ok') == 'yes' else ask('Teşekkür ederim.', 'dob')
        if str(vars.get('r_hint') or '') == 'day_month_swapped':
            vars['swap'] = 'yes'
            return ask('Doğum ayınızı kelimeyle söyler misiniz? Örneğin mart gibi.', 'dob', '')
        if not ok and str(vars.get('r_verified')) in ('', 'None'):
            vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''
            return ask('Tarihi anlayamadım.', vars.get('st'))
        w = int(vars.get('wrong') or 0) + 1; vars['wrong'] = w
        left = vars.get('r_left')
        if w >= SPEC['wrong_answers_max'] or str(left) == '0':
            return close('failed', 'Kimliğinizi doğrulayamadım. Lütfen mobil uygulamamızı kullanın veya bir şubemize başvurun.' + BYE)
        vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''; vars['ph_sofar'] = ''
        return ask('Bu yanıt kayıtlarımızla eşleşmedi.', vars.get('st'))
    if p == 'account':
        pr = facts() if ok or vars.get('r_ok') in ('', None) else None
        if not pr:
            n = int(vars.get('acct_fail') or 0) + 1; vars['acct_fail'] = n
            if n >= 2: return close('service_error', TECH + BYE)
            return tool('account')
        s = ('Teşekkür ederim, doğrulama tamamlandı. Tahsilat ekibinden, gecikmiş bir ödemeniz nedeniyle arıyorum. ' + vars['pname'].capitalize() + ' için '
             + amt(vars['past_due']) + ' vadesi geçmiş tutar var ve ' + str(vars['days_late']) + ' gündür gecikmiş durumda.')
        return ask(s, 'pay')
    if p == 'promise':
        if ok:
            vars['promised'] = 'yes'
            return close('promise', 'Ödeme sözünüz kaydedildi. ' + SPEC['sms_sentence'] + BYE)
        n = int(vars.get('promise_fail') or 0) + 1; vars['promise_fail'] = n
        if n >= 2: return close('service_error', 'Teknik bir sorun nedeniyle ödeme sözünüzü kaydedemedim.' + BYE)
        return tool('promise')
    if p == 'callback':
        if ok:
            return close('callback', vars.get('cb_say'))
        n = int(vars.get('cb_fail') or 0) + 1; vars['cb_fail'] = n
        if n >= 2: return close('no_callback', TECH + BYE)
        return tool('callback')
    if p == 'transfer':
        if ok:
            return close(vars.get('tkey'), vars.get('tsay'))
        n = int(vars.get('tr_fail') or 0) + 1; vars['tr_fail'] = n
        if n >= 2: return close('service_error', TECH + BYE)
        return tool('transfer')
    return talk('')

try:
    if vars.get('v_field') == 'phone_last4' and False: pass
    if vars.get('pending') == 'verify' and vars.get('v_field') == 'date_of_birth' and B(vars.get('r_verified')):
        vars['dob_ok'] = 'yes'
    main()
except Exception as e:
    vars['err'] = str(e)[:200]
    if vars.get('act') not in ('talk', 'end'):
        vars['act'] = 'talk'
    if not vars.get('say'): vars['say'] = 'Özür dilerim, tekrar eder misiniz?'
    vars['act'] = 'talk'
