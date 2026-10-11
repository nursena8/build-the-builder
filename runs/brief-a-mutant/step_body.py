import datetime as _dt
SN = SPEC['sentences']
HOL = SPEC['holidays']
def S(k):
    x = vars.get(k)
    return '' if x is None else str(x)
def I(k):
    try: return int(float(vars.get(k) or 0))
    except Exception: return 0
def F(k):
    try: return float(vars.get(k))
    except Exception: return 0.0
def money(x): return '%.2f' % float(x)
def tl(): return S('title') + ' ' + S('last_name')
def setv(**kw):
    for k, v in kw.items(): vars[k] = v
def talk(say, st=None):
    vars['say'] = say; vars['next_node'] = 'talk'
    if st: vars['st'] = st
def close(key, say):
    o = SPEC['outcomes'][key]
    vars['outcome'] = o[0]; vars['reason'] = o[1]
    vars['closing_say'] = say + ' Thank you, goodbye.'; vars['next_node'] = 'end'; vars['st'] = 'closed'
def transfer(key, queue, say):
    vars['queue'] = queue; vars['tr_key'] = key; vars['tr_say'] = say; vars['next_node'] = 'transfer'; vars['st'] = 'tr_res'
def lastask(): return S('ask')
def ask(text, st=None):
    vars['ask'] = text; talk(text if not S('prefix') else S('prefix') + ' ' + text, st)
def okv(k): return S(k).lower() == 'true'

now = parse_now(vars.get('now')); today = now.date()
st = S('st') or 'open'
intent = S('intent') or 'none'
dw = S('date_words').strip(); tw = S('time_words').strip(); aw = S('amount_words').strip()
vars['prefix'] = ''
vars['next_node'] = ''

def full(): return F('past_due')
def floor(): return F('floor')
def deadline(): return to_date(S('deadline'))
def default_date(): return on_or_after_bd(today, HOL)

def parse_amt(s):
    m = re.search(r'\d[\d,]*(?:\.\d+)?', s or '')
    if not m: return None
    try: return float(m.group(0).replace(',', ''))
    except Exception: return None

def to_confirm(note=''):
    amt = F('cur_amt'); d = to_date(S('cur_date'))
    vars['ask'] = 'Do you confirm?'
    talk((note + ' ' if note else '') + 'To confirm: ' + S('product_say') + ', ' + money(amt) + ' on ' + say_date(d) + '. Do you confirm?', 'confirm')

def flat_refusal():
    n = I('attempts_used') + 1; vars['attempts_used'] = n
    vars['noans'] = 0
    if n > I('attempts_total'):
        return close('refused', 'I understand. I will not take a promise today.')
    amt = floor() if I('full_too_much') else full()
    dl = deadline()
    if n == 1:
        d = last_bd_of_week(today, HOL)
        if d is None or d <= today: d = last_bd_of_week(today + _dt.timedelta(days=7), HOL)
        if d > dl: d = dl
    else:
        amt = floor(); d = dl
    key = money(amt) + '|' + d.isoformat()
    if key in S('offered').split(','):
        return close('refused', 'I understand. I will not take a promise today.')
    vars['offered'] = (S('offered') + ',' + key).strip(',')
    vars['cur_amt'] = amt; vars['cur_date'] = d.isoformat()
    extra = ' The rest stays overdue.' if amt < full() - 0.004 else ''
    ask('I understand. Could you pay ' + money(amt) + ' by ' + say_date(d) + '?' + extra, 'offer')

def handle_proposal(pre=''):
    amt = parse_amt(aw)
    if amt is not None:
        if amt > full() + 0.004: amt = full()
        if amt < floor() - 0.004:
            if I('floor_offered'): return flat_refusal()
            vars['floor_offered'] = 1
            vars['cur_amt'] = floor()
            if not S('cur_date'): vars['cur_date'] = default_date().isoformat()
            return ask(pre + ' That amount cannot be recorded. The lowest I can record is the minimum payment of ' + money(floor()) + ', and the rest stays overdue. Can you pay that on ' + say_date(to_date(S('cur_date'))) + '?', 'offer')
        vars['cur_amt'] = amt
    elif not S('cur_amt'):
        vars['cur_amt'] = full()
    note = pre
    dl = deadline(); d = None
    if dw:
        d0, kind = resolve_phrase(dw, today, SPEC['next_week_mode'])
        if d0 is not None:
            ds = promise_date_state(d0, today, dl, HOL)
            if ds == 'ok': d = d0
            elif ds == 'not_business_day':
                nb = on_or_after_bd(d0, HOL)
                if nb <= dl:
                    d = nb; note += ' ' + say_date(d0) + ' is not a business day. The next business day is ' + say_date(nb) + '.'
                else:
                    d = dl; note += ' The latest date I can record is ' + say_date(dl) + '.'
            elif ds == 'after_deadline':
                d = dl; note += ' The latest date I can record is ' + say_date(dl) + '.'
            else:
                d = default_date(); note += ' That day has already passed. The earliest is ' + say_date(d) + '.'
    if d is None and S('cur_date') and not dw:
        d = to_date(S('cur_date'))
    if d is None:
        if I('asked_exact') == 0:
            vars['asked_exact'] = 1
            return ask((pre + ' ' if pre else '') + 'On which exact day will you pay? Please give me the day and the date.', 'exact_day')
        d = dl; note += ' Then I will propose the latest possible date, ' + say_date(dl) + '.'
    vars['cur_date'] = d.isoformat()
    vars['noans'] = 0
    to_confirm(note.strip())

def common_questions():
    """robot / scam / unanswerable question: answer, then ask again. True when handled."""
    if intent == 'robot_question': vars['prefix'] = SN['robot']
    elif intent == 'scam_question': vars['prefix'] = SN['scam']
    elif intent == 'other_question': vars['prefix'] = SN['no_info']
    elif intent == 'terms_request': vars['prefix'] = 'I can only record a payment date and amount.'
    else: return False
    return True

def reask_debt():
    ask(lastask(), None)

def refusal_pre():
    vars['refusals'] = I('refusals') + 1
    if I('refusals') >= SPEC['id']['refusals_to_close']:
        return close('declined', 'I understand.')
    return None

# ---------------- states ----------------
def do_open():
    if intent == 'agree':
        vars['ask'] = SN['q_dob']
        return talk('Thank you. For security, I need to ask two short questions. ' + SN['q_dob'], 'dob')
    if intent == 'other_person':
        vars['ask'] = 'When can ' + tl() + ' be reached?'
        return talk('When can ' + tl() + ' be reached?', 'third')
    if intent == 'wrong_number': return close('wrong_number', 'I am sorry to have disturbed you.')
    if intent == 'deceased':
        o = SPEC['outcomes']['deceased']; vars['outcome'] = o[0]; vars['reason'] = o[1]
        vars['closing_say'] = SN['deceased'] + ' Goodbye.'; vars['next_node'] = 'end'; vars['st'] = 'closed'; return
    if intent == 'refuse_talk':
        vars['refusals'] = I('refusals') + 1
        if I('refusals') >= 2: return close('declined', 'I understand.')
    vars['open_asks'] = I('open_asks') + 1
    if I('open_asks') >= SPEC['id']['open_asks_max']:
        return close('unclear', 'I could not confirm who I am speaking with.')
    pre = ''
    if intent == 'robot_question': pre = SN['robot']
    elif intent == 'scam_question': pre = SN['scam']
    elif intent == 'what_about': pre = 'I can explain once I have spoken with ' + tl() + '.'
    elif intent == 'other_question': pre = SN['no_info']
    q = 'Am I speaking with ' + tl() + '?'
    vars['ask'] = q
    talk((pre + ' ' if pre else '') + q, 'open')

def do_third():
    if intent == 'wrong_number': return close('wrong_number', 'I am sorry to have disturbed you.')
    if intent == 'deceased':
        o = SPEC['outcomes']['deceased']; vars['outcome'] = o[0]; vars['reason'] = o[1]
        vars['closing_say'] = SN['deceased'] + ' Goodbye.'; vars['next_node'] = 'end'; vars['st'] = 'closed'; return
    q = 'When can ' + tl() + ' be reached? Please give me a day and a time.'
    d = None
    if dw:
        d, kind = resolve_phrase(dw, today, SPEC['next_week_mode'])
    elif S('cb_date'): d = to_date(S('cb_date'))
    t = hhmm_from_words(tw or dw)
    if t:
        h = int(t[:2])
        if 1 <= h <= 6 and not re.search(r'\b(am|pm|morning|afternoon|evening|' + str(h) + r':)', (tw + ' ' + dw).lower()) and t[:2] == '%02d' % h:
            t = '%02d:%s' % (h + 12, t[3:])
    if d is None and t:
        c = dt_combine(today, t)
        d = today if (is_bd(today, HOL) and c > now) else add_bd(today, 1, HOL)
    if d is not None: vars['cb_date'] = d.isoformat()
    if d is None or not t:
        vars['cb_unclear'] = I('cb_unclear') + 1
        if I('cb_unclear') >= 4: return close('no_callback', 'I could not arrange a callback.')
        vars['ask'] = q
        return talk(('I am not able to discuss that. ' if intent in ('other_question','what_about','scam_question') else '') + q, 'third')
    cs = callback_state(d, t, now, SPEC['callback']['start'], SPEC['callback']['end'], HOL)
    if cs == 'ok':
        vars['cb_time'] = t; vars['cb_date'] = d.isoformat(); vars['next_node'] = 'callback'; vars['st'] = 'cb_res'; return
    vars['cb_bad'] = I('cb_bad') + 1
    vars['cb_date'] = ''
    if I('cb_bad') >= 2: return close('no_callback', 'I could not arrange a callback.')
    vars['ask'] = 'I can only call back today or on the next business day, between 09:00 and 17:00. What other time suits?'
    talk(vars['ask'], 'third')

def dt_combine(d, t): return _dt.datetime(d.year, d.month, d.day, int(t[:2]), int(t[3:]))

def merge_dob():
    t = (S('dob_text') or '').lower()
    if not t: return
    mt = re.search(r'\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4}|\d{2})\b', t)
    if mt:
        a, b, c = int(mt.group(1)), int(mt.group(2)), int(mt.group(3))
        if c < 100: c += 2000 if c < 30 else 1900
        vars['dob_d'], vars['dob_m'], vars['dob_y'] = a, b, c; return
    y = re.search(r'\b(1[89]\d{2}|20\d{2})\b', t)
    if y: vars['dob_y'] = int(y.group(1)); t = t.replace(y.group(1), ' ')
    for i, name in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']):
        if re.search(r'\b' + name, t): vars['dob_m'] = i + 1; break
    dd = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', t)
    if dd and 1 <= int(dd.group(1)) <= 31: vars['dob_d'] = int(dd.group(1))
    else:
        for w in sorted(_ORD, key=len, reverse=True):
            if (' ' + w + ' ') in (' ' + t + ' '): vars['dob_d'] = _ORD[w]; break

def id_refuse_or_question(qtext, stname):
    if intent in ('refuse_talk', 'what_about'):
        vars['refusals'] = I('refusals') + 1
        if I('refusals') >= SPEC['id']['refusals_to_close']: return close('declined', 'I understand.')
        vars['ask'] = qtext
        return talk(SN['protect'] + ' ' + qtext, stname)
    if intent == 'human': return False
    pre = ''
    if intent == 'robot_question': pre = SN['robot']
    elif intent == 'scam_question': pre = SN['scam']
    elif intent == 'other_question': pre = 'I can explain after the security check.'
    else: return False
    vars['ask'] = qtext
    talk(pre + ' ' + qtext, stname); return True

def verify_next(field, answer):
    vars['v_field'] = field; vars['v_answer'] = answer
    for k in ('v_ok', 'v_verified', 'v_left', 'v_all', 'v_hint', 'v_error'): vars[k] = 'none'
    vars['next_node'] = 'verify'; vars['st'] = 'v_res'

def do_dob():
    if id_refuse_or_question(SN['q_dob'], 'dob') is not False: return
    merge_dob()
    d_, m_, y_ = I('dob_d'), I('dob_m'), I('dob_y')
    if d_ and m_ and y_:
        try:
            dd = _dt.date(y_, m_, d_)
            return verify_next('date_of_birth', dd.isoformat())
        except Exception:
            for k in ('dob_d', 'dob_m', 'dob_y'): vars[k] = 0
            vars['ask'] = SN['q_dob']; return talk('That is not a valid date. ' + SN['q_dob'], 'dob')
    if not (d_ or m_ or y_):
        vars['ask'] = SN['q_dob']; return talk(SN['q_dob'], 'dob')
    if not y_: q = 'And the year?'
    elif not m_: q = 'And the month?'
    else: q = 'And the day?'
    vars['ask'] = q; talk(q, 'dob')

def do_phone():
    if id_refuse_or_question(SN['q_phone'], 'phone') is not False: return
    new = re.sub(r'\D', '', S('digits_text'))
    digs = S('digits') + new
    if len(digs) > 4: digs = new if len(new) == 4 else digs[-4:] if len(new) == 0 else new[-4:]
    vars['digits'] = digs
    if len(digs) == 4: return verify_next('phone_last4', digs)
    if len(digs) == 0:
        vars['ask'] = SN['q_phone']; return talk(SN['q_phone'], 'phone')
    q = 'I have ' + ' '.join(digs) + '. What are the remaining digits?'
    vars['ask'] = q; talk(q, 'phone')

def do_v_res():
    field = S('v_field')
    qtext = SN['q_dob'] if field == 'date_of_birth' else SN['q_phone']
    stname = 'dob' if field == 'date_of_birth' else 'phone'
    if not okv('v_ok'):
        if I('v_retry') < 1:
            vars['v_retry'] = I('v_retry') + 1; vars['next_node'] = 'verify'; return
        vars['v_retry'] = 0
        for k in ('dob_d', 'dob_m', 'dob_y'): vars[k] = 0
        vars['digits'] = ''
        vars['ask'] = qtext
        return talk('I could not read that answer. ' + qtext, stname)
    vars['v_retry'] = 0
    if okv('v_verified'):
        if field == 'phone_last4' or okv('v_all'):
            vars['next_node'] = 'account'; vars['st'] = 'acct_res'; return
        vars['ask'] = SN['q_phone']
        return talk('Thank you. ' + SN['q_phone'], 'phone')
    for k in ('dob_d', 'dob_m', 'dob_y'): vars[k] = 0
    vars['digits'] = ''
    if S('v_hint') == 'day_month_swapped':
        vars['ask'] = 'Please say your date of birth again, with the month as a word.'
        return talk(vars['ask'], 'dob')
    vars['wrong_total'] = I('wrong_total') + 1
    left = S('v_left')
    try: left_n = int(float(left))
    except Exception: left_n = None
    if vars['wrong_total'] >= SPEC['id']['max_wrong'] or (left_n is not None and left_n <= 0):
        return close('failed', SN['failed_id'])
    vars['ask'] = qtext
    talk('That does not match. ' + qtext, stname)

def get_products():
    p = vars.get('products')
    if isinstance(p, str):
        try: p = json.loads(p)
        except Exception: p = None
    if isinstance(p, list) and p and isinstance(p[0], str):
        try: p = [json.loads(x) if isinstance(x, str) else x for x in p]
        except Exception: p = None
    return p if isinstance(p, list) else None

def do_acct():
    prods = get_products()
    if not okv('a_ok') or not prods:
        if I('acct_retry') < 1:
            vars['acct_retry'] = 1; vars['next_node'] = 'account'; return
        return close('service_error', 'I could not access your account information right now.')
    p = prods[0]
    b = band_for(p.get('days_late'), SPEC['bands']) or SPEC['bands'][-1]
    dl = add_bd(today, b['deadline_bd'], HOL)
    fl = floor_for(p, SPEC['floor_fields'])
    typ = p.get('type')
    if typ == 'credit_card': ps = 'credit card ending ' + str(p.get('card_last4'))
    elif typ == 'personal_loan': ps = 'personal loan'
    else: ps = 'car loan'
    setv(p_id=p.get('product_id'), past_due=p.get('past_due'), floor=fl, deadline=dl.isoformat(), band=b['name'],
         attempts_total=b['attempts'], product_say=ps, attempts_used=0, floor_offered=0, full_too_much=0, asked_exact=0, offered='', noans=0, cur_amt='', cur_date='')
    q = 'Can you make this payment today?'
    vars['ask'] = q
    talk('I am calling from the collections team about a late payment on your ' + ps + '. The past-due amount is ' + money(p.get('past_due')) + ' and it is ' + str(p.get('days_late')) + ' days late. ' + q, 'ask_today')

def do_debt():
    global st
    global intent
    if st == 'human_check':
        if intent in ('human', 'decline'):
            return transfer('human', 'general', 'I will connect you with a colleague now.')
        st = S('hold_st') or 'ask_today'; vars['st'] = st
        if not (dw or aw) and intent in ('none', 'agree'):
            return talk('Of course. ' + lastask(), st)
    if intent == 'human':
        if I('human_asked') == 0:
            vars['human_asked'] = 1; vars['hold_st'] = st
            return talk('Before I connect you, may I try to help you first?', 'human_check')
        return transfer('human', 'general', 'I will connect you with a colleague now.')
    if intent == 'paid': return close('paid', SN['paid'])
    if intent == 'dispute': return close('dispute', 'I understand. I will not take a promise.')
    if intent == 'restructure': return transfer('restructuring', 'restructuring', 'I will connect you with a colleague who can help with that.')
    if intent == 'hardship' and not (dw or aw):
        return talk('I am sorry to hear that. Would you like me to connect you with our customer support team?', 'support')
    if st == 'support' and not (dw or aw):
        if intent == 'agree': return transfer('support', 'support', 'I will connect you with our customer support team now.')
        if intent in ('decline', 'refuse_talk'): return close('hardship', 'I understand.')
        return talk('Would you like me to connect you with our customer support team?', 'support')
    if common_questions() and not (dw or aw):
        return reask_debt()
    if intent == 'refuse_talk':
        vars['refusals'] = I('refusals') + 1
        if I('refusals') >= SPEC['refusals_to_close']: return close('refused', 'I understand. I will not take a promise today.')
        return flat_refusal()
    pre = 'I am sorry to hear that.' if intent == 'hardship' else ''
    if st == 'confirm':
        if dw or aw: return handle_proposal(pre)
        if intent == 'agree': vars['next_node'] = 'promise'; vars['st'] = 'prom_res'; return
        if intent == 'decline': return flat_refusal()
        return reask_debt()
    if dw or aw:
        return handle_proposal(pre)
    if intent == 'full_too_much':
        vars['full_too_much'] = 1
        if I('floor_offered'): return flat_refusal()
        vars['floor_offered'] = 1
        vars['cur_amt'] = floor(); vars['cur_date'] = default_date().isoformat()
        return ask('I can record the minimum payment of ' + money(floor()) + '. The rest stays overdue. Can you pay that on ' + say_date(default_date()) + '?', 'offer')
    if intent == 'agree':
        if st == 'ask_today':
            vars['cur_amt'] = full(); vars['cur_date'] = default_date().isoformat()
            return to_confirm()
        if st == 'offer':
            return to_confirm()
        if st == 'exact_day': return ask('On which exact day will you pay?', 'exact_day')
    if intent == 'decline':
        return flat_refusal()
    vars['noans'] = I('noans') + 1
    if I('noans') >= 2: return flat_refusal()
    reask_debt()

def do_tr_res():
    key = S('tr_key')
    say = S('tr_say')
    close(key, say.replace(' now.', ' now.'))

try:
    if st == 'open': do_open()
    elif st == 'third': do_third()
    elif st == 'dob': do_dob()
    elif st == 'phone': do_phone()
    elif st == 'v_res': do_v_res()
    elif st == 'acct_res': do_acct()
    elif st == 'prom_res':
        if okv('pr_ok'):
            close('promise', 'Your promise is recorded. ' + SN['promise_text'])
        elif I('prom_fail') < 1:
            vars['prom_fail'] = 1; vars['next_node'] = 'promise'
        else:
            close('service_error', 'I could not record your promise.')
    elif st == 'cb_res':
        if okv('cb_ok'):
            close('callback', 'I have noted a callback on ' + say_date(to_date(S('cb_date'))) + ' at ' + S('cb_time') + '.')
        elif I('cb_fail') < 1:
            vars['cb_fail'] = 1; vars['next_node'] = 'callback'
        else:
            close('no_callback', 'I could not book the callback.')
    elif st == 'tr_res': do_tr_res()
    elif st == 'closed': vars['next_node'] = 'end'
    else: do_debt()
    if not S('next_node'): vars['next_node'] = 'talk'
except Exception as e:
    vars['say'] = 'Sorry, could you say that again?'; vars['next_node'] = 'talk'
vars['intent'] = 'none'; vars['date_words'] = ''; vars['time_words'] = ''; vars['amount_words'] = ''; vars['dob_text'] = ''; vars['digits_text'] = ''
