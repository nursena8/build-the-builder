
S = SPEC['sentences']
HOL = SPEC['holidays']
EXTRACT_FIELDS = ['intent', 'dob_day', 'dob_month', 'dob_year', 'digits', 'when_words', 'time_words', 'amount', 'product_ref']


def fmt(s):
    return s.replace('{title}', str(vars.get('title') or '')).replace('{last_name}', str(vars.get('last_name') or ''))


def val(k):
    v = vars.get(k)
    if v is None: return ''
    v = str(v).strip()
    return '' if v.lower() in ('none', 'null', '', 'nan') else v


def truthy(k):
    return str(vars.get(k)).strip().lower() == 'true'


def money(x):
    try: return '{:,.2f}'.format(float(x))
    except Exception: return str(x)


def num(s):
    try: return float(str(s).replace(',', '').strip())
    except Exception: return None


def close(key, text):
    o, r = SPEC['outcomes'][key]
    vars['outcome'] = o
    vars['reason'] = r
    vars['st'] = 'closed'
    vars['act'] = 'end'
    vars['say'] = (text + ' ' + S['bye']).strip()
    return True


def talk(text, q=None):
    if q is not None: vars['q'] = q
    vars['act'] = 'talk'
    vars['say'] = text.strip()
    return True


def load_P():
    try: return json.loads(vars.get('P_json') or '[]')
    except Exception: return []


def save_P(P):
    vars['P_json'] = json.dumps(P)


def today():
    return parse_now(vars.get('now')).date()


def pname(p):
    if p['type'] == 'credit_card':
        return 'credit card ending ' + str(p.get('card_last4') or '')
    return p['type'].replace('_', ' ')


def build_products(items):
    P = []
    t = today()
    for it in items[:SPEC['max_products']]:
        try:
            dl = int(float(it.get('days_late')))
        except Exception:
            dl = 1
        b = band_for(dl, SPEC['bands']) or SPEC['bands'][-1]
        fl = num(it.get(SPEC['floor_fields'].get(str(it.get('type')), 'minimum_payment')))
        due = num(it.get('past_due')) or 0.0
        P.append({'id': str(it.get('product_id')), 'type': str(it.get('type')), 'card_last4': str(it.get('card_last4') or ''),
                  'past_due': due, 'days_late': dl, 'floor': fl if fl is not None else due, 'band': b['name'],
                  'attempts': b['attempts'], 'deadline': add_bd(t, b['deadline_bd'], HOL).isoformat(),
                  'used': 0, 'floor_offered': 0, 'too_much': 0, 'vague': 0, 'dl_offered': 0,
                  'status': 'open', 'date': '', 'amount': 0.0, 'offer_date': '', 'offer_amount': 0.0, 'note': '', 'note_done': 0})
    return P


def debt_text(P):
    parts = ['I am calling from the collections team about a late payment.']
    for p in P:
        parts.append('Your ' + pname(p) + ' has a past-due amount of ' + money(p['past_due']) + ' and is ' + str(p['days_late']) + ' days late.')
    return ' '.join(parts)


def attempt1_date():
    t = today()
    d = last_bd_of_week(t, HOL)
    if d <= t:
        d = last_bd_of_week(t + datetime.timedelta(days=7), HOL)
    return d


def offer_text(p):
    d = to_date(p['offer_date'])
    amt = p['offer_amount']
    extra = ' The rest stays overdue.' if amt < p['past_due'] else ''
    return 'For your ' + pname(p) + ': could you pay ' + money(amt) + ' on ' + say_date(d) + '?' + extra


def make_offer(p):
    """Propose the next persuasion attempt for p, or mark it refused. Returns the sentence or ''."""
    p['used'] += 1
    if p['used'] == 1:
        p['offer_date'] = attempt1_date().isoformat()
        p['offer_amount'] = p['floor'] if p['too_much'] else p['past_due']
        if to_date(p['offer_date']) > to_date(p['deadline']): p['offer_date'] = p['deadline']
        return offer_text(p)
    if p['used'] == 2 and p['attempts'] >= 2:
        p['offer_date'] = p['deadline']
        p['offer_amount'] = p['floor']
        return offer_text(p)
    p['status'] = 'refused'
    p['note'] = 'refused'
    return ''


def check_date(p, words):
    """Returns (date_iso or '', sentence_if_not_ok)."""
    t = today()
    d, kind = resolve_phrase(words, t, SPEC['next_week_mode'])
    if d is None:
        if p['vague'] == 0:
            p['vague'] = 1
            return '', 'Which exact day could you pay on?'
        p['offer_date'] = p['deadline']
        p['offer_amount'] = p['offer_amount'] or (p['floor'] if p['too_much'] else p['past_due'])
        p['dl_offered'] = 1
        return '', 'The latest date I can record is ' + say_date(to_date(p['deadline'])) + '. Could you pay ' + money(p['offer_amount']) + ' on that day?'
    st = promise_date_state(d, t, to_date(p['deadline']), HOL)
    if st == 'ok': return d.isoformat(), ''
    if st == 'past': return '', 'That date has already passed. Which day from today on could you pay?'
    if st == 'after_deadline':
        p['offer_date'] = p['deadline']
        p['offer_amount'] = p['offer_amount'] or (p['floor'] if p['too_much'] else p['past_due'])
        p['dl_offered'] = 1
        return '', 'For your ' + pname(p) + ', the latest date I can record is ' + say_date(to_date(p['deadline'])) + '. Could you pay on that day?'
    nd = on_or_after_bd(d, HOL)
    p['offer_date'] = nd.isoformat()
    p['offer_amount'] = p['offer_amount'] or (p['floor'] if p['too_much'] else p['past_due'])
    return '', 'That day is not a business day. Could you pay ' + money(p['offer_amount']) + ' on ' + say_date(nd) + ' instead?'


def check_amount(p, a):
    """Returns (amount or None, sentence_if_not_ok)."""
    if a >= p['past_due'] - 0.005: return p['past_due'], ''
    if a >= p['floor'] - 0.005: return a, ''
    if not p['floor_offered']:
        p['floor_offered'] = 1
        p['offer_amount'] = p['floor']
        p['offer_date'] = p['offer_date'] or attempt1_date().isoformat()
        if to_date(p['offer_date']) > to_date(p['deadline']): p['offer_date'] = p['deadline']
        return None, 'I cannot record an amount below ' + money(p['floor']) + '. Could you pay ' + money(p['floor']) + ' on ' + say_date(to_date(p['offer_date'])) + '? The rest stays overdue.'
    return None, 'REFUSE'


def readback(P):
    parts = []
    for p in P:
        if p['status'] == 'agreed':
            s = 'your ' + pname(p) + ': ' + money(p['amount']) + ' on ' + say_date(to_date(p['date']))
            if p.get('capped'): s += ' (this is the latest date I can record for this product)'
            parts.append(s)
    vars['rb_count'] = int(vars.get('rb_count') or 0) + 1
    return talk('Let me read back: ' + '; '.join(parts) + '. Do you confirm?', 'readback')


def next_product(P):
    """Move to the next open product, or to the read-back / notes."""
    i = int(vars.get('idx') or 0)
    while i < len(P) and P[i]['status'] != 'open': i += 1
    vars['idx'] = i
    if i < len(P):
        p = P[i]
        vars['st'] = 'prod'
        if p['offer_date'] and p['used'] > 0:
            return offer_text(p)
        s = make_offer(p)
        if s: return s
        return next_product(P)
    if any(p['status'] == 'agreed' for p in P):
        vars['st'] = 'readback'
        return 'READBACK'
    vars['st'] = 'notes'
    return 'NOTES'


def go_on(P, prefix=''):
    s = next_product(P)
    save_P(P)
    if s == 'READBACK':
        r = readback(P)
        vars['say'] = (prefix + ' ' + vars['say']).strip()
        return r
    if s == 'NOTES':
        return finish(P, prefix)
    return talk(prefix + ' ' + s, s)


def final_key(P):
    if any(p['status'] == 'recorded' for p in P): return 'promise'
    if P and all(p['note'] == 'paid' for p in P): return 'paid'
    for p in P:
        if p['note'] and p['note'] != 'paid': return p['note']
    return 'refused'


def finish(P, prefix=''):
    """Record promises, then notes, then close. Runs again after each tool result."""
    for p in P:
        if p['status'] == 'agreed' and vars.get('st') != 'notes':
            vars['st'] = 'record'
            vars['cur_pid'] = p['id']
            vars['v_product_id'] = p['id']
            vars['v_amount'] = p['amount']
            vars['v_date'] = p['date']
            vars['r_ok'] = 'pending'
            vars['pending'] = 'promise'
            vars['act'] = 'promise'
            vars['say_prefix'] = prefix
            save_P(P)
            return True
    vars['st'] = 'notes'
    for p in P:
        if p['status'] != 'recorded' and not p['note']:
            p['note'] = 'refused'
        if p['status'] != 'recorded' and not p['note_done']:
            vars['cur_pid'] = p['id']
            vars['v_product_id'] = p['id']
            vars['v_note'] = p['note']
            vars['r_ok'] = 'pending'
            vars['pending'] = 'note'
            vars['act'] = 'note'
            vars['say_prefix'] = prefix
            save_P(P)
            return True
    save_P(P)
    key = final_key(P)
    pre = prefix
    if any(p['status'] == 'recorded' for p in P):
        pre = (pre + ' ' + S['sms']).strip()
    if any(p['status'] == 'service_error' for p in P):
        pre = (pre + ' I am sorry, I could not record the promise for your ' + ', '.join(pname(p) for p in P if p['status'] == 'service_error') + '.').strip()
    return close(key, pre)


def do_transfer(queue, key, prefix=''):
    vars['v_queue'] = queue
    vars['transfer_key'] = key
    vars['r_ok'] = 'pending'
    vars['pending'] = 'transfer'
    vars['act'] = 'transfer'
    vars['say_prefix'] = prefix
    return True


def tool_return():
    kind = vars.get('pending')
    vars['pending'] = ''
    ok = str(vars.get('r_ok')).strip().lower() == 'true'
    fails = int(vars.get('fails_' + kind) or 0)
    if kind == 'verify':
        if not ok:
            if str(vars.get('r_error') or 'none').lower() not in ('', 'none', 'pending') and fails < SPEC['tool_retries']:
                vars['fails_verify'] = fails + 1
                if vars.get('st') == 'id_phone':
                    vars['digits_so_far'] = ''
                    return talk('Sorry, I could not read that. Could you tell me the last four digits of your phone number?')
                vars['dob_parts'] = '{}'
                return talk('Sorry, I could not read that. Could you tell me your date of birth with the month as a word?')
            if fails < SPEC['tool_retries']:
                vars['fails_' + kind] = fails + 1
                vars['r_ok'] = 'pending'
                vars['pending'] = 'verify'
                vars['act'] = 'verify'
                return True
            return close('service_error', 'I am sorry, there is a technical problem and I cannot continue.')
        vars['fails_verify'] = 0
        if str(vars.get('r_hint') or '') == 'day_month_swapped':
            vars['dob_parts'] = '{}'
            return talk(S['swapped'], S['swapped'])
        if truthy('r_all'):
            vars['verified'] = 'yes'
            vars['r_ok'] = 'pending'
            vars['pending'] = 'account'
            vars['act'] = 'account'
            return True
        if truthy('r_verified'):
            vars['st'] = 'id_phone'
            vars['digits_so_far'] = ''
            return talk(S['phone_q'], S['phone_q'])
        vars['wrong'] = int(vars.get('wrong') or 0) + 1
        if vars['wrong'] >= SPEC['wrong_answers_max']:
            return close('failed', S['failed'])
        if vars.get('st') == 'id_phone':
            vars['digits_so_far'] = ''
            return talk(S['wrong'] + ' Could you tell me the last four digits of your phone number again?', 'Could you tell me the last four digits of your phone number?')
        vars['dob_parts'] = '{}'
        return talk(S['wrong'] + ' Could you tell me your date of birth again?', 'Could you tell me your date of birth?')
    if kind == 'account':
        items = items_from_keys(vars, 'products')
        if not items:
            items = items_from_vars(vars, ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'], prefix='p', max_items=6)
            items = [it for it in items if it.get('product_id') not in (None, '', 'None')]
        if not ok or not items:
            if fails < SPEC['tool_retries']:
                vars['fails_' + kind] = fails + 1
                vars['r_ok'] = 'pending'
                vars['pending'] = 'account'
                vars['act'] = 'account'
                return True
            return close('service_error', 'I am sorry, there is a technical problem and I cannot continue.')
        P = build_products(items)
        save_P(P)
        vars['idx'] = 0
        vars['st'] = 'today'
        q = S['today_q1'] if len(P) == 1 else S['today_qn']
        return talk(debt_text(P) + ' ' + q, q)
    if kind == 'callback':
        if ok: return close('callback', 'Thank you, we will call back then.')
        if fails < SPEC['tool_retries']:
            vars['fails_' + kind] = fails + 1
            vars['r_ok'] = 'pending'
            vars['pending'] = 'callback'
            vars['act'] = 'callback'
            return True
        return close('no_callback', 'I am sorry, I could not arrange the callback.')
    if kind == 'transfer':
        if ok:
            return close(vars.get('transfer_key'), (str(vars.get('say_prefix') or '') + ' ' + S['connect']).strip())
        if fails < SPEC['tool_retries']:
            vars['fails_' + kind] = fails + 1
            vars['r_ok'] = 'pending'
            vars['pending'] = 'transfer'
            vars['act'] = 'transfer'
            return True
        return close(vars.get('transfer_key'), 'I am sorry, I could not connect you. Please call Freya Bank customer service.')
    P = load_P()
    p = [x for x in P if x['id'] == vars.get('cur_pid')]
    p = p[0] if p else None
    prefix = str(vars.get('say_prefix') or '')
    if kind == 'promise' and p:
        if ok:
            p['status'] = 'recorded'
            vars['fails_promise'] = 0
        elif fails < SPEC['tool_retries']:
            vars['fails_promise'] = fails + 1
            vars['r_ok'] = 'pending'
            vars['pending'] = 'promise'
            vars['act'] = 'promise'
            save_P(P)
            return True
        else:
            vars['fails_promise'] = 0
            p['status'] = 'service_error'
            p['note'] = 'service_error'
        save_P(P)
        vars['st'] = 'record'
        return finish(P, prefix)
    if kind == 'note' and p:
        if ok or fails >= SPEC['tool_retries']:
            p['note_done'] = 1
            vars['fails_note'] = 0
        else:
            vars['fails_note'] = fails + 1
        save_P(P)
        return finish(P, prefix)
    return finish(P, prefix)


def merge_dob():
    try: parts = json.loads(vars.get('dob_parts') or '{}')
    except Exception: parts = {}
    for k in ('day', 'month', 'year'):
        v = val('dob_' + k)
        if v:
            n = num(v)
            if n is not None: parts[k] = int(n)
    y = parts.get('year')
    if y is not None and (y < 1900 or y > today().year): parts.pop('year')
    vars['dob_parts'] = json.dumps(parts)
    return parts


def which_products(P):
    ref = val('product_ref')
    if ref and ref != 'all':
        hit = [p for p in P if p['type'] == ref]
        if hit: return hit
    if ref == 'all' or len(P) == 1: return P
    i = int(vars.get('idx') or 0)
    if vars.get('st') == 'today': return P
    return [P[min(i, len(P) - 1)]]


def handle_common(intent, verified):
    """Requests the brief answers in every stage. Returns True when handled."""
    q = str(vars.get('q') or '')
    if intent == 'human':
        if not vars.get('human_asked'):
            vars['human_asked'] = 1
            return talk(S['human_first'], q)
        return do_transfer('general', 'human')
    if intent == 'robot':
        return talk(S['robot'] + ' ' + q)
    if intent == 'scam':
        return talk(S['scam'] + ' ' + q)
    if intent == 'refuse_talk':
        vars['talk_refusals'] = int(vars.get('talk_refusals') or 0) + 1
        if vars['talk_refusals'] >= 2:
            if not verified: return close('declined', '')
            P = load_P()
            for p in P:
                if p['status'] == 'open': p['status'] = 'refused'; p['note'] = 'refused'
            save_P(P)
            if any(p['status'] == 'agreed' for p in P):
                vars['st'] = 'readback'
                return readback(P)
            return finish(P)
        return talk('I understand. ' + q)
    return False


def main():
    st = vars.get('st') or 'confirm'
    if st == 'closed':
        vars['act'] = 'end'
        return
    vars['loops'] = int(vars.get('loops') or 0) + 1
    if vars['loops'] > SPEC['loop_limit']:
        return close('service_error', 'I am sorry, I cannot continue this call.')
    if vars.get('pending'):
        return tool_return()
    intent = val('intent') or 'unclear'
    t = today()
    q = str(vars.get('q') or '')
    if st == 'confirm':
        if intent == 'deceased': return close('deceased', S['deceased'])
        if intent == 'wrong_number': return close('wrong_number', 'I am sorry for the trouble.')
        if intent in ('not_me', 'no'):
            vars['st'] = 'third'
            return talk(fmt(S['third_q']), fmt(S['third_q']))
        if intent == 'yes':
            vars['st'] = 'id_dob'
            vars['dob_parts'] = '{}'
            return talk(S['dob_q'], S['dob_q'])
        if intent in ('human', 'refuse_talk'):
            return handle_common(intent, False)
        vars['confirm_asks'] = int(vars.get('confirm_asks') or 1) + 1
        if vars['confirm_asks'] > 2:
            return close('unclear', '')
        pre = ''
        if intent == 'robot': pre = S['robot']
        elif intent == 'scam': pre = S['scam']
        elif intent in ('what_about', 'question'): pre = 'I am a digital assistant calling from Freya Bank.'
        return talk(pre + ' ' + fmt(S['confirm_q']), fmt(S['confirm_q']))
    if st == 'third':
        if intent == 'deceased': return close('deceased', S['deceased'])
        if intent == 'wrong_number': return close('wrong_number', 'I am sorry for the trouble.')
        if intent == 'yes' and not val('when_words') and not val('time_words'):
            pass
        if intent in ('robot', 'scam', 'human'):
            return handle_common(intent, False)
        w = val('when_words')
        tm = val('time_words')
        if not w and not tm:
            if intent in ('refuse_talk', 'no'):
                return close('no_callback', '')
            vars['cb_unclear'] = int(vars.get('cb_unclear') or 0) + 1
            if vars['cb_unclear'] > 2: return close('no_callback', '')
            return talk('I can only speak with ' + fmt('{title} {last_name}') + ' directly. ' + fmt(S['third_q']), fmt(S['third_q']))
        d = None
        if w:
            d, kind = resolve_phrase(w, t, SPEC['next_week_mode'])
        if d is None and vars.get('cb_date'):
            d = to_date(vars.get('cb_date'))
        if d is None:
            d = t
        hh = hhmm_from_words(tm or w) if (tm or w) else None
        if hh is None and vars.get('cb_time'):
            hh = vars.get('cb_time')
        vars['cb_date'] = d.isoformat()
        if hh is None:
            return talk('At what time?', 'At what time could I call back?')
        vars['cb_time'] = hh
        stt = callback_state(d, hh, parse_now(vars.get('now')), SPEC['callback_window']['start'], SPEC['callback_window']['end'], HOL)
        if stt == 'ok':
            vars['v_cb_date'] = d.isoformat()
            vars['v_cb_time'] = hh
            vars['r_ok'] = 'pending'
            vars['pending'] = 'callback'
            vars['act'] = 'callback'
            return True
        vars['cb_out'] = int(vars.get('cb_out') or 0) + 1
        vars['cb_date'] = ''
        vars['cb_time'] = ''
        if vars['cb_out'] >= 2: return close('no_callback', 'I am sorry, I cannot arrange a call at that time.')
        return talk('I can only call back today or the next business day, between 10:00 and 19:00. Is there another time that works?', 'Is there another time between 10:00 and 19:00, today or the next business day?')
    if st in ('id_dob', 'id_phone'):
        if intent in ('what_about', 'refuse_id'):
            vars['id_refusals'] = int(vars.get('id_refusals') or 0) + 1
            if vars['id_refusals'] >= 2: return close('declined', '')
            return talk(S['protect'] + ' ' + q)
        if handle_common(intent, False): return True
        if intent == 'deceased': return close('deceased', S['deceased'])
        if st == 'id_dob':
            parts = merge_dob()
            if all(k in parts for k in ('day', 'month', 'year')):
                try:
                    d = datetime.date(parts['year'], parts['month'], parts['day'])
                    vars['v_field'] = 'date_of_birth'
                    vars['v_answer'] = d.isoformat()
                except Exception:
                    vars['v_field'] = 'date_of_birth'
                    vars['v_answer'] = '%04d-%02d-%02d' % (parts['year'], parts['month'], parts['day'])
                vars['r_ok'] = 'pending'
                vars['r_error'] = 'none'
                vars['r_hint'] = 'none'
                vars['r_verified'] = 'pending'
                vars['r_all'] = 'pending'
                vars['pending'] = 'verify'
                vars['act'] = 'verify'
                return True
            if not parts:
                return talk(q or S['dob_q'])
            miss = [k for k in ('day', 'month', 'year') if k not in parts]
            return talk('Thank you. And the ' + ' and the '.join(miss) + '?')
        dg = re.sub(r'\D', '', val('digits'))
        so_far = str(vars.get('digits_so_far') or '') + dg
        vars['digits_so_far'] = so_far
        if len(so_far) >= 4:
            vars['v_field'] = 'phone_last4'
            vars['v_answer'] = so_far[-4:]
            vars['r_ok'] = 'pending'
            vars['r_hint'] = 'none'
            vars['r_verified'] = 'pending'
            vars['r_all'] = 'pending'
            vars['pending'] = 'verify'
            vars['act'] = 'verify'
            return True
        if so_far:
            return talk('Thank you. And the remaining digits?')
        return talk(q or S['phone_q'])
    # verified stages
    P = load_P()
    if st == 'support_offer':
        if intent == 'yes':
            return do_transfer('support', 'support')
        w = val('when_words'); a = num(val('amount'))
        if intent in ('no', 'refuse', 'cant_today', 'refuse_talk', 'unclear', 'other') and not w and a is None:
            for p in P:
                if p['status'] == 'open': p['status'] = 'hardship'; p['note'] = 'hardship'
            save_P(P)
            if any(p['status'] == 'agreed' for p in P):
                vars['st'] = 'readback'
                return readback(P)
            return finish(P)
        vars['st'] = vars.get('st_before_support') or 'prod'
        st = vars['st']
    side = ''
    if intent in ('robot', 'scam', 'question', 'what_about', 'discount') and (val('when_words') or val('amount')):
        side = {'robot': S['robot'], 'scam': S['scam'], 'discount': S['discount']}.get(intent, S['no_info'])
        intent = 'other'
        vars['side'] = side
    if intent == 'plan':
        return do_transfer('restructuring', 'restructuring')
    if intent == 'hardship' and not vars.get('support_offered'):
        vars['support_offered'] = 1
        vars['st_before_support'] = st
        w = val('when_words'); a = num(val('amount'))
        if not w and a is None:
            vars['st'] = 'support_offer'
            return talk(S['sympathy'] + ' ' + S['support_offer'], S['support_offer'])
    if handle_common(intent, True): return True
    if intent == 'discount':
        return talk(S['discount'] + ' ' + q)
    if intent in ('question', 'what_about'):
        return talk(S['no_info'] + ' ' + q)
    if intent in ('paid', 'dispute'):
        targets = which_products(P)
        for p in targets:
            if p['status'] in ('open', 'agreed'):
                p['status'] = intent
                p['note'] = intent
        save_P(P)
        pre = S['paid'] if intent == 'paid' else S['dispute']
        if st == 'readback' and any(p['status'] == 'agreed' for p in P):
            r = readback(P); vars['say'] = pre + ' ' + vars['say']; return r
        if st == 'readback':
            return finish(P, pre)
        return go_on(P, pre)
    if st == 'readback':
        if intent == 'change_promise':
            return talk(S['change_app'] + ' ' + q)
        w = val('when_words'); a = num(val('amount'))
        if w or a is not None:
            targets = [p for p in which_products(P) if p['status'] == 'agreed'] or [p for p in P if p['status'] == 'agreed']
            msgs = []
            for p in targets:
                if w:
                    iso, msg = check_date(p, w)
                    if iso: p['date'] = iso; p['capped'] = False
                    elif msg: msgs.append(msg)
                if a is not None:
                    amt, msg = check_amount(p, a)
                    if amt is not None: p['amount'] = amt
                    elif msg != 'REFUSE': msgs.append(msg)
            save_P(P)
            if msgs:
                vars['st'] = 'prod'
                for p in targets:
                    if p['offer_date'] and p['status'] == 'agreed': p['status'] = 'open'; vars['idx'] = P.index(p); break
                save_P(P)
                return talk(msgs[0], msgs[0])
            return readback(P)
        if intent == 'yes':
            return finish(P)
        if int(vars.get('rb_count') or 0) >= 3:
            return finish(P)
        return talk('Which date or amount would you like to change?', q)
    if st == 'today':
        w = val('when_words'); a = num(val('amount'))
        if intent == 'yes' and not w and a is None:
            for p in P:
                if p['status'] == 'open':
                    p['status'] = 'agreed'; p['date'] = t.isoformat(); p['amount'] = p['past_due']
            save_P(P)
            vars['st'] = 'readback'
            return readback(P)
        if w:
            d, kind = resolve_phrase(w, t, SPEC['next_week_mode'])
            if d is not None and (val('product_ref') in ('', 'all') or len(P) == 1):
                msgs = []
                for p in P:
                    if p['status'] != 'open': continue
                    stt = promise_date_state(d, t, to_date(p['deadline']), HOL)
                    amt = p['past_due']
                    if a is not None and len(P) == 1:
                        amt2, msg = check_amount(p, a)
                        if amt2 is None:
                            p['offer_date'] = d.isoformat() if stt == 'ok' else p['offer_date']
                            vars['st'] = 'prod'; vars['idx'] = P.index(p); save_P(P)
                            if msg == 'REFUSE': return go_on(P)
                            return talk(msg, msg)
                        amt = amt2
                    if stt == 'ok':
                        p['status'] = 'agreed'; p['date'] = d.isoformat(); p['amount'] = amt
                    elif stt == 'after_deadline':
                        p['status'] = 'agreed'; p['date'] = p['deadline']; p['amount'] = amt; p['capped'] = True
                    elif stt == 'not_business_day':
                        p['status'] = 'agreed'; p['date'] = on_or_after_bd(d, HOL).isoformat(); p['amount'] = amt; p['capped'] = False
                        if to_date(p['date']) > to_date(p['deadline']): p['date'] = p['deadline']; p['capped'] = True
                    else:
                        msgs.append('That date has already passed. Which day from today on could you pay?')
                save_P(P)
                if msgs: return talk(msgs[0], q)
                vars['st'] = 'prod'
                return go_on(P)
        if intent == 'too_much':
            for p in P: p['too_much'] = 1
        if intent in ('hardship',):
            pass
        # no to today (or anything else without date): flat refusal of today -> attempt 1 per product
        if w or a is not None:
            vars['st'] = 'prod'
            vars['idx'] = 0
            st = 'prod'
        else:
            vars['st'] = 'prod'
            vars['idx'] = 0
            if intent == 'too_much':
                p = P[0]
                p['floor_offered'] = 1
                save_P(P)
            return go_on(P)
    if st == 'prod':
        i = int(vars.get('idx') or 0)
        if i >= len(P): return go_on(P)
        p = P[i]
        w = val('when_words'); a = num(val('amount'))
        if w or a is not None:
            date_iso = p['offer_date'] or ''
            if w:
                iso, msg = check_date(p, w)
                if not iso:
                    save_P(P)
                    return talk(msg, msg)
                date_iso = iso
            amt = p['offer_amount'] or (p['floor'] if p['too_much'] else p['past_due'])
            if a is not None:
                amt2, msg = check_amount(p, a)
                if amt2 is None:
                    if msg == 'REFUSE':
                        s = make_offer(p); save_P(P)
                        if s: return talk(s, s)
                        return go_on(P)
                    if w: p['offer_date'] = date_iso
                    save_P(P)
                    return talk(msg, msg)
                amt = amt2
            if not date_iso:
                p['offer_amount'] = amt; save_P(P)
                return talk('On which day could you pay ' + money(amt) + '?', 'On which day could you pay?')
            p['status'] = 'agreed'; p['date'] = date_iso; p['amount'] = amt
            return go_on(P)
        if intent == 'yes' and p['offer_date']:
            p['status'] = 'agreed'; p['date'] = p['offer_date']; p['amount'] = p['offer_amount'] or p['past_due']
            return go_on(P)
        if intent == 'too_much' and not p['floor_offered']:
            p['too_much'] = 1; p['floor_offered'] = 1
            p['offer_amount'] = p['floor']
            if not p['offer_date']: p['offer_date'] = attempt1_date().isoformat()
            save_P(P)
            s = 'I can record ' + money(p['floor']) + ' for your ' + pname(p) + ' on ' + say_date(to_date(p['offer_date'])) + '. The rest stays overdue. Can you do that?'
            return talk(s, s)
        if intent in ('no', 'refuse', 'cant_today', 'too_much', 'unclear', 'other', 'hardship'):
            vars['prod_unclear'] = int(vars.get('prod_unclear') or 0) + (1 if intent == 'unclear' else 0)
            s = make_offer(p)
            save_P(P)
            if s: return talk(s, s)
            return go_on(P)
        return talk(q)
    return talk(q or S['today_q1'])


try:
    vars['act'] = 'talk'
    vars['side'] = ''
    main()
    if vars.get('side') and vars.get('act') in ('talk', 'end'):
        vars['say'] = vars['side'] + ' ' + str(vars.get('say') or '')
except Exception as e:
    vars['err'] = str(e)[:200]
    if vars.get('st') in ('confirm', 'third', 'id_dob', 'id_phone', None, ''):
        vars['act'] = 'talk'
        vars['say'] = str(vars.get('q') or 'Sorry, could you say that again?')
    else:
        vars['act'] = 'talk'
        vars['say'] = 'Sorry, could you say that again? ' + str(vars.get('q') or '')
if vars.get('act') in ('talk', 'end'):
    prev = vars.get('last_say')
    if vars.get('act') == 'talk' and prev == vars.get('say'):
        vars['same_say'] = int(vars.get('same_say') or 0) + 1
    else:
        vars['same_say'] = 0
    vars['last_say'] = vars.get('say')
    if vars.get('act') == 'talk' and vars['same_say'] >= 2:
        if vars.get('verified') == 'yes':
            P = load_P()
            for p in P:
                if p['status'] == 'open': p['status'] = 'refused'; p['note'] = 'refused'
            save_P(P)
            finish(P)
        elif vars.get('st') == 'third':
            close('no_callback', '')
        elif vars.get('st') in ('id_dob', 'id_phone'):
            close('declined', '')
        else:
            close('unclear', '')
for f in EXTRACT_FIELDS:
    vars[f] = 'none'
