# coding: utf-8
def format_time(t):
    return t.replace(microsecond=0).isoformat() + 'Z'