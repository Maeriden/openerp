# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class Lead(osv.Model):
	SUCCESS = [
		("low",  "Low"),
		("mid",  "Medium"),
		("high", "High"),
		("sure", "Certain"),
	]
	
	_name = "crm.lead"
	_inherit = "crm.lead"
	_columns = {
		"review_id": fields.many2one("ies.review", "Review"),
		"success_level": fields.selection(SUCCESS, "Success chance"),
		"action_ids": fields.one2many("crm.lead.action", "lead_id", "Actions"),
	}
	
	# Sets the default success probability in case any module depends on it
	def onchange_success_level(self, cr, uid, ids, level, context=None):
		vals = {"probability": 0}
		if level:
			if level == "low":
				vals["probability"] = 25
			elif level == "mid":
				vals["probability"] = 50
			elif level == "high":
				vals["probability"] = 75
			elif level == "sure":
				vals["probability"] = 100
		return {"value": vals}
		
	def schedule_phonecall(self, cr, uid, ids, time, summary, desc, phone, contact, user_id=False, section_id=False, categ_id=False, action='schedule', context=None):
		if context is None:
			context = {}
		context["show_in_lead_id"] = ids[0]
		super(Lead, self).schedule_phonecall(cr, uid, ids, time, summary, desc, phone, contact, user_id, section_id, categ_id, action, context)
		
	def action_makeMeeting(self, cr, uid, ids, context=None):
		res = super(Lead, self).action_makeMeeting(cr, uid, ids, context)
		if "context" not in res:
			res["context"] = {}
		res["context"].update({"show_in_lead_id": ids[0]})
		return res
		
	def record_action(self, cr, uid, ids, vals, context={}):
		self.write(cr, uid, ids, {"action_ids": [(0, 0, vals)]}, context)
		return True
		
	def btn_create_review(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "Lead.btn_create_review(): len(ids) != 1"
		this = self.browse(cr, uid, ids[0], context)
		if not this.partner_id:
			raise osv.except_osv("To create a review you need to set a client", "")
		vals = {
			"name": this.name,
			"opportunity_id": this.id,
			"partner_id": this.partner_id.id,
		}
		rev_id = self.pool.get("ies.review").create(cr, uid, vals, context)
		
		vals = {}
		domain = [("name", "=", "Qualification"), ("type", "in", ["opportunity", "both"])]
		stage_ids = self.pool.get("crm.case.stage").search(cr, uid, domain, context=context)
		if stage_ids and stage_ids[0]:
			vals["stage_id"] = stage_ids[0]
		
		vals["review_id"] = rev_id
		self.write(cr, uid, ids, vals, context)
		
		try:
			view = self.pool.get("ir.model.data").get_object_reference(cr, uid, "ies", "review_form")
			return {
				"type": 'ir.actions.act_window',
				"name": "Review",
				"res_model": 'ies.review',
				"res_id": rev_id,
				"view_type": "form",
				"view_mode": "form",
				"view_id": view[1],
				"target": 'current',
				"nodestroy": True,
			}
		except:
			return True



class LeadAction(osv.Model):
	TYPES = [
		("call", "Phone call"),
		("meet", "Meeting"),
		("other", "Other"),
	]
	
	_name = "crm.lead.action"
	_description = "Lead advancement action"
	_order = "date asc"
	_columns = {	
		"lead_id": fields.many2one("crm.lead", "Lead", ondelete="cascade"),
		"name": fields.char("Action", 128, required=True),
		"date": fields.datetime("Date"),
		"state": fields.selection(TYPES, "Type"),	
		"next_id": fields.many2one("crm.lead.action", "Next action", domain="[('lead_id','=',lead_id), ('id','!=',id)]"),
		"next_date": fields.related("next_id", "date", string="Next action date", type="datetime"),
		"phonecall_id": fields.many2one("crm.phonecall", "Call", ondelete="cascade"),
		"meeting_id": fields.many2one("crm.meeting", "Meeting", ondelete="cascade"),
	}
	
	_defaults = {
		"state": "other",
	}
	
	def onchange_next_action(self, cr, uid, ids, next_id, context={}):
		vals = {}
		if next_id:
			vals["next_date"] = self.browse(cr, uid, next_id, context).date
		return {"value": vals}

# Deletion through cascading doesn't call `unlink` and avoids infinite recursion
	def unlink(self, cr, uid, ids, context=None):
		for this in self.browse(cr, uid, ids, context):
			if this.phonecall_id:
				this.phonecall_id.unlink()
			if this.meeting_id:
				this.meeting_id.unlink()
		return super(LeadAction, self).unlink(cr, uid, ids, context)
##
#Display the event associated with the action, be it a call or a meeting
	def view_linked(self, cr, uid, ids, context=None):
		this = self.browse(cr, uid, ids[0], context)
		if this.state == "call":
			view = self.pool.get('ir.model.data').get_object_reference(cr, uid, "crm", "crm_case_phone_form_view")
			res_model = "crm.phonecall"
			res_id = this.phonecall_id.id
		elif this.state == "meet":
			view = self.pool.get('ir.model.data').get_object_reference(cr, uid, "base_calendar", "view_crm_meeting_form")
			res_model = "crm.meeting"
			res_id = this.meeting_id.id
		else:
			return True #Can't display view
		return {
			"type": 'ir.actions.act_window',
			"name": "Planned action",
			"res_model": res_model,
			"res_id": res_id,
			"view_type": 'form',
			"view_mode": 'form',
			"view_id": view[1] if view else 0,
			"target": 'current',
			"nodestroy": True,
		}
		


class Phonecall(osv.Model):
	_name = "crm.phonecall"
	_inherit = "crm.phonecall"
##
#Create a lead action entry if a lead_id is set
	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		id = super(Phonecall, self).create(cr, uid, vals, context)
		lid = context.get("show_in_lead_id", 0)
		if lid:
			data = {
				"state": "call",
				"phonecall_id": id,
				"name": vals["name"],
				"date": vals["date"],
			}
			self.pool.get("crm.lead").record_action(cr, uid, [lid], data, context)
			del context["show_in_lead_id"]
		return id

class Meeting(osv.Model):
	_name = "crm.meeting"
	_inherit = "crm.meeting"
##
#Create a lead action entry if a lead_id is set
	def create(self, cr, uid, vals, context=None):
		if context is None:
			context = {}
		id = super(Meeting, self).create(cr, uid, vals, context)
		lid = context.get("show_in_lead_id", 0)
		if lid:
			data = {
				"state": "meet",
				"meeting_id": id,
				"name": vals["name"],
				"date": vals["date"],
			}
			self.pool.get("crm.lead").record_action(cr, uid, [lid], data, context)
			del context["show_in_lead_id"]
		return id


class Opportunity2Call(osv.TransientModel):
	"""
Makes "schedule" the default action in the schedule/log call wizard
"""
	_name = "crm.opportunity2phonecall"
	_inherit = "crm.opportunity2phonecall"
	
	def default_get(self, cr, uid, fields, context=None):
		defaults = super(Opportunity2Call, self).default_get(cr, uid, fields, context)
		defaults["action"] = "schedule"
		return defaults
