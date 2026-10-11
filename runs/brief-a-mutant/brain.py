
# ---- step brain: one pass per customer turn or tool result ----
S = SPEC['say']
HOL = SPEC['holidays']
WK = tuple(SPEC['weekend'])
EXTR = ['who', 'question', 'intent', 'answer', 'date_words', 'time_words', 'amount_said', 'dob_day', 'dob_month', 'dob_year', 'phone_digits']


def g(k, d=''):
    v = vars.get(k)
    if v is None: return d
    s = str(v).strip()
    return d if s.lower() in ('', 'none', 'null') else s


def gi(k, d=0):
    try: return int(float(vars.get(k)))
    except Exception: return d


def gf(k, d=None):
    try: return float(str(vars.get(k)).replace(',', '').replace('$', ''))
    except Exception: return d


def truthy(k):
    return str(vars.get(k)).strip().lower() == 'true'


def money(x):
    try:
        x = float(x)
        return ('%d' % x) if x == int(x) else ('%.2f' % x)
    except Exception: return str(x)


def name():
    return '%s %s' % (g('title'), g('last_name'))


def bye(text):
    t = (text + ' ' if text else '') + S['goodbye']
    return t.strip()


def close(key, text):
    o, r = SPEC['outcomes'][key]
    if vars.get('promised') == 'yes' and key not in ('t_restructuring', 't_human', 't_support'):
        o, r = 'promise', ''
    vars['outcome'] = o
    vars['reason'] = r
    vars['bye'] = bye(text)
    vars['st'] = 'closed'
    vars['next'] = 'end'
    return True


def say(text):
    vars['say'] = text
    vars['next'] = 'talk'
    return True


def call(tool):
    vars['pending'] = tool
    vars['next'] = tool
    return True


def today():
    return parse_now(g('now')).date()


def answer_q(q):
    if q == 'robot': return S['robot']
    if q == 'scam': return S['scam']
    if q == 'cannot_answer': return S['no_info']
    return ''


def transfer(queue_key):
    vars['t_queue'] = SPEC['queues'][queue_key]
    vars['t_key'] = 't_' + queue_key
    vars['t_tries'] = 0
    return call('transfer_to_agent')


def tool_ok(prefix):
    return g(prefix + '_ok').lower() == 'true'


def retry_or(tool, failkey, failtext):
    n = gi(tool + '_tries') + 1
    vars[tool + '_tries'] = n
    if n <= SPEC['tool_retries']:
        return call(tool)
    return close(failkey, failtext)


# ---------- payment logic ----------
def prod_words():
    return vars.get('prod_words') or 'account'


def offer(amount, d, text_before):
    vars['o_amount'] = amount
    vars['o_date'] = d.isoformat()
    vars['pay_q'] = 'offer'
    return say((text_before + ' ' if text_before else '') + 'Could you pay %s on %s?' % (money(amount), say_date(d)))


def readback(amount, d, prefix=''):
    vars['c_amount'] = amount
    vars['c_date'] = d.isoformat()
    vars['st'] = 'confirm'
    return say((prefix + ' ' if prefix else '') + 'So that is a payment of %s for your %s on %s. Do you confirm?' % (money(amount), prod_words(), say_date(d)))


def persuade(prefix=''):
    """flat refusal or non-answer: use one persuasion attempt, or stop."""
    used = gi('attempts_used')
    allowed = gi('attempts_allowed', 1)
    full = gf('full'); floor = gf('floor', full)
    dl = to_date(vars.get('deadline'))
    t = today()
    refused = vars.get('refused_offers') or ''
    while used < allowed:
        used += 1
        vars['attempts_used'] = used
        if used == 1:
            amt = floor if vars.get('too_much') == 'yes' else full
            d = last_bd_of_week(t, HOL, WK)
            if d <= t: d = last_bd_of_week(t + datetime.timedelta(days=7), HOL, WK)
            if dl and d > dl: d = dl
        else:
            amt = floor; d = dl
        keyo = '%s@%s' % (money(amt), d.isoformat())
        if keyo in refused: continue
        return offer(amt, d, prefix)
    return close('refused', 'I understand. I am sorry we could not agree on a payment today.')


def refuse_current(prefix=''):
    """customer said no to the open offer (floor, deadline or attempt)."""
    if vars.get('pay_q') == 'offer':
        vars['refused_offers'] = (vars.get('refused_offers') or '') + '|%s@%s' % (money(gf('o_amount', 0)), str(vars.get('o_date')))
    return persuade(prefix)


def check_proposal(dw, amt_said, prefix=''):
    """customer proposed a date and/or an amount. Returns True when handled."""
    t = today()
    full = gf('full'); floor = gf('floor', full)
    dl = to_date(vars.get('deadline'))
    amt = None
    if amt_said is not None:
        if amt_said > full: amt_said = full
        if amt_said < floor:
            if vars.get('floor_offered') == 'yes':
                return refuse_current(prefix + ' I am sorry, I cannot record an amount below %s.' % money(floor))
            vars['floor_offered'] = 'yes'
            vars['too_much'] = 'yes'
            d0 = to_date(vars.get('p_date_wip')) or t
            return offer(floor, d0, (prefix + ' I am sorry, that amount cannot be recorded. The lowest amount I can record is %s, and the rest stays overdue.' % money(floor)).strip())
        amt = amt_said
        vars['p_amount_wip'] = amt
    d = None
    if dw:
        d, kind = resolve_phrase(dw, t, SPEC['next_week_mode'])
        if d is None:
            if vars.get('vague_asked') == 'yes':
                return offer(amt or gf('p_amount_wip') or full, dl, (prefix + ' The latest date I can record is %s.' % say_date(dl)).strip())
            vars['vague_asked'] = 'yes'
            return say((prefix + ' Could you tell me the exact day you can pay?').strip())
        stt = promise_date_state(d, t, dl, HOL, WK)
        if stt == 'past':
            return say((prefix + ' That date has already passed. On which day from today can you pay?').strip())
        if stt == 'after_deadline':
            return offer(amt or gf('p_amount_wip') or full, dl, (prefix + ' The latest date I can record is %s.' % say_date(dl)).strip())
        if stt == 'not_business_day':
            nd = on_or_after_bd(d, HOL, WK)
            if nd > dl: nd = dl
            return offer(amt or gf('p_amount_wip') or full, nd, (prefix + ' %s is not a business day. The next business day is %s.' % (say_date(d), say_date(nd))).strip())
        vars['p_date_wip'] = d.isoformat()
    a = amt if amt is not None else gf('p_amount_wip')
    dd = d or to_date(vars.get('p_date_wip'))
    if amt is not None and dd is None:
        return say((prefix + ' Thank you. On which day can you pay %s?' % money(amt)).strip())
    if dd is not None and a is None:
        a = floor if vars.get('too_much') == 'yes' and vars.get('pay_q') == 'offer' and gf('o_amount') == floor else full
        if vars.get('pay_q') == 'offer' and gf('o_amount') is not None: a = gf('o_amount')
    return readback(a, dd, prefix)


def pay_turn(it, ans, q, dw, amt_said, pre):
    t = today()
    full = gf('full'); floor = gf('floor', full)
    if it == 'paid':
        return close('paid', S['paid'])
    if it == 'dispute':
        return close('dispute', 'I understand. I will not take a payment promise today.')
    if it == 'plan':
        return transfer('restructuring')
    if it == 'hardship' and not dw and amt_said is None:
        vars['st'] = 'hardship_offer'
        return say((pre + ' I am very sorry to hear that. Would you like me to connect you with our customer support team?').strip())
    if it == 'change_promise' and vars.get('promised') == 'yes':
        return say((pre + ' ' + S['change_app']).strip())
    if dw or amt_said is not None:
        return check_proposal(dw, amt_said, pre)
    if it == 'vague':
        if vars.get('vague_asked') == 'yes':
            dl = to_date(vars.get('deadline'))
            return offer(gf('p_amount_wip') or (floor if vars.get('too_much') == 'yes' else full), dl, (pre + ' The latest date I can record is %s.' % say_date(dl)).strip())
        vars['vague_asked'] = 'yes'
        return say((pre + ' Could you tell me the exact day you can pay?').strip())
    if it == 'too_much':
        vars['too_much'] = 'yes'
        if vars.get('floor_offered') != 'yes':
            vars['floor_offered'] = 'yes'
            return offer(floor, to_date(vars.get('o_date')) if vars.get('pay_q') == 'offer' else t,
                         (pre + ' I understand. The lowest amount I can record is %s, and the rest stays overdue.' % money(floor)).strip())
        return refuse_current(pre)
    if it == 'discount':
        return say((pre + ' ' + S['no_discount'] + ' ' + (vars.get('last_q') or S['ask_today'])).strip())
    if ans == 'yes' or it == 'accept':
        if vars.get('pay_q') == 'offer':
            return readback(gf('o_amount'), to_date(vars.get('o_date')), pre)
        if vars.get('pay_q') == 'today':
            return readback(gf('p_amount_wip') or full, t, pre)
    if ans == 'no' or it in ('refuse', 'stop_talking', 'other'):
        return refuse_current(pre)
    if pre:
        return say(pre + ' ' + (vars.get('last_q') or S['ask_today']))
    if it == 'incomplete':
        return say(vars.get('last_q') or S['ask_today'])
    if gi('nonans') < 1:
        vars['nonans'] = gi('nonans') + 1
        return say(vars.get('last_q') or S['ask_today'])
    return refuse_current(pre)


def main():
    if g('st') == 'closed':
        vars['next'] = 'end'
        return True
    vars['loops'] = int(vars.get('loops') or 0) + 1
    if vars['loops'] > 40:
        return close('service_error', 'I am sorry, I cannot continue this call.')
    t = today()
    st = g('st', 'who')
    pend = g('pending')
    vars['pending'] = 'none'
    # ---------- tool results ----------
    if pend == 'verify_identity':
        if not tool_ok('v'):
            if g('v_error') or str(vars.get('verify_identity_response.status_code') or '') == '200':
                # unreadable answer: not a wrong answer, ask again
                return say('I am sorry, I did not catch that. ' + (S['ask_dob'] if st == 'dob' else S['ask_phone']))
            return retry_or('verify_identity', 'service_error', 'I am sorry, there is a technical problem and I cannot continue the call now.')
        vars['verify_identity_tries'] = 0
        if truthy('v_all'):
            vars['st'] = 'account'
            return call('get_account')
        if truthy('v_verified'):
            vars['st'] = 'phone'
            return say(S['ask_phone'])
        if g('v_hint') == 'day_month_swapped':
            for k in ('dob_d', 'dob_m', 'dob_y'): vars[k] = ''
            return say(S['swapped'])
        w = gi('wrong') + 1
        vars['wrong'] = w
        left = vars.get('v_left')
        if w >= SPEC['wrong_answers_max'] or (str(left) not in ('', 'None', 'none') and gi('v_left', 1) <= 0):
            return close('failed', S['failed'])
        if st == 'dob':
            for k in ('dob_d', 'dob_m', 'dob_y'): vars[k] = ''
            return say('That does not match our records. ' + S['ask_dob'])
        vars['ph'] = ''
        return say('That does not match our records. Could you tell me the last four digits of your phone number again?')
    if pend == 'get_account':
        items = items_from_keys(vars, 'products') or items_from_vars(vars, ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'])
        if not tool_ok('a') or not items:
            return retry_or('get_account', 'service_error', 'I am sorry, there is a technical problem and I cannot continue the call now.')
        p = items[0]
        typ = str(p.get('type') or '')
        if typ == 'credit_card':
            pw = 'credit card ending %s' % str(p.get('card_last4') or '')
        elif typ == 'car_loan':
            pw = 'car loan'
        else:
            pw = 'personal loan'
        full = float(p.get('past_due') or 0)
        fl = floor_for(p, SPEC['floor_fields'])
        try: fl = float(fl)
        except Exception: fl = full
        dlate = int(float(p.get('days_late') or 0))
        b = band_for(dlate, SPEC['bands']) or (SPEC['bands'][0] if dlate < 1 else SPEC['bands'][-1])
        dl = add_bd(t, b['deadline_bd'], HOL, WK)
        vars['product_id'] = str(p.get('product_id') or '')
        vars['prod_words'] = pw
        vars['full'] = full
        vars['floor'] = fl
        vars['band'] = b['name']
        vars['attempts_allowed'] = b['attempts']
        vars['attempts_used'] = 0
        vars['deadline'] = dl.isoformat()
        vars['st'] = 'pay'
        vars['pay_q'] = 'today'
        vars['last_q'] = S['ask_today']
        vars['facts'] = 'Product: %s. Past due: %s. Days late: %d. Band: %s. Deadline: %s. Floor: %s.' % (pw, money(full), dlate, b['name'], dl.isoformat(), money(fl))
        return say('%s It is about your %s. The past-due amount is %s, and it is %d days late. %s' % (S['collections'], pw, money(full), dlate, S['ask_today']))
    if pend == 'create_promise':
        if tool_ok('pr'):
            vars['promised'] = 'yes'
            return close('promise', 'Your promise is recorded. ' + S['sms'])
        return retry_or('create_promise', 'service_error', 'I am sorry, I could not record your promise.')
    if pend == 'schedule_callback':
        if tool_ok('cb'):
            return close('callback', 'Thank you. We will call back on %s at %s.' % (say_date(to_date(vars.get('cb_date'))), vars.get('cb_time')))
        return retry_or('schedule_callback', 'no_callback', 'I am sorry, I could not book the callback.')
    if pend == 'transfer_to_agent':
        if tool_ok('tr'):
            return close(vars.get('t_key') or 't_human', 'I am transferring you now.')
        return retry_or('transfer_to_agent', 'service_error', 'I am sorry, I could not transfer the call.')

    # ---------- customer turn ----------
    who = g('who', 'none'); q = g('question', 'none'); it = g('intent', 'none'); ans = g('answer', 'none')
    dw = g('date_words'); tw = g('time_words')
    amt_said = gf('amount_said')
    pre = answer_q(q)
    verified = st in ('pay', 'confirm', 'hardship_offer', 'account')

    if it == 'deceased' and not verified:
        return close('deceased', S['sorry_loss'])
    if it == 'wrong_number' and not verified:
        return close('wrong_number', 'I apologise for the inconvenience.')
    if g('await_human') == 'yes':
        vars['await_human'] = 'no'
        if ans == 'no' and it in ('none', 'other', 'human'):
            return transfer('human')
    if it == 'human':
        h = gi('human_asks') + 1
        vars['human_asks'] = h
        if h > SPEC['human_asks_before_transfer']:
            return transfer('human')
        vars['await_human'] = 'yes'
        return say((pre + ' ' + S['human_first']).strip())
    if st != 'third' and it == 'stop_talking':
        s = gi('stop_talking') + 1
        vars['stop_talking'] = s
        if s >= SPEC['stop_talking_max']:
            return close('refused' if verified else 'declined', 'I understand.')

    if st == 'who' and who == 'not_customer':
        vars['st'] = 'third'
        st = 'third'
        if not (dw or tw):
            return say('When can %s be reached?' % name())
    if st == 'who':
        if who == 'none' and ans == 'yes' and q == 'none':
            who = 'confirmed'
        if who == 'confirmed':
            vars['st'] = 'dob'
            return say((pre + ' Thank you. ' + S['ask_dob']).strip())
        if it == 'incomplete':
            return say(S['ask_who'].replace('{title}', g('title')).replace('{last_name}', g('last_name')))
        n = gi('who_asks', 1)
        if n >= SPEC['who_asks_max']:
            return close('unclear', (pre + ' I am sorry, I could not confirm who I am speaking with.').strip())
        vars['who_asks'] = n + 1
        if q == 'purpose':
            pre = 'I can explain once I know I am speaking with %s.' % name()
        return say((pre + ' Am I speaking with %s?' % name()).strip())

    if st == 'third' and g('st') == 'third':
        if q in ('purpose', 'cannot_answer'):
            pre = 'I am sorry, I can only discuss this with %s.' % name()
        d = None
        if dw:
            d, kind = resolve_phrase(dw, t, SPEC['next_week_mode'])
            if d: vars['cb_d_wip'] = d.isoformat()
        d = d or to_date(vars.get('cb_d_wip'))
        hh = hhmm_from_words(tw) if tw else None
        if hh: vars['cb_t_wip'] = hh
        hh = hh or (g('cb_t_wip') or None)
        if hh and d is None and is_bd(t, HOL, WK) and hh > parse_now(g('now')).strftime('%H:%M'):
            d = t
        if (dw or tw) and (d is None or hh is None):
            if d is None and hh is None:
                return say((pre + ' Could you tell me the day and the time?').strip())
            return say((pre + (' At what time on that day?' if hh is None else ' On which day?')).strip())
        if d is not None and hh is not None:
            cs = callback_state(d, hh, parse_now(g('now')), SPEC['callback_window']['start'], SPEC['callback_window']['end'], HOL, WK)
            if cs == 'ok':
                vars['cb_date'] = d.isoformat(); vars['cb_time'] = hh
                return call('schedule_callback')
            o = gi('cb_out') + 1
            vars['cb_out'] = o
            vars['cb_d_wip'] = ''; vars['cb_t_wip'] = ''
            if o > SPEC['callback_out_of_window_asks']:
                return close('no_callback', 'I am sorry, I cannot arrange a call at that time.')
            nb = add_bd(t, 1, HOL, WK)
            return say((pre + ' I can only arrange a call today or on %s, between 9 in the morning and 5 in the afternoon. Could you suggest another time?' % say_date(nb)).strip())
        if ans == 'no' or it in ('refuse', 'stop_talking'):
            return close('no_callback', 'I understand.')
        if who == 'confirmed':
            vars['st'] = 'dob'
            return say((pre + ' Thank you. ' + S['ask_dob']).strip())
        return say((pre + ' When can %s be reached?' % name()).strip())

    if st in ('dob', 'phone'):
        if it in ('refuse', 'stop_talking') or q == 'purpose':
            dcount = gi('declines') + 1
            vars['declines'] = dcount
            if dcount >= SPEC['decline_max']:
                return close('declined', 'I understand.')
            return say(S['protect'] + ' ' + (S['ask_dob'] if st == 'dob' else S['ask_phone']))
        if st == 'dob':
            for src, dst in (('dob_day', 'dob_d'), ('dob_month', 'dob_m'), ('dob_year', 'dob_y')):
                v = re.sub(r'[^0-9]', '', g(src))
                if v: vars[dst] = v
            dd, mm, yy = g('dob_d'), g('dob_m'), g('dob_y')
            if dd and mm and yy:
                try:
                    y = int(yy)
                    if y < 100: y += 1900 if y > 30 else 2000
                    iso = datetime.date(y, int(mm), int(dd)).isoformat()
                except Exception:
                    for k in ('dob_d', 'dob_m', 'dob_y'): vars[k] = ''
                    return say((pre + ' I am sorry, I did not catch that. Could you tell me your full date of birth, with day, month and year?').strip())
                vars['v_field'] = 'date_of_birth'; vars['v_answer'] = iso
                for k in ('v_ok', 'v_verified', 'v_all', 'v_hint', 'v_left', 'v_error'): vars[k] = 'none'
                return call('verify_identity')
            if dd or mm or yy:
                miss = [w for w, v in (('day', dd), ('month', mm), ('year', yy)) if not v]
                return say((pre + ' Thank you. And the %s?' % ' and the '.join(miss)).strip())
            return say((pre + ' ' + S['ask_dob']).strip())
        dg = re.sub(r'[^0-9]', '', g('phone_digits'))
        if dg:
            cur = (g('ph') + dg)[-4:] if len(dg) < 4 else dg[-4:]
            vars['ph'] = cur
            if len(cur) == 4:
                vars['v_field'] = 'phone_last4'; vars['v_answer'] = cur
                for k in ('v_ok', 'v_verified', 'v_all', 'v_hint', 'v_left', 'v_error'): vars[k] = 'none'
                return call('verify_identity')
            return say((pre + ' Thank you. And the remaining digits?').strip())
        return say((pre + ' ' + S['ask_phone']).strip())

    if st == 'hardship_offer':
        if dw or amt_said is not None:
            vars['st'] = 'pay'
            return check_proposal(dw, amt_said, pre)
        if ans == 'yes' or it == 'accept':
            return transfer('support')
        if ans == 'no' or it in ('refuse', 'stop_talking'):
            return close('hardship', 'I understand. Please take care.')
        return say((pre + ' Would you like me to connect you with our customer support team?').strip())

    if st == 'confirm':
        if dw or amt_said is not None:
            vars['st'] = 'pay'
            return check_proposal(dw, amt_said, pre)
        if ans == 'yes' or it == 'accept':
            vars['p_amount'] = gf('c_amount'); vars['p_date'] = vars.get('c_date')
            vars['pr_ok'] = 'none'
            return call('create_promise')
        if ans == 'no' or it in ('refuse', 'other', 'stop_talking', 'too_much', 'vague', 'paid', 'dispute', 'plan', 'hardship', 'discount'):
            vars['st'] = 'pay'
            vars['pay_q'] = 'offer'; vars['o_amount'] = gf('c_amount'); vars['o_date'] = vars.get('c_date')
            return pay_turn(it if it != 'none' else 'refuse', 'no' if ans == 'no' else ans, q, dw, amt_said, pre)
        return say((pre + ' Do you confirm?').strip())

    if st == 'pay':
        return pay_turn(it, ans, q, dw, amt_said, pre)
    return say(pre or S['no_info'])


try:
    main()
except Exception as e:
    vars['err'] = str(e)[:200]
    if not vars.get('next') or vars.get('next') == 'none':
        vars['say'] = 'I am sorry, could you say that again?'
        vars['next'] = 'talk'
# remember the question that is open now
if vars.get('next') == 'talk':
    if vars.get('st') == 'pay':
        s = str(vars.get('say') or '')
        qs = s[s.rfind('. ') + 1:].strip() if '?' in s else ''
        if qs: vars['last_q'] = qs
for k in EXTR:
    vars[k] = 'none'
