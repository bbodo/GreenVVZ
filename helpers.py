import collections
from datetime import date
from dateutil.relativedelta import relativedelta
import re

# returns a dictionary containing the values 'year' and 'session' as ref_date (default is today)
# ref_date the date to compare to the target_date, which is feb of the ref year by default
def get_session(ref_date=date.today(), target_date=None):
# SPRING: PREV YEAR 004
# FALL:   SAME YEAR 003
    # if no target_date given, simply use ref_date year and 1. feb
    target_date = target_date if target_date != None else date(ref_date.year, 2, 1)
    if ref_date < target_date:
        return {'year': ref_date.year - 1, 'session': 3}
    elif ref_date < target_date+relativedelta(months=6):
        return {'year': ref_date.year - 1, 'session': 4}
    else:
        return {'year': ref_date.year, 'session': 3}

def get_current_sessions(num_prev_semesters=4):
    sessions = [ # next session (6 months from now)
        get_session(date.today()+relativedelta(months=6)), 
        get_session(date.today())
    ] # current session
    # previous sessions: 6 months back per semester
    for months in range(6, 6*num_prev_semesters+1, 6):
        sessions.append(get_session(date.today()-relativedelta(months=months)))
    return sessions

# returns current year as int
def current_year():
    return date.today().year
