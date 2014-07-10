# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class SaleOrder(osv.Model):
	STATES = [ #Copy of the states in addons/sale/sale.py
		('draft', 'Draft Quotation'),
		('sent', 'Quotation Sent'),
		('cancel', 'Cancelled'),
		('waiting_date', 'Waiting Schedule'),
		('progress', 'Sales Order'),
		('manual', 'Sale to Invoice'),
		('invoice_except', 'Invoice Exception'),
		('done', 'Done'),
	]
	
	_name = "sale.order"
	_inherit = "sale.order"
	_columns = {
		"review_id": fields.many2one("ies.review", "Review", ondelete="cascade"),
		"dropbox": fields.char("Dropbox link", 128),
	}

