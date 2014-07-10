# -*- coding: utf-8 -*-

from openerp.osv import osv, fields
from datetime import datetime

class RevenueShare(osv.Model):
	_name = "ies.revenue.share"
	_columns = {
		"desc": fields.char("Description", 64, help="Invoice line description"),
		"period_id": fields.many2one("account.period", "Period"),
		"invoice_id": fields.many2one("account.invoice", "Invoice", required=True),
		"code": fields.related("invoice_id", "number", type="char", string="Number"),
		"amount": fields.related("invoice_id", "amount_untaxed", type="float", string="Invoiced amount"),
		"partner_id": fields.related("invoice_id", "partner_id", type="many2one", relation="res.partner", string="Contract client"),
		"share_line_ids": fields.one2many("ies.revenue.share.line", "share_id", string="Shares"),
	}





class RevenueShareLine(osv.Model):
	_name = "ies.revenue.share.line"
	_columns = {
		"share_id": fields.many2one("ies.revenue.share", "Share", required=True, ondelete="cascade"),
		"partner_id": fields.many2one("res.partner", "Resource"),
		"amount": fields.float("Amount"),
	}

