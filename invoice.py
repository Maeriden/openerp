# -*- coding: utf-8 -*- 

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
from datetime import datetime, timedelta
from helpers import *

class Invoice(osv.Model):
	_name = "account.invoice"
	_inherit = "account.invoice"
	_columns = {
		"contract_id": fields.many2one("account.analytic.account", "Contract"),
	}
	
	def _default_reminder_rule_ids(self, cr, uid, context=None):
		return self.pool.get("ies.defaults").browse(cr, uid).supplier_invoice_delay_reminder_ids
	
	def _default_mail_template_id(self, cr, uid, context=None):
		template = self.pool.get("ies.defaults").browse(cr, uid).supplier_invoice_delay_template_id
		return template.id if template else 0
	
	def create(self, cr, uid, vals, context=None):
		id = super(Invoice, self).create(cr, uid, vals, context)
		if vals.get("type") == "in_invoice":
			rule = self.pool.get("ies.reminder.rule")
			rule_ids = self._default_reminder_rule_ids(cr, uid, context)
			for rid in rule_ids:
				rule.set_watcher(cr, uid, rid, self._name, [id], "date_due", "_in_delay", context)
		return id
	
	def write(self, cr, uid, ids, vals, context=None):
		ret = super(Invoice, self).write(cr, uid, ids, vals, context)
		for this in self.browse(cr, uid, ids, context):
			if this.type == "in_invoice":
				rule = self.pool.get("ies.reminder.rule")
				rule_ids = self._default_reminder_rule_ids(cr, uid, context)
				for rid in rule_ids:
					rule.set_watcher(cr, uid, rid, self._name, ids, "date_due", "_in_delay", context)
		return ret
	
	def copy(self, cr, uid, id, defaults, context=None):
		new_id = super(Invoice, self).copy(cr, uid, id, defaults, context)
		this = self.browse(cr, uid, new_id, context)
		if this.type == "in_invoice":
			rule = self.pool.get("ies.reminder.rule")
			rule_ids = self._default_reminder_rule_ids(cr, uid, context)
			for rid in rule_ids:
				rule.set_watcher(cr, uid, rid, self._name, [new_id], "date_due", "_in_delay", context)
		return new_id
	
	def unlink(self, cr, uid, ids, context=None):
		rule = self.pool.get("ies.reminder.rule")
		rule.remove_watcher(cr, uid, self._name, ids, "date_due", context)
		return super(Invoice, self).unlink(cr, uid, ids, context)
		
	def _in_delay(self, cr, uid, id, field, context=None):
		tid = self._default_mail_template_id(cr, uid, context)
		if tid:
			template = self.pool.get("email.template")
			template.send_mail(cr, uid, tid, id, True, context)
	
	def confirm_paid(self, cr, uid, ids, context=None):
		ret = super(Invoice, self).confirm_paid(cr, uid, ids, context)
		try:
			self.btn_register_shares(cr, uid, ids, context)
		except: #Not found = osv.except_osv. Ignore shares and continue
			pass
		noalarm_ids = []
		for this in self.read(cr, uid, ids, ["type"], context):
			if this["type"] == "in_invoice":
				noalarm_ids.append(this["id"])
		if noalarm_ids:
			rule = self.pool.get("ies.reminder.rule")
			rule.remove_watcher(cr, uid, self._name, noalarm_ids, "date_due", context)
		return ret
	
	def btn_register_shares(self, cr, uid, ids, context=None):
		share = self.pool.get("ies.revenue.share")
		period = self.pool.get("account.period")
		now = datetime.now().strftime(DATE_FORMAT)
		period_id = period.find(cr, uid, now, context)
		if not period_id:
			raise osv.except_osv("There is no period defined for today. Create one", "")
		period_id = period_id[0]
			
		# Take out ids for which there is already a shares record
		recorded_ids = share.search(cr, uid, [("invoice_id", "in", ids)], context==context)
	#	invoice_ids = [s["invoice_id"] for s in share.read(cr, uid, recorded_ids, ["invoice_id"], context)] #gets tuple????
		recorded_invoice_ids = [s.invoice_id.id for s in share.browse(cr, uid, recorded_ids, context)]
		torecord_ids = [id for id in ids if id not in recorded_invoice_ids]
		if not torecord_ids:
			raise osv.except_osv("Shares record already exists for selected invoice(s)", "")
		
		res_ids = []
		for this in self.browse(cr, uid, torecord_ids, context):
			if not this.contract_id:
				continue
			review = this.contract_id.review_id
			if not review or not review.pnv: #Can't calculate shares without a total price
				continue
			
			name = this.origin
			if this.name:
			    name += " "+this.name
			elif this.invoice_line:
			    name += " "+this.invoice_line[0].name
			
			vals = {
				"desc": name,
				"period_id": this.period_id.id,
				"invoice_id": this.id,
				"share_line_ids": [],
			}
			if review.gm_id: #General manager's 10%
				vals["share_line_ids"].append( (0, 0, {
					"partner_id": review.gm_id.id,
					"amount": this.amount_untaxed * 0.1,
				}) )
			for task in review.service_line_ids:
				if task.partner_id: #No partner no share
					percentage = float(task.total) / review.pnv
					vals["share_line_ids"].append( (0, 0, {
						"partner_id": task.partner_id.id,
						"amount": this.amount_untaxed * percentage,
					}) )
			res_ids.append(share.create(cr, uid, vals, context))
		
		#FIXME Display tree view if more than one record is created
		if res_ids:
			view = self.pool.get("ir.model.data").get_object_reference(cr, uid, "ies", "revenue_share_form")
			return {
				"type": 'ir.actions.act_window',
				"name": "Shares",
				"res_model": 'ies.revenue.share',
				"res_id": res_ids[0],
				"view_type": 'form',
				"view_mode": 'form',
				"domain": [("id", "in", res_ids)],
				"view_id": view[1],
				"target": 'current',
				"nodestroy": True,
			}




