# Calendar, date-phrase, band and window helpers for Freya code nodes.
# This file is pasted into code nodes, so it uses only `datetime` and `re` (the platform allows json, re, datetime)
# and defines plain functions. Every function takes its parameters explicitly; no brief values live here.
import datetime, re

_WD = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
_MON = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
_ONES = ['', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth',
         'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth', 'nineteenth', 'twentieth']
_ORD = {w: i for i, w in enumerate(_ONES) if w}
_ORD.update({'twenty first': 21, 'twenty second': 22, 'twenty third': 23, 'twenty fourth': 24, 'twenty fifth': 25, 'twenty sixth': 26,
             'twenty seventh': 27, 'twenty eighth': 28, 'twenty ninth': 29, 'thirtieth': 30, 'thirty first': 31})


def to_date(x):
    """A date, a datetime or a string that starts with YYYY-MM-DD -> datetime.date. None when it is not one."""
    if isinstance(x, datetime.datetime): return x.date()
    if isinstance(x, datetime.date): return x
    m = re.match(r'\s*(\d{4})-(\d{2})-(\d{2})', str(x or ''))
    if not m: return None
    try: return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError: return None


def parse_now(s):
    """'2026-10-14T11:00' (seconds and zone optional) -> datetime.datetime."""
    m = re.match(r'\s*(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?', str(s or ''))
    if not m: return None
    return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), int(m.group(5) or 0))


def is_bd(d, holidays, weekend=(5, 6)):
    return d.weekday() not in weekend and d.isoformat() not in holidays


def add_bd(d, n, holidays, weekend=(5, 6)):
    """The n-th business day after d (d itself never counts). n=0 returns d."""
    x, c = d, 0
    while c < n:
        x = x + datetime.timedelta(days=1)
        if is_bd(x, holidays, weekend): c += 1
    return x


def on_or_after_bd(d, holidays, weekend=(5, 6)):
    x = d
    while not is_bd(x, holidays, weekend): x = x + datetime.timedelta(days=1)
    return x


def last_bd_of_week(d, holidays, weekend=(5, 6)):
    """Last business day in the Monday-Sunday week that contains d."""
    monday = d - datetime.timedelta(days=d.weekday())
    best = None
    for i in range(7):
        x = monday + datetime.timedelta(days=i)
        if is_bd(x, holidays, weekend): best = x
    return best


def say_date(d):
    return _WD[d.weekday()].capitalize() + ' ' + str(d.day) + ' ' + _MON[d.month - 1].capitalize() + ' ' + str(d.year)


def _month_day(day, month, today):
    """The next date with this day of month (and month, when given) that is today or later."""
    y, m = today.year, (month or today.month)
    for _ in range(14):
        try:
            c = datetime.date(y, m, day)
            if c >= today or month and c.year > today.year: return c
        except ValueError:
            pass
        if month: y += 1
        else:
            m += 1
            if m > 12: m, y = 1, y + 1
    return None


def resolve_phrase(text, today, next_week_mode='following_week'):
    """Turn what a customer said into a date. Returns (date or None, kind).

    kinds: iso, today, tomorrow, day_after_tomorrow, day_of_month, this_weekday, next_weekday, weekday, none.
    The customer's words go in as text ("tomorrow morning", "the twentieth", "next Friday"). The date is worked out
    from `today`, the call's own date, never from the real clock.
    this_weekday: that weekday in the current Monday-Sunday week (can be in the past; the caller checks).
    next_weekday: that weekday in the following calendar week when next_week_mode is 'following_week';
                  the first such weekday after today when it is 'next_occurrence'.
    weekday: a bare weekday name; the first such weekday today or later.
    A written day of the month ("the 20th", "October 20", "20 October") wins over a weekday name said with it.
    """
    t = ' ' + re.sub(r'[^a-z0-9: ]+', ' ', str(text or '').lower().replace('-', ' ')) + ' '
    t = re.sub(r'\s+', ' ', t)
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', str(text or ''))
    if m:
        d = to_date(m.group(0))
        if d: return d, 'iso'
    if ' day after tomorrow ' in t: return today + datetime.timedelta(days=2), 'day_after_tomorrow'
    if ' tomorrow ' in t: return today + datetime.timedelta(days=1), 'tomorrow'
    mon = None
    for i, name in enumerate(_MON):
        if re.search(r'\b' + name[:3] + r'[a-z]*\b', t) and (name[:3] != 'mar' or ' march ' in t or re.search(r'\bmar\b', t)) and (name[:3] != 'may' or ' may ' in t):
            mon = i + 1; break
    day = None
    mm = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', t)
    if mm and 1 <= int(mm.group(1)) <= 31 and not re.search(r'\b' + mm.group(1) + r'\s*(?:am|pm|o ?clock|:)', t): day = int(mm.group(1))
    if day is None:
        for w in sorted(_ORD, key=len, reverse=True):
            if (' ' + w + ' ') in t: day = _ORD[w]; break
    if day is not None and (mon is not None or re.search(r'\b(the|on)\b', t) or re.search(r'\d(?:st|nd|rd|th)', t) or not re.search(r'\b(' + '|'.join(_WD) + r')\b', t)):
        d = _month_day(day, mon, today)
        if d: return d, 'day_of_month'
    for i, name in enumerate(_WD):
        if re.search(r'\b' + name + r'\b', t):
            monday = today - datetime.timedelta(days=today.weekday())
            if re.search(r'\bnext ' + name + r'\b', t):
                if next_week_mode == 'next_occurrence':
                    d = today + datetime.timedelta(days=1)
                    while d.weekday() != i: d += datetime.timedelta(days=1)
                    return d, 'next_weekday'
                return monday + datetime.timedelta(days=7 + i), 'next_weekday'
            if re.search(r'\b(this|coming) ' + name + r'\b', t): return monday + datetime.timedelta(days=i), 'this_weekday'
            d = today
            while d.weekday() != i: d += datetime.timedelta(days=1)
            return d, 'weekday'
    if ' today ' in t or ' tonight ' in t: return today, 'today'
    return None, 'none'


def promise_date_state(d, today, deadline, holidays, weekend=(5, 6)):
    """'ok', 'past', 'not_business_day' or 'after_deadline' for a promise date."""
    if d < today: return 'past'
    if not is_bd(d, holidays, weekend): return 'not_business_day'
    if d > deadline: return 'after_deadline'
    return 'ok'


def callback_state(d, hhmm, now, start, end, holidays, weekend=(5, 6)):
    """'ok', 'day', 'time' or 'past' for a callback date and 'HH:MM' time.
    The day must be today or the next business day; the time must lie in [start, end] (both included) and be after now."""
    today = now.date()
    allowed = []
    if is_bd(today, holidays, weekend): allowed.append(today)
    allowed.append(add_bd(today, 1, holidays, weekend))
    if d not in allowed: return 'day'
    if not re.match(r'^\d{2}:\d{2}$', str(hhmm or '')): return 'time'
    if hhmm < start or hhmm > end: return 'time'
    if datetime.datetime(d.year, d.month, d.day, int(hhmm[:2]), int(hhmm[3:])) <= now: return 'past'
    return 'ok'


def band_for(days_late, bands):
    """bands: list of dicts {min, max, name, deadline_bd, attempts}. The band whose [min, max] holds days_late, else None."""
    try: n = int(float(days_late))
    except (TypeError, ValueError): return None
    for b in bands:
        if b['min'] <= n <= b['max']: return b
    return None


def floor_for(product, floor_fields):
    """floor_fields: {product type: field name}. The product's floor amount, or None."""
    f = floor_fields.get(product.get('type'))
    return product.get(f) if f else None


def hhmm_from_words(text):
    """'eleven in the morning', '11', '3 pm', '15:30', 'half past two' -> 'HH:MM' or None. 'morning' with no hour -> None."""
    t = str(text or '').lower().replace('.', ':')
    nums = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12}
    m = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b', t)
    h = mi = None; ap = None
    if m and re.search(r'(:|am|pm|o ?clock|at \d|around \d|about \d|by \d)', t):
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    else:
        for w, v in nums.items():
            if re.search(r'\b' + w + r'\b', t): h, mi = v, 0; break
        mm = re.search(r'\b(half past|quarter past|quarter to)\b', t)
        if h is not None and mm: mi = {'half past': 30, 'quarter past': 15, 'quarter to': -15}[mm.group(1)]
        ap = 'pm' if re.search(r'\b(afternoon|evening|pm)\b', t) else ('am' if re.search(r'\b(morning|am)\b', t) else None)
    if h is None: return None
    if mi < 0: h, mi = h - 1, 45
    if ap == 'pm' and h < 12: h += 12
    if ap == 'am' and h == 12: h = 0
    if h > 23 or mi > 59: return None
    return '%02d:%02d' % (h, mi)


def items_from_vars(vars, fields, prefix='p', max_items=8):
    """Rebuild a list of records from flattened variables.
    The platform stores a response list only as single values ('data.products.0.past_due'), so map each field of
    item i to a variable '<prefix><i>_<field>' (for example p0_past_due) and call this to get [{...}, {...}].
    Items with no product_id-like first field value are dropped. Numbers stay as the platform gave them."""
    out = []
    for i in range(max_items):
        rec = {}
        for f in fields:
            v = vars.get('%s%d_%s' % (prefix, i, f))
            if v is not None and str(v) != '': rec[f] = v
        if not rec: break
        out.append(rec)
    return out


def items_from_keys(vars, name, max_items=20):
    """Rebuild a response list from the flattened variables the platform stores for every API node, with no mapping needed:
    '<node>_response.data.<name>.<i>.<field>' (seen live: 'load_account_response.data.products.0.past_due').
    A list variable the platform did store (a list, or a JSON/repr string) wins. Returns [{field: value}, ...] in index order."""
    import json, re
    p = vars.get(name)
    if isinstance(p, str):
        for t in (p, p.replace(chr(39), chr(34)).replace('True', 'true').replace('False', 'false').replace('None', 'null')):
            try: p = json.loads(t); break
            except Exception: pass
    if isinstance(p, list) and p and isinstance(p[0], dict): return p
    rows = {}
    pat = re.compile(r'(?:^|\.)' + re.escape(name) + r'\.(\d+)\.([A-Za-z_0-9]+)$')
    for k in list(vars.keys()):
        m = pat.search(str(k))
        if m and int(m.group(1)) < max_items: rows.setdefault(int(m.group(1)), {})[m.group(2)] = vars.get(k)
    return [rows[i] for i in sorted(rows)]


# ---------------------------------------------------------------------------------------------------------------------
# Turkish. Same contract as the English helpers. The text is first folded to plain ASCII lower case (ç->c, ğ->g, ı->i, ö->o,
# ş->s, ü->u, İ->i), so "Cuma'ya", "CUMAYA" and "cumaya" all read the same. `unicodedata` is not available in code nodes,
# so the fold is a table.
# ---------------------------------------------------------------------------------------------------------------------
_TR_FOLD = {'ı': 'i', 'İ': 'i', 'I': 'i', 'ğ': 'g', 'Ğ': 'g', 'ş': 's', 'Ş': 's', 'ç': 'c', 'Ç': 'c', 'ö': 'o', 'Ö': 'o', 'ü': 'u', 'Ü': 'u',
            'â': 'a', 'î': 'i', 'û': 'u', 'Â': 'a', 'Î': 'i', 'Û': 'u'}
_WD_TR = ['pazartesi', 'sali', 'carsamba', 'persembe', 'cuma', 'cumartesi', 'pazar']
_WD_TR_SAY = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
_MON_TR = ['ocak', 'subat', 'mart', 'nisan', 'mayis', 'haziran', 'temmuz', 'agustos', 'eylul', 'ekim', 'kasim', 'aralik']
_MON_TR_SAY = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
_NUM_TR = {'sifir': 0, 'bir': 1, 'iki': 2, 'uc': 3, 'dort': 4, 'bes': 5, 'alti': 6, 'yedi': 7, 'sekiz': 8, 'dokuz': 9,
           'on': 10, 'yirmi': 20, 'otuz': 30, 'kirk': 40, 'elli': 50, 'altmis': 60, 'yetmis': 70, 'seksen': 80, 'doksan': 90}
_NUM_END = ('', 'i', 'u', 'si', 'su', 'yi', 'yu', 'e', 'a', 'ye', 'ya', 'de', 'da', 'den', 'dan', 'inci', 'nci', 'uncu', 'ncu', 'ini', 'unu', 'sini', 'in', 'un', 'nin', 'li', 'lik')


def tr_ascii(text):
    """Fold Turkish text to ASCII lower case without punctuation (apostrophes vanish: "Cuma'ya" -> "cumaya")."""
    s = ''.join(_TR_FOLD.get(c, c) for c in str(text or '')).replace('̇', '').lower()
    s = re.sub(r"['’`´]", '', s)
    return ' ' + re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9: ]+', ' ', s.replace('-', ' '))).strip() + ' '


def _num_stem(tok):
    """A token like 'yirmisi', 'uce', 'bine' -> its number stem, else None. Also 'dokuzyuz' style joins return the list of stems."""
    if tok in ('yuz', 'bin'): return tok
    for stem in sorted(_NUM_TR, key=len, reverse=True):
        if tok.startswith(stem) and tok[len(stem):] in _NUM_END: return stem
    return None


def _split_join(tok):
    """'dokuzyuz' -> ['dokuz', 'yuz']; 'yirmiuc' -> ['yirmi', 'uc']; None when the token is not made of number words."""
    if _num_stem(tok): return [_num_stem(tok)]
    words = sorted(list(_NUM_TR) + ['yuz', 'bin'], key=len, reverse=True)
    out, rest = [], tok
    while rest:
        for w in words:
            if rest.startswith(w):
                out.append(w); rest = rest[len(w):]; break
        else:
            return None
    return out if len(out) > 1 else None


def numbers_tr(text):
    """Every number in a Turkish sentence, digits or words, in order: 'bin dokuz yuz seksen dokuz' -> [1989], 'yirmi uc subat' -> [23].
    Words: sifir..dokuz, on..doksan, yuz, bin ('iki bin yirmi alti' = 2026). Endings are ignored ('yirmisi' = 20)."""
    t = tr_ascii(text)
    out, cur, total, seen = [], 0, 0, False
    def flush():
        nonlocal cur, total, seen
        if seen: out.append(total + cur)
        cur = total = 0; seen = False
    for tok in t.split():
        md = re.fullmatch(r'(\d+)([a-z]{0,5})', tok)
        if md:  # '5', '5i' (from 5'i), '20si'
            flush(); out.append(int(md.group(1))); continue
        stems = _split_join(tok)
        if not stems:
            flush(); continue
        for st in stems:
            seen = True
            if st == 'yuz': cur = (cur or 1) * 100
            elif st == 'bin': total += (cur or 1) * 1000; cur = 0
            else:
                cur += _NUM_TR[st]
    flush()
    return out


def digits_tr(text):
    """'sifir dokuz sifir dort' or '0 9 0 4' or '0904' -> '0904' (a run of single digits and digit words)."""
    t = tr_ascii(text)
    out = ''
    for tok in t.split():
        if re.fullmatch(r'\d+', tok): out += tok
        elif tok in _NUM_TR and _NUM_TR[tok] < 10: out += str(_NUM_TR[tok])
    return out


def say_date_tr(d):
    return str(d.day) + ' ' + _MON_TR_SAY[d.month - 1] + ' ' + str(d.year) + ' ' + _WD_TR_SAY[d.weekday()]


def resolve_phrase_tr(text, today, next_week_mode='following_week'):
    """Turkish version of resolve_phrase. Returns (date or None, kind) with the same kinds.
    bugun, yarin, obur gun / yarindan sonra, 'bu cuma' (this), 'haftaya / gelecek / onumuzdeki / sonraki cuma' (next, see next_week_mode),
    a bare weekday ('cuma gunu'), 'ayin yirmisi', '20 Ekim', 'yirmi uc kasim', an ISO date."""
    raw = str(text or '')
    t = tr_ascii(raw)
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', raw)
    if m:
        d = to_date(m.group(0))
        if d: return d, 'iso'
    if re.search(r' (obur gun|yarindan sonra|ertesi gun)\w* ', t): return today + datetime.timedelta(days=2), 'day_after_tomorrow'
    if re.search(r' yarin\w* ', t): return today + datetime.timedelta(days=1), 'tomorrow'
    if ' saat ' not in t:   # dd.mm.yyyy, dd/mm/yyyy, dd.mm (Turkish order: day first)
        md = re.search(r'(?<![\d.,/])(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?(?![\d])', raw)
        if md and 1 <= int(md.group(2)) <= 12 and 1 <= int(md.group(1)) <= 31:
            dd, mm_ = int(md.group(1)), int(md.group(2))
            if md.group(3):
                yy = int(md.group(3)); yy = yy + 2000 if yy < 100 else yy
                try: return datetime.date(yy, mm_, dd), 'numeric_date'
                except ValueError: pass
            else:
                d = _month_day(dd, mm_, today)
                if d: return d, 'numeric_date'
    mon = None
    for i, name in enumerate(_MON_TR):
        if re.search(r' ' + name + r'(?:\w*)? ', t): mon = i + 1; break
    # a weekday name, longest first so 'cumartesi' is not read as 'cuma' and 'pazartesi' not as 'pazar'
    wd = None; rest = t
    for name in sorted(_WD_TR, key=len, reverse=True):
        mw = re.search(r' ' + name + r'\w* ', rest)
        if mw: wd = _WD_TR.index(name); break
    nums = [n for n in numbers_tr(t) if 1 <= n <= 31]
    dayn = None
    # a written day of the month wins over a weekday said with it ('yirmi altisi pazartesi gunu' = the 26th, a Monday): the number carries an ending
    # ('altisi', '26si') or is a digit group next to the weekday ('26 pazartesi')
    suffixed = any((_num_stem(tok) not in (None, tok)) or re.fullmatch(r'\d{1,2}[a-z]{1,5}', tok) for tok in t.split())
    digit_day = bool(re.search(r'(?<![\d:])\d{1,2}(?![\d:])', t)) and ' saat ' not in t
    if nums and (mon is not None or ' ayin ' in t or suffixed or digit_day or wd is None):
        # a clock time ('saat 11') is not a day of the month
        if not (wd is None and mon is None and re.search(r' saat ', t)):
            dayn = nums[0]
    if dayn is not None:
        d = _month_day(dayn, mon, today)
        if d: return d, 'day_of_month'
    if wd is not None:
        monday = today - datetime.timedelta(days=today.weekday())
        if re.search(r' (haftaya|gelecek|onumuzdeki|sonraki|gelecek hafta|haftaya) ', t) and not re.search(r' bu ', t):
            if next_week_mode == 'next_occurrence':
                d = today + datetime.timedelta(days=1)
                while d.weekday() != wd: d += datetime.timedelta(days=1)
                return d, 'next_weekday'
            return monday + datetime.timedelta(days=7 + wd), 'next_weekday'
        if re.search(r' bu ', t): return monday + datetime.timedelta(days=wd), 'this_weekday'
        d = today
        while d.weekday() != wd: d += datetime.timedelta(days=1)
        return d, 'weekday'
    if re.search(r' (bugun|bu aksam|bu gun)\w* ', t): return today, 'today'
    return None, 'none'


def hhmm_from_words_tr(text):
    """Turkish clock words -> 'HH:MM' or None. '15:30', 'saat 17', 'on bir', 'uc bucuk', 'ogleden sonra uc', 'aksam alti', 'sabah on'.
    'ogleden sonra', 'aksam', 'gece' put an hour below 12 in the afternoon; 'sabah' keeps it. An hour 1-6 said with no part of day is returned
    as said (03:30): the caller decides. 'sabah/ogle' with no hour -> None."""
    t = tr_ascii(text)
    h = mi = None
    m = re.search(r'\b(\d{1,2}):(\d{2})\b', t) or re.search(r'(?<![\d.,/])(\d{1,2})\.(\d{2})(?![\d.,/])', str(text or ''))   # 15:30 or 15.30
    if m and int(m.group(1)) <= 24 and int(m.group(2)) <= 59: h, mi = int(m.group(1)), int(m.group(2))
    elif m: m = None
    if h is not None: pass
    if h is None:
        m = re.search(r' saat (\d{1,2}) ', t) or re.search(r' (\d{1,2}) (?:bucuk|de|da|ye|ya|e|a)? ?', t)
        nums = numbers_tr(t)
        if m and re.search(r'saat \d|\d{1,2} ?(?:bucuk)', t): h, mi = int(m.group(1)), 0
        elif nums:
            cand = [n for n in nums if 0 <= n <= 24]
            if cand: h, mi = cand[0], 0
            # 'on bir' is two words but one hour: numbers_tr already adds them (10 + 1)
        if h is not None and re.search(r' bucuk ', t): mi = 30
        elif h is not None:
            mm = re.search(r' (\w+) dakika ', t)
            if mm and mm.group(1).isdigit(): mi = int(mm.group(1))
    if h is None: return None
    pm = bool(re.search(r' (ogleden sonra|aksam|aksamustu|gece yarisindan once)\w* ', t) or (' gece ' in t and 7 <= h <= 11))
    if pm and h < 12: h += 12
    if ' gece ' in t and h == 12: h = 0
    if h > 23 or mi > 59: return None
    return '%02d:%02d' % (h, mi)


def resolve_phrase_any(text, today, lang='en', next_week_mode='following_week'):
    """resolve_phrase for 'en' or 'tr'."""
    return resolve_phrase_tr(text, today, next_week_mode) if lang == 'tr' else resolve_phrase(text, today, next_week_mode)


def hhmm_from_words_any(text, lang='en'):
    return hhmm_from_words_tr(text) if lang == 'tr' else hhmm_from_words(text)


def say_date_any(d, lang='en'):
    return say_date_tr(d) if lang == 'tr' else say_date(d)


def amount_tr(text):
    """A Turkish amount -> float or None. '1.250,50' (dot = thousands, comma = decimals), '1250,5', '1250', '1.250', '250,00 TL',
    'bin iki yuz elli lira', 'uc yuz altmis bes lira elli kurus', '300 lira'. A dot followed by 1-2 digits and nothing else is a decimal ('365.50')."""
    raw = str(text or '')
    m = re.search(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+|\d+\.\d{1,2}(?!\d)|\d+', raw)
    if m:
        x = m.group(0)
        if ',' in x: x = x.replace('.', '').replace(',', '.')
        elif re.fullmatch(r'\d{1,3}(?:\.\d{3})+', x): x = x.replace('.', '')
        try: return float(x)
        except ValueError: return None
    t = tr_ascii(raw)
    before, _, after = t.partition(' lira ')
    n = numbers_tr(before if _ else t)
    if not n: return None
    total = float(n[0])
    if _ and ' kurus' in after:
        k = numbers_tr(after)
        if k and k[0] < 100: total += k[0] / 100.0
    return total


def say_amount_tr(x):
    """1250.5 -> '1.250,50 TL'; 365 -> '365 TL'."""
    s = '{:,.2f}'.format(float(x)).replace(',', 'X').replace('.', ',').replace('X', '.')
    if s.endswith(',00'): s = s[:-3]
    return s + ' TL'
