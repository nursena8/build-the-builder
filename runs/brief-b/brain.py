
S = SPEC['sentences']; HOL = SPEC['holidays']
def V(k, d=''):
    x = vars.get(k)
    return d if x is None else x
def tb(x): return str(x).strip().lower() == 'true'
def money(a):
    try: return '%.2f' % float(a)
    except Exception: return str(a)
def pname(p):
    t = p.get('type')
    if t == 'credit_card': return 'credit card ending ' + str(p.get('card_last4') or '')
    return {'personal_loan': 'personal loan', 'car_loan': 'car loan'}.get(t, 'product')
def ds(d): return say_date(d)
st = json.loads(V('state_json') or '{}')
now = parse_now(V('now')); today = now.date()
who = (str(V('title')) + ' ' + str(V('last_name'))).strip()
out = []
def say(x): out.append(x)
def close(o, r, extra=''):
    st['outcome'] = o; st['reason'] = r; st['stage'] = 'closed'
    if extra: say(extra)
    say(S['bye'])
    vars['act'] = 'end'
def ask(x): say(x); vars['act'] = 'talk'

def readback():
    acc = [p for p in st['prods'] if p['status'] == 'agreed']
    parts = []
    for p in acc:
        s = 'your ' + pname(p) + ': ' + money(p['amount']) + ' on ' + ds(to_date(p['date']))
        if p.get('moved'): s += ' (the latest date I can record for it)'
        parts.append(s)
    st['stage'] = 'readback'
    ask('To confirm: ' + '; '.join(parts) + '. Do you confirm?')

def next_action():
    # after a decision: go to next undecided product, read back, record promises, add notes, close
    for i, p in enumerate(st['prods']):
        if p['status'] == 'open':
            st['cur'] = i
            if not p.get('started'):
                p['started'] = 1
                return attempt(p, 'Now your ' + pname(p) + '. ')
            return
    if any(p['status'] == 'agreed' for p in st['prods']) and not st.get('confirmed'):
        return readback()
    for p in st['prods']:
        if p['status'] == 'agreed':
            p['status'] = 'recording'; p['tries'] = 0
            return call_promise(p)
    if st.get('promised_said') == 1:
        st['promised_said'] = 2; say(S['sms'])
    for p in st['prods']:
        if p['status'] in ('refused', 'hardship', 'dispute', 'paid', 'service_error') and not p.get('noted'):
            p['noted'] = 1; p['ntries'] = 0
            return call_note(p)
    finish()

def finish():
    if st.get('transfer'): return close('transferred', st['transfer'])
    ps = st['prods']
    if any(p['status'] == 'promised' for p in ps): return close('promise', '')
    if ps and all(p['status'] == 'paid' for p in ps): return close('paid', '')
    for p in ps:
        if p['status'] != 'paid': return close('no_promise', p['status'] if p['status'] in ('refused','hardship','dispute','service_error') else 'refused')
    close('no_promise', 'refused')

def call_promise(p):
    st['pending'] = 'promise'; vars['a_pid'] = p['product_id']; vars['a_amount'] = str(p['amount']); vars['a_date'] = p['date']
    vars['r_ok'] = ''; vars['act'] = 'promise'
def call_note(p):
    st['pending'] = 'note'; vars['a_pid'] = p['product_id']; vars['a_reason'] = p['status']
    vars['r_ok'] = ''; vars['act'] = 'note'
def call_transfer(q, reason):
    for p in st['prods']:
        if p['status'] in ('agreed', 'recording'): p['status'] = 'dropped'
    st['pending'] = 'transfer'; st['transfer'] = reason; st['tq'] = q; st['ttries'] = 0
    vars['a_queue'] = q; vars['r_ok'] = ''; vars['act'] = 'transfer'
    say('I will connect you now.')

def attempt(p, pre=''):
    # next persuasion attempt for product p, or refusal when used up (A 30, 31; B 4, 5)
    n = p['att'] + 1
    if n > p['attempts']:
        p['status'] = 'refused'; say(pre + 'I understand.' if pre else 'I understand.')
        return next_action()
    p['att'] = n
    amt = p['floor'] if (p.get('too_much') and p['floor']) else p['past_due']
    if n == 1:
        d = last_bd_of_week(today, HOL)
        if d <= today: d = last_bd_of_week(today + datetime.timedelta(days=7), HOL)
        if d > to_date(p['deadline']): d = to_date(p['deadline'])
    else:
        amt = p['floor'] or p['past_due']; d = to_date(p['deadline'])
    p['offer'] = {'amount': amt, 'date': d.isoformat(), 'kind': 'attempt'}
    extra = ' The rest stays overdue.' if amt != p['past_due'] else ''
    ask(pre + 'Could you pay ' + money(amt) + ' on your ' + pname(p) + ' on ' + ds(d) + '?' + extra)

def agree(p, amount, d, moved=False):
    p['status'] = 'agreed'; p['amount'] = amount; p['date'] = d.isoformat(); p['moved'] = moved; p['offer'] = None

def check_date(p, d, amount, quiet=False):
    """returns True if agreed, else asks"""
    dl = to_date(p['deadline'])
    s = promise_date_state(d, today, dl, HOL)
    if s == 'ok': agree(p, amount, d); return True
    if s == 'past': ask('That date has passed. Which day from today can you pay?'); return False
    if s == 'not_business_day':
        nd = on_or_after_bd(d, HOL)
        if nd > dl: nd = dl
        p['offer'] = {'amount': amount, 'date': nd.isoformat(), 'kind': 'nbd'}
        ask(ds(d) + ' is not a business day. Could you pay ' + money(amount) + ' on ' + ds(nd) + '?'); return False
    p['offer'] = {'amount': amount, 'date': dl.isoformat(), 'kind': 'deadline'}
    ask('The latest date I can record for your ' + pname(p) + ' is ' + ds(dl) + '. Could you pay ' + money(amount) + ' on ' + ds(dl) + '?'); return False

def pending_amount(p):
    if p.get('offer'): return p['offer']['amount']
    if p.get('amount_ok'): return p['amount_ok']
    return p['floor'] if p.get('too_much') and p.get('floor_said') else p['past_due']

def parse_amount(x):
    try:
        a = float(str(x).replace(',', ''))
        return a if a > 0 else None
    except Exception: return None

def side_answers(it):
    if it == 'robot': say(S['robot'])
    elif it == 'scam': say(S['scam'])
    elif it == 'discount': say('I cannot offer a discount, a waiver or other terms.')
    elif it == 'change_promise': say('A recorded promise cannot be changed in this call; you can change it in the mobile app.')

def main():
    if st.get('stage') == 'closed': vars['act'] = 'end'; return
    vars['loops'] = int(V('loops') or 0) + 1
    if vars['loops'] > SPEC['loop_limit']:
        return close('no_promise', 'refused')
    if not st:
        st.update({'stage': 'confirm', 'asks': 1, 'wrong': 0, 'decl': 0, 'human': 0, 'talkref': 0, 'prods': [], 'dob': {}, 'digits': ''})
        return ask(S['opening'].replace('{title}', str(V('title'))).replace('{last_name}', str(V('last_name'))))
    pend = st.get('pending')
    if pend:
        st['pending'] = ''
        return on_result(pend)
    it = str(V('intent') or 'none')
    dw = str(V('date_words') or '').strip(); tw = str(V('time_words') or '').strip()
    am = parse_amount(V('amount')); dg = re.sub(r'\D', '', str(V('digits') or ''))
    dd, dm, dy = V('dob_day', 0), V('dob_month', 0), V('dob_year', 0)
    for k in ('date_words', 'time_words', 'digits'): vars[k] = ''
    for k in ('amount', 'dob_day', 'dob_month', 'dob_year'): vars[k] = 0
    vars['intent'] = 'none'
    stage = st['stage']
    # shared requests (A 42, 45, 4, 43) in every stage
    if it == 'human':
        st['human'] += 1
        if st['human'] >= 2 or st.get('human_asked'):
            if stage in ('confirm', 'third', 'dob', 'phone'):
                st['prods'] = []
            return call_transfer('general', 'human')
        st['human_asked'] = 1
        return ask('Before I transfer you, can I help you with this myself?')
    side_answers(it)
    if stage == 'confirm':
        if it == 'deceased': st['sympathy'] = 1; return close('not_reached', 'deceased', S['loss'])
        if it == 'wrong_number': return close('not_reached', 'wrong_number')
        if it == 'yes': st['stage'] = 'dob'; return ask('Thank you. For security, please tell me your date of birth.')
        if it == 'no':
            st['stage'] = 'third'; st['cbbad'] = 0
            if dw or tw: return third(dw, tw)
            return ask('When can ' + who + ' be reached?')
        if it == 'refuse_talk':
            st['decl'] += 1
            if st['decl'] >= 2: return close('not_verified', 'declined')
        if st['asks'] >= 2 and it not in ('robot', 'scam'):
            return close('not_reached', 'unclear')
        if it in ('robot', 'scam', 'what_about') and st.get('q_answered'):
            if st['asks'] >= 2: return close('not_reached', 'unclear')
        if it in ('robot', 'scam', 'what_about'): st['q_answered'] = 1
        if it == 'what_about': say('I can only discuss that with ' + who + '.')
        st['asks'] += 1
        return ask('Am I speaking with ' + who + '?')
    if stage == 'third':
        if it == 'deceased': return close('not_reached', 'deceased', S['loss'])
        if it == 'wrong_number': return close('not_reached', 'wrong_number')
        if it == 'refuse_talk': return close('not_reached', 'no_callback')
        if it == 'what_about': say('I can only discuss that with ' + who + '.')
        return third(dw, tw)
    if stage in ('dob', 'phone'):
        if it in ('refuse_talk', 'what_about', 'no') and not (dd or dm or dy or dg):
            st['decl'] += 1
            if st['decl'] >= 2: return close('not_verified', 'declined')
            say('These questions protect your account.')
            return ask('Please tell me your date of birth.' if stage == 'dob' else 'Please tell me the last four digits of the phone number we have on file.')
        if stage == 'dob':
            d = st['dob']
            for k, v in (('d', dd), ('m', dm), ('y', dy)):
                try:
                    v = int(v)
                    if v: d[k] = v
                except Exception: pass
            if 'y' in d and d['y'] < 100: d['y'] += 1900 if d['y'] > 26 else 2000
            if not d.get('d') or not d.get('m'): return ask('Please tell me the day and the month of your date of birth.' if not d.get('y') else 'And the day and the month?')
            if not d.get('y'): return ask('And the year?')
            try: iso = datetime.date(d['y'], d['m'], d['d']).isoformat()
            except Exception:
                st['dob'] = {}; return ask('I did not catch that. Please tell me your date of birth with the day, the month and the year.')
            return call_verify('date_of_birth', iso)
        dg2 = (st['digits'] + dg) if len(st['digits']) < 4 else dg
        if len(dg) >= 4: dg2 = dg[-4:]
        st['digits'] = dg2
        if not dg2: return ask('Please tell me the last four digits of the phone number we have on file.')
        if len(dg2) < 4: return ask('And the remaining digits?')
        return call_verify('phone_last4', dg2[:4])
    if stage == 'support':
        if it == 'yes': return call_transfer('support', 'support')
        p = st['prods'][st['cur']]
        if dw or am: st['stage'] = 'prod'; return prod(p, it, dw, am)
        for q in st['prods']:
            if q['status'] == 'open': q['status'] = 'hardship'
        st['stage'] = 'prod'; say('I understand.')
        return next_action()
    if stage == 'today_all':
        open_ = [p for p in st['prods'] if p['status'] == 'open']
        if it == 'plan': return call_transfer('restructuring', 'restructuring')
        if it == 'yes' and not dw and not am:
            for p in open_: agree(p, p['past_due'], today)
            st['stage'] = 'prod'; return next_action()
        st['stage'] = 'prod'
        if dw:
            d, kind = resolve_phrase(dw, today, SPEC['next_week_mode'])
            if d and d >= today:
                say_any = []
                for p in open_:
                    p['started'] = 1
                    dl = to_date(p['deadline'])
                    s = promise_date_state(d, today, dl, HOL)
                    if s == 'ok': agree(p, p['past_due'], d)
                    elif s == 'after_deadline': agree(p, p['past_due'], dl, True)
                    elif s == 'not_business_day':
                        nd = min(on_or_after_bd(d, HOL), dl); agree(p, p['past_due'], nd, nd != d)
                return next_action()
        p = open_[0]; st['cur'] = st['prods'].index(p)
        if it == 'too_much':
            for q in open_: q['too_much'] = 1
        if len(open_) == 1:
            p['started'] = 1
            return prod(p, it if it != 'no' else 'refuse', dw, am)
        if it in ('paid', 'dispute', 'hardship', 'robot', 'scam', 'what_about', 'discount') :
            p['started'] = 1
            return prod(p, it, dw, am)
        return next_action()
    if stage == 'prod':
        return prod(st['prods'][st['cur']], it, dw, am)
    if stage == 'readback':
        if it == 'plan': return call_transfer('restructuring', 'restructuring')
        if it == 'yes' and not dw and not am:
            st['confirmed'] = 1; return next_action()
        if dw:
            d, kind = resolve_phrase(dw, today, SPEC['next_week_mode'])
            if d and d >= today:
                for p in st['prods']:
                    if p['status'] == 'agreed':
                        dl = to_date(p['deadline']); s = promise_date_state(d, today, dl, HOL)
                        if s == 'ok': p['date'] = d.isoformat(); p['moved'] = False
                        elif s == 'after_deadline': p['date'] = dl.isoformat(); p['moved'] = True
                        elif s == 'not_business_day':
                            nd = min(on_or_after_bd(d, HOL), dl); p['date'] = nd.isoformat(); p['moved'] = True
                return readback()
        st['rbno'] = st.get('rbno', 0) + 1
        if st['rbno'] >= 2:
            for p in st['prods']:
                if p['status'] == 'agreed': p['status'] = 'refused'
            st['confirmed'] = 1; return next_action()
        return ask('What would you like to change: the date or the amount?')
    vars['act'] = 'talk'
    if not out: say('Sorry, could you say that again?')

def third(dw, tw):
    d, kind = resolve_phrase(dw or tw, today, SPEC['next_week_mode'])
    if d is None and (tw or dw): d = today
    hh = hhmm_from_words(tw or dw)
    if d is None and hh is None: return ask('When can ' + who + ' be reached? Please tell me a day and a time.')
    if hh is None: return ask('At what time?')
    w = SPEC['callback_window']
    s = callback_state(d, hh, now, w[0], w[1], HOL)
    if s == 'ok':
        st['pending'] = 'callback'; st['cbtries'] = 0; vars['a_date'] = d.isoformat(); vars['a_time'] = hh; vars['r_ok'] = ''; vars['act'] = 'callback'; return
    st['cbbad'] = st.get('cbbad', 0) + 1
    if st['cbbad'] >= 2: return close('not_reached', 'no_callback')
    return ask('I can only arrange a call back today or on the next business day, between 10:00 and 19:00. Is there another time?')

def call_verify(field, ans):
    st['pending'] = 'verify'; st['vfield'] = field; st.setdefault('vtries', 0)
    vars['v_field'] = field; vars['v_answer'] = ans; vars['r_ok'] = ''; vars['r_verified'] = ''; vars['r_hint'] = ''; vars['r_all'] = ''
    vars['act'] = 'verify'

def prod(p, it, dw, am):
    if it == 'plan': return call_transfer('restructuring', 'restructuring')
    if it == 'dispute': p['status'] = 'dispute'; say('I understand, I have noted that.' if False else 'I understand.'); return next_action()
    if it == 'paid' and not am:
        p['status'] = 'paid'; say('Payments can take one business day to appear.'); return next_action()
    if dw:
        d, kind = resolve_phrase(dw, today, SPEC['next_week_mode'])
        amount = am if am and p['floor'] and p['floor'] <= am <= p['past_due'] else pending_amount(p)
        if d is None:
            if not p.get('vague'):
                p['vague'] = 1; return ask('Which exact day can you pay?')
            p['offer'] = {'amount': amount, 'date': p['deadline'], 'kind': 'deadline'}
            return ask('Could you pay ' + money(amount) + ' on ' + ds(to_date(p['deadline'])) + '?')
        if check_date(p, d, amount): return next_action()
        return
    if am:
        fl = p['floor'] or p['past_due']
        if fl <= am <= p['past_due']:
            p['amount_ok'] = am
            if p.get('offer'): agree(p, am, to_date(p['offer']['date'])); return next_action()
            return ask('On which day can you pay ' + money(am) + '?')
        if am < fl:
            if p.get('floor_said'): p['status'] = 'refused'; say('I understand.'); return next_action()
            p['floor_said'] = 1; p['too_much'] = 1
            d = to_date(p['offer']['date']) if p.get('offer') else today
            p['offer'] = {'amount': fl, 'date': d.isoformat(), 'kind': 'floor'}
            return ask('I cannot record that amount. The lowest I can record is ' + money(fl) + '; the rest stays overdue. Could you pay ' + money(fl) + ' on ' + ds(d) + '?')
    if it == 'hardship':
        st['stage'] = 'support'
        return ask('I am sorry to hear that. Would you like me to connect you with our customer support team?')
    if it == 'yes' and p.get('offer'):
        o = p['offer']; agree(p, o['amount'], to_date(o['date'])); return next_action()
    if it == 'too_much' and p['floor'] and not p.get('floor_said'):
        p['floor_said'] = 1; p['too_much'] = 1
        d = to_date(p['offer']['date']) if p.get('offer') else today
        p['offer'] = {'amount': p['floor'], 'date': d.isoformat(), 'kind': 'floor'}
        return ask('I can record ' + money(p['floor']) + ' instead; the rest stays overdue. Could you pay ' + money(p['floor']) + ' on ' + ds(d) + '?')
    if it == 'refuse_talk':
        st['talkref'] += 1
        if st['talkref'] >= 2:
            for q in st['prods']:
                if q['status'] == 'open': q['status'] = 'refused'
            return next_action()
    if it in ('robot', 'scam', 'what_about', 'discount', 'change_promise') and p.get('offer'):
        o = p['offer']
        if it == 'what_about': say('I am calling about the late payment on your ' + pname(p) + '.')
        return ask('Could you pay ' + money(o['amount']) + ' on ' + ds(to_date(o['date'])) + '?')
    if it in ('robot', 'scam', 'what_about', 'discount'):
        return attempt(p)
    # flat refusal, no, non-answer, refused floor or deadline -> one attempt used
    if p.get('offer') and p['offer']['kind'] == 'floor' and p['att'] >= p['attempts']:
        p['status'] = 'refused'; say('I understand.'); return next_action()
    return attempt(p)

def on_result(pend):
    ok = tb(V('r_ok'))
    if pend == 'verify':
        if not ok:
            if str(V('r_ok')).strip().lower() == 'false':
                st['dob'] = {}; st['digits'] = ''
                return ask('I could not read that. ' + ('Please tell me your date of birth again.' if st['vfield'] == 'date_of_birth' else 'Please tell me the four digits again.'))
            st['vtries'] += 1
            if st['vtries'] >= 2: return close('no_promise', 'service_error', 'I am sorry, there is a technical problem.')
            say(S['tech']); return call_verify(V('v_field'), V('v_answer'))
        st['vtries'] = 0
        if tb(V('r_verified')):
            if st['vfield'] == 'date_of_birth' and not tb(V('r_all')):
                st['stage'] = 'phone'; return ask('Thank you. And what are the last four digits of the phone number we have on file?')
            st['pending'] = 'account'; st['atries'] = 0; vars['r_ok'] = ''; vars['act'] = 'account'; return
        if str(V('r_hint')) == 'day_month_swapped':
            st['dob'] = {}; return ask('Could you please say your date of birth again, with the month as a word?')
        st['wrong'] += 1; st['dob'] = {}; st['digits'] = ''
        if st['wrong'] >= SPEC['max_wrong']:
            return close('not_verified', 'failed', 'I cannot verify your identity. Please use the Freya Bank mobile app or visit a branch.')
        return ask('That does not match our records. ' + ('Please tell me your date of birth again.' if st['vfield'] == 'date_of_birth' else 'Please tell me the last four digits again.'))
    if pend == 'account':
        items = items_from_keys(vars, 'products') if ok else []
        if not items:
            try: items = items_from_vars(vars, ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'])
            except Exception: items = []
        items = [x for x in items if x.get('product_id')]
        if not ok or not items:
            st['atries'] = st.get('atries', 0) + 1
            if st['atries'] >= 2: return close('no_promise', 'service_error', 'I am sorry, there is a technical problem.')
            say(S['tech']); st['pending'] = 'account'; vars['r_ok'] = ''; vars['act'] = 'account'; return
        lines = []
        for x in items[:3]:
            b = band_for(x.get('days_late'), SPEC['bands']) or SPEC['bands'][-1]
            fl = floor_for(x, SPEC['floor_fields'])
            try: fl = float(fl) if fl not in (None, '') else None
            except Exception: fl = None
            p = {'product_id': str(x['product_id']), 'type': x.get('type'), 'card_last4': str(x.get('card_last4') or ''),
                 'past_due': float(x.get('past_due') or 0), 'days_late': int(float(x.get('days_late') or 0)),
                 'floor': fl, 'band': b['name'], 'attempts': b['attempts'],
                 'deadline': add_bd(today, b['deadline_bd'], HOL).isoformat(), 'att': 0, 'status': 'open', 'offer': None}
            st['prods'].append(p)
            lines.append('Your ' + pname(p) + ' has ' + money(p['past_due']) + ' past due and is ' + str(p['days_late']) + ' days late.')
        st['stage'] = 'today_all'
        q = 'Can you make this payment today?' if len(items) == 1 else 'Can you pay all of them in full today?'
        return ask('Thank you. I am calling from the collections team about a late payment. ' + ' '.join(lines) + ' ' + q)
    if pend == 'promise':
        p = [x for x in st['prods'] if x['status'] == 'recording'][0]
        if ok:
            p['status'] = 'promised'; st['promised_said'] = st.get('promised_said') or 1
            say('The promise for your ' + pname(p) + ' is recorded.')
            return next_action()
        p['tries'] += 1
        if p['tries'] >= 2:
            p['status'] = 'service_error'; say('I could not record the promise for your ' + pname(p) + '.')
            return next_action()
        say(S['tech']); return call_promise(p)
    if pend == 'note':
        p = [x for x in st['prods'] if x.get('noted') == 1][-1]
        if not ok and p.get('ntries', 0) < 1:
            p['ntries'] = 1; return call_note(p)
        p['noted'] = 2
        return next_action()
    if pend == 'callback':
        if ok: return close('not_reached', 'callback', 'I have arranged the call back.')
        st['cbtries'] += 1
        if st['cbtries'] >= 2: return close('not_reached', 'no_callback', 'I am sorry, I could not arrange the call back.')
        say(S['tech']); st['pending'] = 'callback'; vars['r_ok'] = ''; vars['act'] = 'callback'; return
    if pend == 'transfer':
        if ok: st['stage'] = 'closed'; st['outcome'] = 'transferred'; st['reason'] = st['transfer']; say('Thank you. Goodbye.'); vars['act'] = 'end'; return
        st['ttries'] = st.get('ttries', 0) + 1
        if st['ttries'] >= 2:
            st['transfer'] = ''
            return close('no_promise', 'service_error', 'I am sorry, I could not transfer you.')
        say(S['tech']); st['pending'] = 'transfer'; vars['r_ok'] = ''; vars['act'] = 'transfer'; return

try:
    vars['act'] = 'talk'
    main()
except Exception as e:
    vars['act'] = 'talk'
    vars['dbg'] = repr(e)[:200]
    if not out: out.append('Sorry, could you say that again?')
if vars.get('act') == 'talk' and not out: out.append('Sorry, could you say that again?')
if vars.get('act') in ('talk', 'end'):
    vars['say'] = ' '.join([st.pop('buf', '')] + out).strip() or 'Sorry, could you say that again?'
else:
    st['buf'] = (st.get('buf', '') + ' ' + ' '.join(out)).strip()
vars['outcome'] = st.get('outcome', '')
vars['reason'] = st.get('reason', '') or ''
vars['state_json'] = json.dumps(st)
