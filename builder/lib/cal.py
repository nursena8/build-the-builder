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
