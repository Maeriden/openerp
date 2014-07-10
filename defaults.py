# -*- coding: utf-8 -*-

from openerp.osv import osv, fields

class Defaults(osv.Model):
	_name = "ies.defaults"
	_rec_name = "description"
	_columns = {
		"description": fields.char("Description", 32, readonly=True),
		"review_product_category_id": fields.many2one("product.category", "Review products category",
			domain="[('type','=','normal')]", help="'type' must be 'normal'"),
		"review_follower_ids": fields.many2many("res.partner", string="Followers"),
		"review_task_template_id": fields.many2one("email.template", "Task assignment email",
			domain="[('model_id.model','=','ies.review.service.line')]"),
		"contract_expiration_reminder_id": fields.many2one("ies.reminder.rule", "Contract expiration reminder"),
		"contract_expiration_template_id": fields.many2one("email.template", "Contract expiration email",
			domain="[('model_id.model','=','account.analytic.account')]", help="'model' must be 'account.analytic.account'"),
		"invoice_schedule_reminder_id": fields.many2one("ies.reminder.rule", "Invoice schedule reminder"),
		"invoice_schedule_template_id": fields.many2one("email.template", "Invoice schedule email",
			domain="[('model_id.model','=','ies.invoice.schedule.line')]", help="'model' must be 'ies.invoice.schedule.line'"),
		"supplier_invoice_delay_template_id": fields.many2one("email.template", "Supplier payment delay email",
			domain="[('model_id.model','=','account.invoice')]", help="'model' must be 'account.invoice'"),
		"supplier_invoice_delay_reminder_ids": fields.many2many("ies.reminder.rule", "m2m_config_delay_reminder", "config_id", "rule_id", string="Payment delay reminders"),
	}
	_defaults = {"description": "Configure default values"}
		
	def browse(self, cr, uid, ids=0, context=None):
		ids = self.search(cr, uid, [], limit=1)
		id = ids[0] if ids else 0
		return super(Defaults, self).browse(cr, uid, id, context)
		
		







