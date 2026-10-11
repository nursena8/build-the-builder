
H = SPEC['holidays']
WE = tuple(SPEC['weekend'])
OUT = SPEC['outcomes']
NAMES = dict(credit_card='credit card', personal_loan='personal loan', car_loan='car loan')

def g(k, d=''):
    v = vars.get(k)
    return d if v is None else v

def gi(k):
    try:
        return int(float(str(vars.get(k) or 0)))
    except Exception:
        return 0

def gf(k):
    try:
        return float(str(vars.get(k) or 0).replace(',', ''))
    except Exception:
        return 0.0

def money(x):
    try:
        x = float(x)
    except Exception:
        return str(x)
    return ('%d' % x) if x == int(x) else ('%.2f' % x)

def close(key, say):
    o, r = OUT.get(key, OUT['service_error'])
    if vars.get('transfer_reason'):
        o, r = OUT[vars['transfer_reason']]
    elif key in ('refused', 'hardship', 'dispute', 'service_error') and vars.get('promises_made'):
        o, r = OUT['promise']
    vars['outcome'] = o
    vars['reason'] = r
    vars['say'] = (say + ' ' if say else '') + 'Thank you for your time. Goodbye.'
    vars['action'] = 'end'
    vars['st'] = 'closed'
    return True

def talk(say):
    vars['say'] = say
    vars['action'] = 'talk'
    return True

def transfer(key, say):
    vars['transfer_reason'] = key
    vars['queue'] = SPEC['queues'][key]
    vars['outcome'], vars['reason'] = OUT[key]
    vars['say'] = say + ' Thank you for your time. Goodbye.'
    vars['action'] = 'transfer'
    vars['st'] = 'closed'
    return True

def ask_name():
    return 'Am I speaking with ' + str(g('title')) + ' ' + str(g('last_name')) + '?'

def product_words(p):
    t = p.get('type')
    if t == 'credit_card':
        return 'credit card ending ' + str(p.get('card_last4') or '')
    return NAMES.get(t, 'account')

def cur():
    return vars['products_list'][gi('pidx')]

def readback():
    p = cur()
    d = to_date(g('c_date'))
    vars['pst'] = 'confirm'
    return talk('So that is your ' + product_words(p) + ', ' + money(g('c_amount')) + ', to be paid on ' + say_date(d) + '. ' + SPEC['confirm_q'])

def start_product(prefix):
    p = cur()
    n = vars['now_dt']
    today = n.date()
    b = band_for(p.get('days_late'), SPEC['bands']) or SPEC['bands'][-1]
    dl = add_bd(today, b['deadline_bd'], H, WE)
    full = float(p.get('past_due') or 0)
    fl = floor_for(p, SPEC['floor_fields'])
    try:
        fl = float(fl)
    except Exception:
        fl = full
    vars['band'] = b['name']
    vars['attempts_max'] = b['attempts']
    vars['attempts_used'] = 0
    vars['deadline'] = dl.isoformat()
    vars['full'] = full
    vars['floor'] = fl
    vars['too_much'] = 'no'
    vars['floor_offered'] = 'no'
    vars['below_offered'] = 'no'
    vars['vague_asked'] = 'no'
    vars['c_amount'] = full
    vars['c_date'] = on_or_after_bd(today, H, WE).isoformat()
    vars['pst'] = 'ask_today'
    vars['promise_tries'] = 0
    vars['facts'] = 'Product ' + product_words(p) + ', band ' + b['name'] + ', deadline ' + dl.isoformat() + ', floor ' + money(fl)
    return talk(prefix + 'I am calling from the collections team about a late payment on your ' + product_words(p) + '. The past-due amount is ' + money(full) + ' and it is ' + str(p.get('days_late')) + ' days late. ' + SPEC['pay_today'])

def next_product_or_close(prefix):
    i = gi('pidx') + 1
    if i < len(vars['products_list']):
        vars['pidx'] = i
        return start_product(prefix + 'There is also another product. ')
    if vars.get('promises_made'):
        return close('promise', prefix)
    return close('refused', prefix)

def attempt(prefix):
    today = vars['now_dt'].date()
    used = gi('attempts_used') + 1
    vars['attempts_used'] = used
    if used > gi('attempts_max'):
        return next_product_or_close(prefix + 'I understand.')
    if used == 1:
        d = last_bd_of_week(today, H, WE)
        if d is None or d <= today:
            d = last_bd_of_week(today + datetime.timedelta(days=7), H, WE)
        amt = gf('floor') if g('too_much') == 'yes' else gf('full')
    else:
        d = to_date(g('deadline'))
        amt = gf('floor')
        if g('floor_offered') == 'yes' and g('deadline_refused') == 'yes':
            return next_product_or_close(prefix + 'I understand.')
        vars['floor_offered'] = 'yes'
        prefix = prefix + 'The rest would stay overdue. '
    vars['c_amount'] = amt
    vars['c_date'] = d.isoformat()
    vars['pst'] = 'offer'
    return talk(prefix + 'Could you pay ' + money(amt) + ' on ' + say_date(d) + '?')

def refusal(prefix=''):
    if g('pst') == 'offer' and g('c_date') == g('deadline'):
        vars['deadline_refused'] = 'yes'
    return attempt(prefix)

def common_events(ev, verified):
    # requests the brief answers in every stage (rules 4, 32, 39-45)
    if ev == 'robot_q':
        return 'answer', "I am Freya Bank's digital assistant. "
    if ev == 'scam_q':
        return 'answer', "You can verify this call by phoning Freya Bank's customer service number. "
    if ev == 'human':
        vars['human_asks'] = gi('human_asks') + 1
        if gi('human_asks') >= 2:
            transfer('human', 'I will transfer you to a colleague now.')
            return 'done', ''
        return 'answer', 'Is there anything I can help you with first? '
    if ev == 'refuse_talk':
        vars['refuse_talk'] = gi('refuse_talk') + 1
        if gi('refuse_talk') >= 2:
            if verified:
                if gi('pidx') + 1 < len(vars.get('products_list') or []) and False:
                    pass
                close('refused', 'I understand.')
            else:
                close('declined', 'I understand.')
            return 'done', ''
        return 'answer', 'I understand. It will only take a moment. '
    return None, ''

def main():
    vars['loops'] = gi('loops') + 1
    if vars['loops'] > 60 and g('st') != 'closed':
        return close('service_error', 'I am sorry, I cannot continue this call.')
    n = parse_now(g('now')) or datetime.datetime(2026, 10, 14, 11, 0)
    vars['now_dt'] = n
    today = n.date()
    st = g('st') or 'init'
    ev = str(g('event') or 'none')
    ans = str(g('answer') or 'none')
    pend = g('pending')
    vars['pending'] = ''
    vars['action'] = 'talk'

    if st == 'init':
        vars['st'] = 'opening'
        vars['name_asks'] = 1
        return talk(SPEC['opening'] + ' ' + ask_name())

    # ---------- tool results ----------
    if pend == 'verify':
        ok = str(g('verify_ok')).lower() == 'true'
        ver = str(g('verify_verified')).lower()
        allv = str(g('verify_all')).lower() == 'true'
        hint = str(g('verify_hint'))
        if not ok or ver not in ('true', 'false'):
            if g('v_field') == 'date_of_birth' and ok is False and str(g('verify_error')):
                vars['dob_d'] = 0; vars['dob_m'] = 0; vars['dob_y'] = 0
            vars['vfail'] = gi('vfail') + 1
            if gi('vfail') >= 3:
                return close('service_error', 'There was a technical problem and I cannot continue.')
            if g('v_field') == 'date_of_birth':
                return talk('I could not read that date. Could you say your full date of birth, with the month as a word?')
            return talk('There was a technical problem. Could you say the last four digits of your phone number again?')
        if allv or (ver == 'true' and g('v_field') == 'phone_last4'):
            vars['st'] = 'account'
            vars['pending'] = 'account'
            vars['action'] = 'account'
            return True
        if ver == 'true':
            vars['st'] = 'phone'
            vars['digits_sofar'] = ''
            return talk('Thank you. What are the last four digits of the phone number we have on file?')
        if hint == 'day_month_swapped':
            vars['dob_d'] = 0; vars['dob_m'] = 0; vars['dob_y'] = 0
            return talk('Could you say your date of birth again, with the month as a word, please?')
        vars['wrong'] = gi('wrong') + 1
        left = g('verify_left')
        if gi('wrong') >= SPEC['max_wrong'] or str(left) == '0':
            return close('failed', 'I am sorry, I could not verify your identity. Please use the Freya Bank mobile app or visit a branch.')
        if g('v_field') == 'date_of_birth':
            vars['dob_d'] = 0; vars['dob_m'] = 0; vars['dob_y'] = 0
            return talk('That does not match our records. Could you say your date of birth again?')
        vars['digits_sofar'] = ''
        return talk('That does not match our records. Could you say the last four digits of your phone number again?')

    if pend == 'account':
        items = []
        try:
            items = items_from_keys(vars, 'products')
        except Exception:
            items = []
        if not items:
            try:
                items = items_from_vars(vars, ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'])
            except Exception:
                items = []
        items = [x for x in items if x.get('product_id')]
        if not items:
            vars['afail'] = gi('afail') + 1
            if gi('afail') >= 2:
                return close('service_error', 'I am sorry, there was a technical problem and I cannot see your account.')
            vars['pending'] = 'account'
            vars['action'] = 'account'
            return True
        vars['products_list'] = items
        vars['pidx'] = 0
        vars['st'] = 'promise'
        return start_product('Thank you, you are verified. ')

    if pend == 'promise':
        ok = str(g('promise_ok')).lower() == 'true'
        if ok:
            vars['promises_made'] = gi('promises_made') + 1
            return next_product_or_close('Your promise is recorded. ' + SPEC['sms'] + ' ')
        vars['promise_tries'] = gi('promise_tries') + 1
        if gi('promise_tries') >= 2:
            if vars.get('promises_made'):
                return next_product_or_close('I am sorry, I could not record this promise. ')
            return close('service_error', 'I am sorry, I could not record the promise.')
        vars['say'] = 'There was a technical problem, I will try once more.'
        vars['pending'] = 'promise'
        vars['action'] = 'promise'
        return True

    if pend == 'callback':
        return close('callback', 'Thank you, we will call back then.')

    # ---------- user turn ----------
    verified = st in ('promise', 'account')
    if ev == 'deceased' and not verified:
        vars['say'] = SPEC['loss']
        return close('deceased', SPEC['loss'])
    if ev == 'wrong_number' and not verified:
        return close('wrong_number', 'Sorry for the inconvenience.')

    if st == 'opening':
        if ev == 'not_customer' or (ans == 'no' and ev == 'none'):
            vars['st'] = 'third_party'
            return talk('When can ' + str(g('title')) + ' ' + str(g('last_name')) + ' be reached?')
        kind, pre = common_events(ev, False)
        if kind == 'done':
            return True
        if ans == 'yes' and kind is None:
            vars['st'] = 'dob'
            return talk('Thank you. Before we continue I need to ask two security questions. What is your date of birth?')
        if ans == 'incomplete' and kind is None:
            return talk(ask_name())
        if ev == 'purpose_q':
            pre = 'I am Freya Bank\'s digital assistant, and I can only explain once I know who I am speaking with. '
        if gi('name_asks') >= 2:
            return close('unclear', 'I am sorry, I could not confirm who I am speaking with.')
        vars['name_asks'] = 2
        return talk(pre + ask_name())

    if st == 'third_party':
        dt = str(g('day_text') or '').strip()
        tt = str(g('time_text') or '').strip()
        if ev == 'offer_pay':
            return talk('I can only speak with ' + str(g('title')) + ' ' + str(g('last_name')) + '. When can they be reached?')
        if not dt and not tt:
            kind, pre = common_events(ev, False)
            if kind == 'done':
                return True
            if ans == 'incomplete':
                return talk('When can ' + str(g('title')) + ' ' + str(g('last_name')) + ' be reached?')
            vars['cb_out'] = gi('cb_out') + 1
            if gi('cb_out') >= 2:
                return close('no_callback', 'Then we will not schedule a call.')
            return talk(pre + 'Could you tell me a day and a time between 9 in the morning and 5 in the afternoon, today or the next business day?')
        d = today
        if dt:
            d, kind = resolve_phrase(dt, today, SPEC['next_week_mode'])
        hm = hhmm_from_words(tt or dt)
        if d is None:
            return talk('Which day exactly, today or the next business day?')
        if not hm:
            vars['cb_day_text'] = dt
            return talk('At what time on ' + say_date(d) + '?')
        stt = callback_state(d, hm, n, SPEC['callback_window'][0], SPEC['callback_window'][1], H, WE)
        if stt == 'ok':
            vars['cb_date'] = d.isoformat()
            vars['cb_time'] = hm
            vars['pending'] = 'callback'
            vars['action'] = 'callback'
            vars['say'] = 'We will call back on ' + say_date(d) + ' at ' + hm + '.'
            return True
        vars['cb_out'] = gi('cb_out') + 1
        if gi('cb_out') >= 2:
            return close('no_callback', 'I am sorry, I cannot schedule a call at that time.')
        return talk('I am sorry, I can only arrange a call today or the next business day, between 09:00 and 17:00. Is there another time?')

    if st in ('dob', 'phone'):
        kind, pre = common_events(ev, False)
        if kind == 'done':
            return True
        if ev in ('decline_security', 'purpose_q') or (ans == 'no' and kind is None and st == 'dob' and not gi('dob_y') and not gi('dob_d')):
            vars['declines'] = gi('declines') + 1
            if gi('declines') >= 2:
                return close('declined', 'I understand.')
            q = 'What is your date of birth?' if st == 'dob' else 'What are the last four digits of your phone number on file?'
            return talk('These questions protect your account, and I can explain why I am calling once they are answered. ' + q)
        if st == 'dob':
            dd, mm, yy = gi('x_dob_day') or gi('dob_d'), gi('x_dob_month') or gi('dob_m'), gi('x_dob_year') or gi('dob_y')
            vars['dob_d'], vars['dob_m'], vars['dob_y'] = dd, mm, yy
            if dd and mm and yy:
                try:
                    if yy < 100:
                        yy = yy + (1900 if yy > today.year % 100 else 2000)
                    iso = datetime.date(yy, mm, dd).isoformat()
                except Exception:
                    vars['dob_d'] = 0; vars['dob_m'] = 0; vars['dob_y'] = 0
                    return talk(pre + 'Sorry, I did not get a valid date. Could you say your full date of birth, with the month as a word?')
                vars['v_field'] = 'date_of_birth'
                vars['v_answer'] = iso
                vars['pending'] = 'verify'
                vars['action'] = 'verify'
                return True
            if not (dd or mm or yy):
                return talk(pre + 'What is your date of birth?')
            miss = 'the day' if not dd else ('the month' if not mm else 'the year')
            return talk(pre + 'And ' + miss + '?')
        digs = re.sub(r'\D', '', str(g('x_digits') or ''))
        sofar = str(g('digits_sofar') or '') + digs
        if len(sofar) > 4:
            sofar = digs[-4:] if len(digs) >= 4 else sofar[-4:]
        vars['digits_sofar'] = sofar
        if len(sofar) == 4:
            vars['v_field'] = 'phone_last4'
            vars['v_answer'] = sofar
            vars['pending'] = 'verify'
            vars['action'] = 'verify'
            vars['digits_sofar'] = ''
            return True
        if sofar:
            return talk(pre + 'And the remaining ' + str(4 - len(sofar)) + ' digits?')
        return talk(pre + 'What are the last four digits of the phone number we have on file?')

    if st == 'promise':
        p = cur()
        deadline = to_date(g('deadline'))
        if ev == 'hardship':
            vars['st'] = 'hardship'
            return talk('I am sorry to hear that. Would you like me to connect you with our customer support team?')
        if ev == 'paid':
            return close('paid', 'Thank you. Payments can take one business day to appear.')
        if ev == 'dispute':
            return close('dispute', 'I understand, I will not take a promise for this.')
        if ev == 'restructuring':
            return transfer('restructuring', 'I will transfer you to our team that handles payment plans.')
        if ev == 'change_request' and vars.get('promises_made') and g('pst') != 'confirm':
            return talk('A recorded promise cannot be changed in this call. You can change it in the mobile app. ' + ('Could you pay ' + money(g('c_amount')) + ' on ' + say_date(to_date(g('c_date'))) + '?'))
        kind, pre = common_events(ev, True)
        if kind == 'done':
            return True
        if ev == 'discount':
            pre = 'I am sorry, I cannot offer that. '
        if ev in ('other_q', 'purpose_q'):
            pre = 'I am sorry, I do not have that information. '
        amt = gf('x_amount')
        dt = str(g('day_text') or '').strip()
        changed = False
        if amt > 0:
            if amt > gf('full'):
                amt = gf('full')
            if amt < gf('floor') - 0.001:
                if g('below_offered') == 'yes':
                    return refusal(pre + 'I cannot record that amount. ')
                vars['below_offered'] = 'yes'
                vars['floor_offered'] = 'yes'
                vars['c_amount'] = gf('floor')
                vars['pst'] = 'offer'
                return talk(pre + 'I cannot record that amount. The lowest amount I can record is ' + money(gf('floor')) + ', and the rest stays overdue. Could you pay ' + money(gf('floor')) + ' on ' + say_date(to_date(g('c_date'))) + '?')
            vars['c_amount'] = amt
            changed = True
        if dt:
            d, k = resolve_phrase(dt, today, SPEC['next_week_mode'])
            if d is None:
                if g('vague_asked') != 'yes':
                    vars['vague_asked'] = 'yes'
                    vars['pst'] = 'need_day'
                    return talk(pre + 'Which exact day can you pay?')
                vars['c_date'] = deadline.isoformat()
                vars['pst'] = 'offer'
                return talk(pre + 'The latest date I can record is ' + say_date(deadline) + '. Could you pay ' + money(g('c_amount')) + ' on ' + say_date(deadline) + '?')
            s = promise_date_state(d, today, deadline, H, WE)
            if s == 'past':
                return talk(pre + 'That date has already passed. Which day from today can you pay?')
            if s == 'not_business_day':
                nd = on_or_after_bd(d, H, WE)
                if nd <= deadline:
                    vars['c_date'] = nd.isoformat()
                    vars['pst'] = 'offer'
                    return talk(pre + say_date(d) + ' is not a business day. Could you pay ' + money(g('c_amount')) + ' on ' + say_date(nd) + '?')
                s = 'after_deadline'
            if s == 'after_deadline':
                vars['c_date'] = deadline.isoformat()
                vars['pst'] = 'offer'
                return talk(pre + 'The latest date I can record is ' + say_date(deadline) + '. Could you pay ' + money(g('c_amount')) + ' on ' + say_date(deadline) + '?')
            vars['c_date'] = d.isoformat()
            changed = True
        if changed:
            return readback()
        if g('pst') == 'need_day' and ev == 'none' and ans != 'yes':
            vars['c_date'] = deadline.isoformat()
            vars['pst'] = 'offer'
            return talk(pre + 'The latest date I can record is ' + say_date(deadline) + '. Could you pay ' + money(g('c_amount')) + ' on ' + say_date(deadline) + '?')
        if ev == 'too_much':
            vars['too_much'] = 'yes'
            if g('floor_offered') != 'yes':
                vars['floor_offered'] = 'yes'
                vars['c_amount'] = gf('floor')
                vars['pst'] = 'offer'
                return talk(pre + 'I understand. You could pay ' + money(gf('floor')) + ' instead, and the rest stays overdue. Could you pay ' + money(gf('floor')) + ' on ' + say_date(to_date(g('c_date'))) + '?')
            return refusal(pre)
        if ans == 'yes':
            if g('pst') == 'confirm':
                vars['pending'] = 'promise'
                vars['action'] = 'promise'
                vars['p_product'] = p.get('product_id')
                vars['p_amount'] = gf('c_amount')
                vars['p_date'] = g('c_date')
                vars['say'] = 'Thank you, one moment please.'
                return True
            return readback()
        if ans == 'incomplete' or kind == 'answer' or ev in ('discount', 'other_q', 'purpose_q', 'change_request'):
            if g('pst') == 'confirm':
                return talk(pre + SPEC['confirm_q'])
            if g('pst') == 'ask_today':
                return talk(pre + SPEC['pay_today'])
            return talk(pre + 'Could you pay ' + money(g('c_amount')) + ' on ' + say_date(to_date(g('c_date'))) + '?')
        return refusal(pre)

    if st == 'hardship':
        dt = str(g('day_text') or '').strip()
        if gf('x_amount') > 0 or dt:
            vars['st'] = 'promise'
            vars['pst'] = 'offer'
            vars['action'] = 'talk'
            return main_again()
        if ans == 'yes' or ev == 'human':
            return transfer('support', 'I will connect you with our customer support team.')
        if ans == 'no' or ev in ('refuse_talk', 'none'):
            return close('hardship', 'I understand. Take care.')
        return talk('Would you like me to connect you with our customer support team?')

    return close('service_error', 'I am sorry, I cannot continue this call.')

def main_again():
    vars['event'] = 'none'
    vars['answer'] = 'none'
    return main()

try:
    main()
except Exception as e:
    vars['err'] = str(e)[:200]
    if not vars.get('say'):
        vars['say'] = 'Sorry, could you say that again?'
    vars['action'] = vars.get('action') or 'talk'
vars['now_dt'] = ''
vars['event'] = 'none'
vars['answer'] = 'none'
vars['day_text'] = ''
vars['time_text'] = ''
vars['x_digits'] = ''
vars['x_amount'] = 0
vars['x_dob_day'] = 0
vars['x_dob_month'] = 0
vars['x_dob_year'] = 0
if vars.get('outcome'):
    vars['outcome_final'] = vars['outcome']
