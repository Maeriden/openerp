# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class ResPartner(osv.Model):
	RELIABILITY = [
		("low", "Low"),
		("mid", "Medium"),
		("high", "High"),
	]

	_name = "res.partner"
	_inherit = "res.partner"
	_columns = {
		"reliability": fields.selection(RELIABILITY, "Reliability"),
		"reliability_desc": fields.text("Client profile description"),
		"reliability_effect": fields.text("Administrative effects"),
		"dimension": fields.char("Dimension", size=64, help="Sales figures, employees"),
		"operative_venues": fields.char("Operative venues", size=128),
	}
	
	def onchange_reliability(self, cr, uid, ids, rel, context=None):
		"""Placeholder"""
		vals = {}
		return {"value": vals}
	
