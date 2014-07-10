# -*- coding: utf-8 -*-
from datetime import timedelta

def ids_(model, cr, uid, ids, context=None):
	return ids

def to_delta(rule):
	delta = timedelta(0)
	sign = 1 if rule.occurs == "after" else -1
	if rule.uom == "days":
		delta = timedelta(days=rule.delta*sign)
	elif rule.uom == "hours":
		delta = timedelta(hours=rule.delta*sign)
	elif rule.uom == "minutes":
		delta = timedelta(minutes=rule.delta*sign)
	return delta
