MONTHS = ['january','february','march','april','may','june','july','august','september','october','november','december']
NUMW = {'zero':0,'oh':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12,
        'thirteen':13,'fourteen':14,'fifteen':15,'sixteen':16,'seventeen':17,'eighteen':18,'nineteen':19,'twenty':20,'thirty':30,
        'first':1,'second':2,'third':3,'fourth':4,'fifth':5,'sixth':6,'seventh':7,'eighth':8,'ninth':9,'tenth':10,'eleventh':11,'twelfth':12,
        'thirteenth':13,'fourteenth':14,'fifteenth':15,'sixteenth':16,'seventeenth':17,'eighteenth':18,'nineteenth':19,'twentieth':20,'thirtieth':30}
PNAME = {'credit_card': 'credit card', 'personal_loan': 'personal loan', 'car_loan': 'car loan'}


def S(k):
    return SPEC['say'][k]


def money(x):
    try:
        x = float(x)
    except Exception:
        return str(x)
    return ('%.2f' % x).rstrip('0').rstrip('.') + ' euros' if x != int(x) else '%d euros' % int(x)


def dob_parts(text):
    t = str(text or '').lower().replace(',', ' ').replace('/', ' ').replace('.', ' ').replace('-', ' ')
    day = month = year = None
    for i, m in enumerate(MONTHS):
        if m in t or re.search(r'\b' + m[:3] + r'\b', t):
            month = i + 1
    toks = re.findall(r'[a-z]+|\d+', t)
    nums = []
    i = 0
    while i < len(toks):
        w = toks[i]
        if w.isdigit():
            nums.append(int(w)); i += 1; continue
        if w in NUMW:
            v = NUMW[w]
            if v in (20, 30) and i + 1 < len(toks) and toks[i + 1] in NUMW and NUMW[toks[i + 1]] < 10:
                v += NUMW[toks[i + 1]]; i += 1
            nums.append(v)
        i += 1
    rest = []
    for n in nums:
        if n >= 1900 and year is None:
            year = n
        else:
            rest.append(n)
    if year is None:
        # nineteen eighty nine
        for a in range(len(rest) - 1):
            if rest[a] in (19, 20) and 0 <= rest[a + 1] <= 99:
                year = rest[a] * 100 + rest[a + 1]; rest = rest[:a] + rest[a + 2:]; break
    if month is None and len(rest) >= 2:
        day, month = rest[0], rest[1]
    elif rest:
        day = rest[0]
    return day, month, year


def digits_en(text):
    t = str(text or '').lower()
    out = ''
    for w in re.findall(r'[a-z]+|\d', t):
        if w.isdigit():
            out += w
        elif w in NUMW and NUMW[w] < 10 and w not in ('first',):
            out += str(NUMW[w])
        elif w in ('double',):
            out += '*'
    while '*' in out:
        k = out.index('*')
        out = out[:k] + (out[k + 1:k + 2] * 2) + out[k + 2:]
    return out


def amount_en(text):
    t = str(text or '').lower().replace(',', '')
    m = re.search(r'\d+(\.\d+)?', t)
    if m:
        return float(m.group(0))
    tot = 0; cur = 0; found = False
    for w in re.findall(r'[a-z]+', t):
        if w in NUMW and w not in ('first',):
            cur += NUMW[w]; found = True
        elif w == 'hundred':
            cur = max(cur, 1) * 100; found = True
        elif w == 'thousand':
            tot += max(cur, 1) * 1000; cur = 0; found = True
    return float(tot + cur) if found else None


def vague(text):
    t = str(text or '').lower()
    return any(w in t for w in ('next week', 'end of', 'salary', 'payday', 'soon', 'later', 'month', 'some time', 'sometime'))


def close(key, say):
    o, r = SPEC['outcomes'][key]
    vars['outcome'] = o; vars['reason'] = r
    vars['bye'] = (say + ' ' if say else '') + S('goodbye')
    vars['st'] = 'closed'; vars['act'] = 'end'
    return True


def talk(text):
    vars['say'] = text.strip(); vars['act'] = 'talk'
    return True


def prods():
    try:
        return json.loads(vars.get('prods_json') or '[]')
    except Exception:
        return []


def save(ps):
    vars['prods_json'] = json.dumps(ps)


def pname(p):
    n = PNAME.get(p.get('type'), 'account')
    if p.get('type') == 'credit_card' and p.get('card_last4'):
        n += ' ending ' + str(p.get('card_last4'))
    return n


def finish_products(prefix):
    """All products decided: read back promises, or go to notes and closing."""
    ps = prods()
    agreed = [p for p in ps if p.get('state') == 'agreed']
    if agreed:
        parts = []
        for p in agreed:
            s = 'your ' + pname(p) + ': ' + money(p['amt']) + ' on ' + say_date(to_date(p['date']))
            if p.get('capped'):
                s += ' (the latest date I can record for it)'
            elif p.get('shifted'):
                s += ' (the next business day after the day you named)'
            parts.append(s)
        vars['st'] = 'readback'
        vars['rb_n'] = int(vars.get('rb_n') or 0) + 1
        return talk(prefix + ' To confirm: ' + '; '.join(parts) + '. Do you confirm?')
    vars['st'] = 'recording'
    return run_queue(prefix)


def run_queue(prefix):
    """Record agreed+confirmed promises one by one, then notes, then close."""
    ps = prods()
    vars['pre'] = (str(vars.get('pre') or '') + ' ' + prefix).strip()
    for i, p in enumerate(ps):
        if p.get('state') == 'confirmed':
            vars['c_pid'] = p['product_id']; vars['c_amt'] = p['amt']; vars['c_date'] = p['date']
            vars['cur'] = i; vars['act'] = 'promise'; vars['pending'] = 'promise'
            return True
    if vars.get('transfer') not in ('restructuring', 'human', 'support'):
        for i, p in enumerate(ps):
            if p.get('state') not in ('recorded',) and not p.get('noted'):
                r = p.get('reason') or 'refused'
                if p.get('state') in ('open', 'agreed', 'confirmed', None):
                    r = 'refused' if not p.get('reason') else r
                p['reason'] = r; save(ps)
                vars['n_pid'] = p['product_id']; vars['n_reason'] = r; vars['n_text'] = 'Customer outcome: ' + r
                vars['cur'] = i; vars['act'] = 'note'; vars['pending'] = 'note'
                return True
    return final_close()


def final_close():
    ps = prods()
    pre = str(vars.get('pre') or '')
    rec = [p for p in ps if p.get('state') == 'recorded']
    tr = vars.get('transfer')
    if tr in ('restructuring', 'human', 'support'):
        return close(tr, pre)
    if rec:
        return close('promise', (pre + ' ' + S('sms')).strip())
    if ps and all(p.get('reason') == 'paid' for p in ps):
        return close('paid', pre)
    for p in ps:
        if p.get('reason') != 'paid':
            return close(p.get('reason') or 'refused', pre)
    return close('refused', pre)


def do_transfer(kind, prefix):
    # B10: promises agreed but not recorded are dropped; no notes at all
    vars['transfer'] = kind; vars['queue'] = SPEC['queues'][kind]
    if vars.get('transfer_done') == 'yes':
        return final_close()
    vars['transfer_done'] = 'yes'; vars['pending'] = 'transfer'; vars['act'] = 'transfer'
    vars['pre'] = prefix
    return True


def offer_text(p):
    """Persuasion attempt text (A30)."""
    today = parse_now(vars.get('now')).date()
    H = SPEC['holidays']
    if p['attempt'] == 1 and p.get('vague_dl'):
        # A21: still no exact day after asking once -> propose the deadline
        d = to_date(p['deadline']); amt = p['floor'] if p.get('too_much') and p.get('floor') else p['past_due']
        p['off_date'] = d.isoformat(); p['off_amt'] = amt; p['dl_offered'] = True
        return 'For your ' + pname(p) + ', the latest date I can record is ' + say_date(d) + '. Could you pay ' + money(amt) + ' by then?'
    if p['attempt'] == 1:
        d = last_bd_of_week(today, H)
        if d <= today:
            d = last_bd_of_week(today + datetime.timedelta(days=7), H)
        if d > to_date(p['deadline']):
            d = to_date(p['deadline'])
        amt = p['floor'] if p.get('too_much') and p.get('floor') else p['past_due']
    else:
        d = to_date(p['deadline']); amt = p['floor'] or p['past_due']
    p['off_date'] = d.isoformat(); p['off_amt'] = amt
    extra = ' The rest stays overdue.' if amt != p['past_due'] else ''
    return 'For your ' + pname(p) + ', could you pay ' + money(amt) + ' on ' + say_date(d) + '?' + extra


def next_product(prefix):
    ps = prods()
    for i, p in enumerate(ps):
        if p.get('state') == 'open':
            vars['cur'] = i
            p['attempt'] = 1
            t = offer_text(p)
            save(ps)
            vars['st'] = 'prod'
            return talk(prefix + ' ' + t)
    return finish_products(prefix)


def check_date(p, d, amt, prefix):
    """Check a customer date for product p (A19, A20, A23). Returns sentence or marks agreed."""
    today = parse_now(vars.get('now')).date()
    H = SPEC['holidays']; dl = to_date(p['deadline'])
    stt = promise_date_state(d, today, dl, H)
    if stt == 'ok':
        p['state'] = 'agreed'; p['amt'] = amt; p['date'] = d.isoformat(); p['capped'] = False; p['shifted'] = False
        return None
    if stt == 'past':
        return 'That date has passed. Which day from today on can you pay?'
    if stt == 'not_business_day':
        nd = on_or_after_bd(d, H)
        p['off_date'] = nd.isoformat(); p['off_amt'] = amt
        return 'That day is not a business day. Could you pay on ' + say_date(nd) + ' instead?'
    p['off_date'] = dl.isoformat(); p['off_amt'] = amt; p['dl_offered'] = True
    return 'For your ' + pname(p) + ' the latest date I can record is ' + say_date(dl) + '. Can you pay ' + money(amt) + ' by then?'


def refusal(p, ps, prefix):
    """A flat refusal or non-answer uses one attempt (A30, A31, B5)."""
    if p['attempt'] < p['attempts']:
        p['attempt'] += 1
        t = offer_text(p); save(ps)
        return talk(prefix + ' ' + t)
    p['state'] = 'done'; p['reason'] = 'refused'; save(ps)
    return next_product(prefix)


def main():
    it = str(vars.get('intent') or 'none')
    side = str(vars.get('side_q') or 'none')
    dw = str(vars.get('date_words') or '').strip()
    aw = str(vars.get('amount_words') or '').strip()
    tw = str(vars.get('time_words') or '').strip()
    ans = str(vars.get('answer_words') or '').strip()
    for k in ('date_words', 'amount_words', 'time_words', 'answer_words'):
        vars[k] = ''
    vars['intent'] = 'none'; vars['side_q'] = 'none'
    if dw.lower() == 'none': dw = ''
    if aw.lower() == 'none': aw = ''
    if tw.lower() == 'none': tw = ''
    if ans.lower() == 'none': ans = ''
    st = vars.get('st') or 'confirm'
    now = parse_now(vars.get('now')); today = now.date(); H = SPEC['holidays']
    pend = vars.get('pending') or ''
    vars['pending'] = ''
    LOOPGUARD
    pre = ''
    verified = st not in ('confirm', 'third', 'dob', 'phone')
    if side == 'robot': pre += S('robot') + ' '
    elif side == 'scam': pre += S('scam') + ' '
    elif side == 'other_question' and verified: pre += S('no_info') + ' '

    # ---------- tool results ----------
    if pend == 'callback':
        ok = str(vars.get('callback_response.data.ok')).lower() == 'true'
        if ok:
            return close('callback', 'Thank you, we will call back then.')
        n = int(vars.get('cb_fail') or 0) + 1; vars['cb_fail'] = n
        if n < 2:
            vars['pending'] = 'callback'; vars['act'] = 'callback'; return True
        return close('no_callback', '')
    if pend == 'verify':
        okv = str(vars.get('verify_response.data.ok')).lower()
        ver = str(vars.get('verify_response.data.verified')).lower()
        allv = str(vars.get('verify_response.data.all_verified')).lower()
        hint = str(vars.get('verify_response.data.hint') or '')
        left = vars.get('verify_response.data.wrong_answers_left')
        if okv != 'true' or ver not in ('true', 'false'):
            n = int(vars.get('v_fail') or 0) + 1; vars['v_fail'] = n
            if n >= 2:
                return close('failed', 'Please use the mobile app or visit a branch.')
            if st == 'dob':
                vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''
                return talk(S('tech') + ' Could you say your date of birth again, with the month as a word?')
            vars['ph'] = ''
            return talk(S('tech') + ' Could you say the last four digits of your phone number again?')
        vars['v_fail'] = 0
        if allv == 'true':
            vars['st'] = 'account'; vars['act'] = 'account'; vars['pending'] = 'account'; return True
        if ver == 'true':
            vars['st'] = 'phone'; vars['ph'] = ''
            return talk('Thank you. What are the last four digits of your phone number?')
        if hint == 'day_month_swapped':
            vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''
            return talk('Could you say your date of birth again, with the month as a word, for example the fifth of March?')
        try:
            lf = int(left)
        except Exception:
            lf = 3 - (int(vars.get('wrong') or 0) + 1)
        vars['wrong'] = int(vars.get('wrong') or 0) + 1
        if lf <= 0 or int(vars['wrong']) >= 3:
            return close('failed', 'I could not verify your identity. Please use the mobile app or visit a branch.')
        if st == 'dob':
            vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''
            return talk('That does not match our records. Could you tell me your date of birth again?')
        vars['ph'] = ''
        return talk('That does not match our records. Could you tell me the last four digits of your phone number again?')
    if pend == 'account':
        items = items_from_keys(vars, 'products')
        if not items:
            items = items_from_vars(vars, ['product_id', 'type', 'card_last4', 'past_due', 'days_late', 'minimum_payment', 'instalment_amount'])
        ok = str(vars.get('account_response.data.ok')).lower() == 'true' or bool(items)
        if not ok or not items:
            n = int(vars.get('a_fail') or 0) + 1; vars['a_fail'] = n
            if n < 2:
                vars['act'] = 'account'; vars['pending'] = 'account'; return True
            return close('service_error', 'There was a technical problem and I cannot continue.')
        ps = []; lines = []
        for p in items[:SPEC['max_products']]:
            try:
                dlate = int(float(p.get('days_late')))
            except Exception:
                dlate = 0
            b = band_for(dlate, SPEC['bands']) or SPEC['bands'][-1]
            fl = floor_for(p, SPEC['floor_fields'])
            q = {'product_id': str(p.get('product_id')), 'type': p.get('type'), 'card_last4': str(p.get('card_last4') or ''),
                 'past_due': float(p.get('past_due') or 0), 'days_late': dlate, 'band': b['name'], 'attempts': b['attempts'],
                 'deadline': add_bd(today, b['deadline_bd'], H).isoformat(), 'floor': float(fl) if fl not in (None, '') else None,
                 'state': 'open', 'attempt': 0}
            ps.append(q)
            lines.append('Your ' + pname(q) + ' has ' + money(q['past_due']) + ' past due and is ' + str(dlate) + ' days late.')
        save(ps)
        vars['facts'] = ' '.join(lines)
        vars['st'] = 'today'
        intro = 'Thank you. I am calling from the collections team about late payments. ' if len(ps) > 1 else 'Thank you. I am calling from the collections team about a late payment. '
        return talk(intro + ' '.join(lines) + (' Can you make all of these payments today?' if len(ps) > 1 else ' Can you make this payment today?'))
    if pend == 'promise':
        ps = prods(); i = int(vars.get('cur') or 0); p = ps[i]
        if str(vars.get('promise_response.data.ok')).lower() == 'true':
            p['state'] = 'recorded'; save(ps); vars['p_fail'] = 0
            return run_queue('The promise for your ' + pname(p) + ' is recorded.')
        n = int(vars.get('p_fail') or 0) + 1; vars['p_fail'] = n
        if n < 2:
            vars['act'] = 'promise'; vars['pending'] = 'promise'; return True
        vars['p_fail'] = 0
        p['state'] = 'done'; p['reason'] = 'service_error'; save(ps)
        return run_queue('I could not record the promise for your ' + pname(p) + '.')
    if pend == 'note':
        ps = prods(); i = int(vars.get('cur') or 0)
        ok = str(vars.get('note_response.data.ok')).lower() == 'true'
        n = int(vars.get('n_fail') or 0) + 1
        if ok or n >= 2:
            ps[i]['noted'] = True; save(ps); vars['n_fail'] = 0
        else:
            vars['n_fail'] = n
        return run_queue('')
    if pend == 'transfer':
        return final_close()

    # ---------- requests that apply in every stage ----------
    if it == 'human':
        if vars.get('human_asked') == 'yes':
            return do_transfer('human', 'I will connect you with a colleague now.')
        vars['human_asked'] = 'yes'
        return talk(pre + S('help_first'))
    if it == 'not_talk' or (it == 'purpose' and st in ('dob', 'phone')):
        n = int(vars.get('decl') or 0) + 1; vars['decl'] = n
        if n >= 2:
            if not verified:
                return close('declined', '')
            ps = prods()
            for p in ps:
                if p.get('state') in ('open', 'agreed'):
                    p['state'] = 'done'; p['reason'] = p.get('reason') or 'refused'
            save(ps)
            return run_queue('')
        if st in ('dob', 'phone'):
            q = 'What is your date of birth?' if st == 'dob' else 'What are the last four digits of your phone number?'
            return talk(pre + S('protect') + ' ' + q)
        if st == 'confirm':
            return talk(pre + 'I understand. Am I speaking with ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + '?')
        if not verified:
            return talk(pre + 'I understand. When can ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + ' be reached?')
        # verified: fall through to the stage as a refusal

    # ---------- opening ----------
    if st == 'confirm':
        if it == 'wrong_number':
            return close('wrong_number', 'Sorry for the trouble.')
        if it == 'deceased':
            return close('deceased', S('loss'))
        if it == 'yes':
            vars['st'] = 'dob'
            return talk(pre + 'Thank you. Before we continue, I need to ask two security questions. What is your date of birth?')
        if it == 'not_me':
            vars['st'] = 'third'
            if tw or dw:
                st = 'third'
            else:
                return talk(pre + 'When can ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + ' be reached?')
        else:
            n = int(vars.get('asks') or 1) + 1; vars['asks'] = n
            if n > 2:
                return close('unclear', '')
            if it == 'purpose':
                pre += 'I can explain once I know I am speaking with the right person. '
            return talk(pre + 'Am I speaking with ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + '?')
    if st == 'third':
        if it == 'wrong_number':
            return close('wrong_number', 'Sorry for the trouble.')
        if it == 'deceased':
            return close('deceased', S('loss'))
        if it == 'yes' and not (tw or dw):
            return talk(pre + 'What day and time would suit?')
        if not (tw or dw):
            if it == 'no':
                return close('no_callback', '')
            return talk(pre + 'I can only say that this is Freya Bank. When can ' + str(vars.get('title') or '') + ' ' + str(vars.get('last_name') or '') + ' be reached?')
        d, kind = resolve_phrase(dw or tw, today, SPEC['next_week_mode'])
        if d is None:
            d = today
        hh = hhmm_from_words(tw or dw)
        if not hh:
            vars['cb_day'] = d.isoformat()
            return talk(pre + 'At what time?')
        s = callback_state(d, hh, now, SPEC['cb_start'], SPEC['cb_end'], H)
        if s == 'ok':
            vars['cb_date'] = d.isoformat(); vars['cb_time'] = hh
            vars['pending'] = 'callback'; vars['act'] = 'callback'; return True
        n = int(vars.get('cb_out') or 0) + 1; vars['cb_out'] = n
        if n >= 2:
            return close('no_callback', '')
        return talk(pre + 'I can only arrange a call today or on the next business day, between 10:00 and 19:00. Is there another time?')
    if st == 'dob':
        dd, mm, yy = dob_parts(ans or dw)
        if dd: vars['dob_d'] = dd
        if mm: vars['dob_m'] = mm
        if yy: vars['dob_y'] = yy
        dd, mm, yy = vars.get('dob_d'), vars.get('dob_m'), vars.get('dob_y')
        if dd and mm and yy:
            try:
                vars['v_answer'] = datetime.date(int(yy), int(mm), int(dd)).isoformat()
            except Exception:
                try:
                    vars['v_answer'] = datetime.date(int(yy), int(dd), int(mm)).isoformat()
                except Exception:
                    vars['dob_d'] = ''; vars['dob_m'] = ''; vars['dob_y'] = ''
                    return talk(pre + 'Sorry, could you say your date of birth again, with the month as a word?')
            vars['v_field'] = 'date_of_birth'; vars['pending'] = 'verify'; vars['act'] = 'verify'
            return True
        if dd or mm or yy:
            miss = 'the year' if not yy else ('the month' if not mm else 'the day')
            return talk(pre + 'Thank you. And ' + miss + '?')
        return talk(pre + 'What is your date of birth?')
    if st == 'phone':
        dg = digits_en(ans or aw)
        cur = str(vars.get('ph') or '') + dg
        if len(cur) > 4 and len(dg) >= 4:
            cur = dg[-4:]
        vars['ph'] = cur
        if len(cur) >= 4:
            vars['v_answer'] = cur[-4:]; vars['v_field'] = 'phone_last4'; vars['pending'] = 'verify'; vars['act'] = 'verify'
            return True
        if cur:
            return talk(pre + 'Thank you. And the remaining ' + str(4 - len(cur)) + ' digits?')
        return talk(pre + 'What are the last four digits of your phone number?')

    # ---------- verified stages ----------
    ps = prods()
    if it == 'change_recorded':
        pre += S('app') + ' '
    if it == 'discount':
        pre += S('no_discount') + ' '
    if it == 'plan':
        return do_transfer('restructuring', 'I will connect you with our restructuring team.')
    d = None
    if dw:
        d, kind = resolve_phrase(dw, today, SPEC['next_week_mode'])
        if d is not None and d < today and it in ('paid', 'dispute'):
            d = None
    amt = amount_en(aw) if aw else None
    if vars.get('support_offered') == 'yes' and vars.get('support_answered') != 'yes' and it in ('yes', 'no'):
        vars['support_answered'] = 'yes'
        if it == 'yes':
            return do_transfer('support', 'I will connect you with our customer support team.')
        for p in ps:
            if p.get('state') == 'open':
                p['state'] = 'done'; p['reason'] = 'hardship'
        save(ps)
        if d is None and amt is None:
            return finish_products(pre.strip())
    if it == 'hardship' and d is None and amt is None:
        if vars.get('support_offered') != 'yes':
            vars['support_offered'] = 'yes'
            return talk(pre + S('sympathy') + ' ' + S('support_offer'))
        for p in ps:
            if p.get('state') == 'open':
                p['state'] = 'done'; p['reason'] = 'hardship'
        save(ps)
        return finish_products(pre.strip())

    if st == 'today':
        if it in ('paid', 'dispute') and d is None and amt is None:
            for p in ps:
                p['state'] = 'done'; p['reason'] = it
            save(ps)
            return finish_products(pre + (S('paid') if it == 'paid' else 'I understand, I will note that.'))
        if it == 'yes' and d is None and amt is None:
            for p in ps:
                p['state'] = 'agreed'; p['amt'] = p['past_due']; p['date'] = today.isoformat()
            save(ps)
            return finish_products(pre.strip())
        if d is not None:
            msgs = []
            for p in ps:
                a = p['past_due']
                if len(ps) == 1 and amt is not None and p.get('floor') and p['floor'] <= amt <= p['past_due']:
                    a = amt
                dl = to_date(p['deadline'])
                if d > dl:
                    p['state'] = 'agreed'; p['amt'] = a; p['date'] = dl.isoformat(); p['capped'] = True
                else:
                    r = check_date(p, d, a, '')
                    if r:
                        msgs.append(r); p['state'] = 'open'
                        nd = on_or_after_bd(d, H) if d >= today else today
                        if nd <= dl and d >= today:
                            p['state'] = 'agreed'; p['date'] = nd.isoformat(); p['amt'] = a; p['capped'] = False; p['shifted'] = True
            save(ps)
            if any(p.get('state') == 'open' for p in ps):
                return next_product(pre.strip())
            return finish_products(pre.strip())
        if vague(dw) and vars.get('vague_asked') != 'yes':
            vars['vague_asked'] = 'yes'
            return talk(pre + 'Which exact day can you pay?')
        if vague(dw):
            # A21: asked once already, still no exact day -> each product is offered its own deadline
            for p in ps:
                if p.get('state') == 'open':
                    p['vague_dl'] = True; p['vague_asked'] = True
            save(ps)
            return next_product(pre.strip())
        if it in ('unclear',) and not dw and not aw:
            return talk(pre + ('Can you make all of these payments today?' if len(ps) > 1 else 'Can you make this payment today?'))
        if it == 'too_much':
            for p in ps:
                p['too_much'] = True
            save(ps)
        if (it == 'other' and side != 'none') or it in ('discount', 'change_recorded'):
            return talk(pre + ('Can you make all of these payments today?' if len(ps) > 1 else 'Can you make this payment today?'))
        return next_product(pre.strip())

    if st == 'prod':
        i = int(vars.get('cur') or 0); p = ps[i]
        if it in ('paid', 'dispute') and d is None and amt is None:
            p['state'] = 'done'; p['reason'] = it; save(ps)
            return next_product(pre + (S('paid') if it == 'paid' else 'I understand, I will note that.'))
        if amt is not None:
            fl = p.get('floor') or p['past_due']
            if fl <= amt <= p['past_due']:
                dd = d or (to_date(p['off_date']) if p.get('off_date') else None)
                if dd is None:
                    p['off_amt'] = amt; save(ps)
                    return talk(pre + 'Thank you. On which day can you pay ' + money(amt) + '?')
                r = check_date(p, dd, amt, '')
                save(ps)
                if r:
                    return talk(pre + r)
                return next_product(pre.strip())
            if amt < fl:
                if p.get('floor_offered'):
                    return refusal(p, ps, pre + 'That amount cannot be recorded.')
                p['floor_offered'] = True; p['too_much'] = True
                p['off_amt'] = fl; save(ps)
                return talk(pre + 'That amount cannot be recorded. The lowest amount I can record is ' + money(fl) + '; the rest stays overdue. Can you pay ' + money(fl) + ' on ' + say_date(to_date(p.get('off_date') or p['deadline'])) + '?')
        if d is not None:
            a = p.get('off_amt') or p['past_due']
            r = check_date(p, d, a, '')
            save(ps)
            if r:
                return talk(pre + r)
            return next_product(pre.strip())
        if vague(dw) and not p.get('vague_asked'):
            p['vague_asked'] = True; save(ps)
            return talk(pre + 'Which exact day can you pay?')
        if vague(dw) and p.get('vague_asked'):
            dl = to_date(p['deadline']); p['off_date'] = dl.isoformat(); save(ps)
            return talk(pre + 'The latest date I can record is ' + say_date(dl) + '. Can you pay ' + money(p.get('off_amt') or p['past_due']) + ' by then?')
        if it == 'yes':
            p['state'] = 'agreed'; p['amt'] = p.get('off_amt') or p['past_due']; p['date'] = p.get('off_date') or p['deadline']
            p['capped'] = bool(p.get('dl_offered')); save(ps)
            return next_product(pre.strip())
        if it == 'too_much' and p.get('floor') and not p.get('floor_offered'):
            p['floor_offered'] = True; p['too_much'] = True; p['off_amt'] = p['floor']; save(ps)
            return talk(pre + 'I understand. Could you pay ' + money(p['floor']) + ' on ' + say_date(to_date(p.get('off_date') or p['deadline'])) + '? The rest stays overdue.')
        if (it in ('other', 'unclear') and side != 'none') or it in ('discount', 'change_recorded'):
            return talk(pre + 'Could you pay ' + money(p.get('off_amt') or p['past_due']) + ' on ' + say_date(to_date(p.get('off_date') or p['deadline'])) + '?')
        return refusal(p, ps, pre.strip())

    if st == 'readback':
        if it == 'yes' and d is None and amt is None:
            for p in ps:
                if p.get('state') == 'agreed':
                    p['state'] = 'confirmed'
            save(ps); vars['st'] = 'recording'
            return run_queue(pre.strip())
        if d is not None:
            for p in ps:
                if p.get('state') == 'agreed':
                    dl = to_date(p['deadline'])
                    if d > dl:
                        p['date'] = dl.isoformat(); p['capped'] = True
                    elif promise_date_state(d, today, dl, H) == 'ok':
                        p['date'] = d.isoformat(); p['capped'] = False
                    elif d >= today:
                        p['date'] = on_or_after_bd(d, H).isoformat(); p['capped'] = False; p['shifted'] = True
            save(ps)
        if amt is not None:
            # A35: a new amount at the read-back is checked against A27, then read back again
            ag = [p for p in ps if p.get('state') == 'agreed']
            if len(ag) == 1:
                p = ag[0]; fl = p.get('floor') or p['past_due']
                if fl <= amt <= p['past_due']:
                    p['amt'] = amt
                else:
                    pre += 'That amount cannot be recorded. I can record from ' + money(fl) + ' up to ' + money(p['past_due']) + '. '
                save(ps)
        if int(vars.get('rb_n') or 0) >= 3:
            for p in ps:
                if p.get('state') == 'agreed':
                    p['state'] = 'done'; p['reason'] = 'refused'
            save(ps); vars['st'] = 'recording'
            return run_queue(pre.strip())
        if it == 'no' and d is None and amt is None:
            for p in ps:
                if p.get('state') == 'agreed':
                    p['state'] = 'open'; p['attempt'] = 0
            save(ps)
            return next_product(pre.strip())
        return finish_products(pre.strip())
    return talk(pre + 'Sorry, could you repeat that?')


try:
    main()
except Exception as e:
    vars['say'] = 'Sorry, could you repeat that?'; vars['act'] = 'talk'; vars['err'] = str(e)[:200]
