# -*- coding: utf-8 -*-

from openerp.osv import fields, osv
from openerp.tools.misc import DEFAULT_SERVER_DATE_FORMAT as SERVER_FORMAT
from datetime import datetime, timedelta
from helpers import *

class ReminderRule(osv.Model):
	"""
This model is meant to be linked with any model that whishes to use a reminder.
After a rule reference and a date are avaiable, pass them to
ies.reminder.alarm.set_alarm() to automatically create/update a reminder
tailored for the object.
"""
	OCCURRENCES = [
		("before", "Before"),
		("after", "After"),
	]
	UNITS_OF_MEASURE = [
		("minutes", "Minutes"),
		("hours", "Hours"),
		("days", "Days"),
	]
	
	def _seconds(self, cr, uid, ids, field, arg, context=None):
		res = {}
		for this in self.browse(cr, uid, ids, context):
			delta = to_delta(this)
			res[this.id] = int(delta.total_seconds())
		return res

			
	_name = "ies.reminder.rule"
	_order = "seconds"
	_columns = {
		"name": fields.char("Name", 64, required=True),
		"occurs": fields.selection(OCCURRENCES, "Occurs", required=True),
		"uom": fields.selection(UNITS_OF_MEASURE, "Unit of measure", required=True),
		"delta": fields.integer("UoM amount", required=True),
		"seconds": fields.function(_seconds, type="integer", string="Sequence", store={
			"ies.reminder.rule": (ids_, ["occurs","uom","delta"], 10),
		}),
	}
	_defaults = {
		"occurs": "before",
		"uom": "minutes",
		"delta": 0,
	}
		
	
	# Should return a browse_record list sorted by time delta from an arbitrary point in time
	# e.g. [10hb, 10mb, now, 5ha, 3da]
	def sort(self, cr, uid, browse_list, descending=False, context=None):
		unsorted = {}
		now = datetime.now()
		for this in browse_list:
			unsorted[this.offset] = this
		
		order = sorted(unsorted.keys())
		ordered = []
		for key in order:
			ordered.append(unordered[key])
		if descending:
			ordered.reverse()
		return ordered
	
		
	def set_watcher(self, cr, uid, id, model, res_ids, field, method, context=None):
		assert isinstance(id, (int, long)), "ReminderRule.set_watcher(): list id"
		if isinstance(res_ids, (int, long)): res_ids = [res_ids]
		alarms = self.pool.get("ies.reminder.watcher")
		
		vals = {
			"rule_id": id,
			"model": model,
			"field": field,
			"method": method,
		}
		for res_id in res_ids:
			vals["res_id"] = res_id
			domain = [("model","=",model), ("res_id","=",res_id), ("field","=",field)]
			alarm_ids = alarms.search(cr, uid, domain, context=context)
			if alarm_ids:
				alarms.write(cr, uid, alarm_ids, vals, context)
			else:
				alarms.create(cr, uid, vals, context)
	
	def remove_watcher(self, cr, uid, model, res_ids, field, context=None):
		alarms = self.pool.get("ies.reminder.watcher")
		domain = [("model","=",model), ("res_id","in",res_ids), ("field","=",field)]
		alarm_ids = alarms.search(cr, uid, domain, context=context)
		if alarm_ids:
			alarms.unlink(cr, uid, alarm_ids, context)



class Watcher(osv.Model):
	_name = "ies.reminder.watcher"
	
	def _rule_watchers(model, cr, uid, ids, context=None):
		res = []
		watchers = model.pool.get("ies.reminder.watcher")
		watcher_ids = watchers.search(cr, uid, [])
		for this in watchers.browse(cr, uid, watcher_ids, context):
			if this.rule_id.id in ids:
				res.append(this.id)
		return res
	
	def _type(self, cr, uid, ids, field, arg, context=None):
		res = {}
		for this in self.browse(cr, uid, ids, context):
			res[this.id] = this.rule_id.uom
		return res
	
	_columns = {
		"rule_id": fields.many2one("ies.reminder.rule", "Reminder", required=True, ondelete="restrict"),
		"type": fields.function(_type, type="selection", string="Type", store={
			"ies.reminder.watcher": (ids_, ["rule_id"], 10),
			"ies.reminder.rule": (_rule_watchers, ["uom"], 15),
		}),
		"model": fields.char("Model", 64, required=True, help="Model of the object on which the reminder is set"),
		"res_id": fields.integer("Database ID", required=True, help="ID of the object to monitor"),
		"field": fields.char("Field", 64, help="Field used to calculate trigger time. Must be a date(time)"),
		"method": fields.char("Method to call", 64, help="Will be called when the alarm triggers"),
	}
	
	def _group_records(self, cr, uid, type, context=None):
		models = {}
		domain = [("type", "=", type)] if type else []
		ids = self.search(cr, uid, domain, context=context)
		if ids: #Necessary?
			for alarm in self.browse(cr, uid, ids, context):
				model = models.setdefault(alarm.model, {})
				model.setdefault("fields", set() ).add(alarm.field) # Uniqueness of fields
				model.setdefault("records", {}).setdefault(alarm.res_id, {})[alarm.field] = alarm
		
			for model in models.values(): # Convert to list for read()
				model["fields"] = list( model["fields"] )
		
		return models

#models - {}
#	model_1 - {}
#		fields - []
#		records - {}
#			res_1 - {}
#				field_1 - browse_record(alarm)
#				field_2 - browse_record(alarm)
#			res_2 - {}
#				field_1 - browse_record(alarm)
#				field_2 - browse_record(alarm)

	def cron_check(self, cr, uid, type=None, context=None):
		now = datetime.now()
		unlink = []
		models = self._group_records(cr, uid, type, context)
		for model, info in models.items():
			model = self.pool.get(model)
			records = info["records"]
			existing_ids = model.exists(cr, uid, records.keys())
			
			#Delete watcher if its resource was deleted but it didn't delete the watcher
			deleted_records = [id for id in records.keys() if id not in existing_ids]
			for del_id in deleted_records:
				alarms = records[del_id].values()
				unlink.extend([alarm.id for alarm in alarms])
			
			data = model.read(cr, uid, existing_ids, info["fields"], context)
			for res in data:
				id = res.pop("id")
				for field, val in res.items():
					if val: #Time must be set
						alarm = records[id][field]
						trigger = datetime.strptime(val, SERVER_FORMAT) + to_delta(alarm.rule_id)
						if now >= trigger:
							self.call_method(cr, uid, alarm, model, context)
							unlink.append(alarm.id)
		if unlink:
			self.unlink(cr, uid, unlink, context)
	
	
	def call_method(self, cr, uid, alarm, model, context=None):
		try:
			method = getattr(model, alarm.method)
			if method:
				method(cr, uid, alarm.res_id, alarm.field, context) # self passed implicitly?
		except:
			pass

	
###############################################################################
###############################################################################
#class ReminderAlarm(osv.Model):
#	"""Model that sends emails when a certain point in time is passed.
#Using set_alarm(), alarms can be created for anything that supplies a rule and
#a date/time. In theory.
#Emails are created from templates.
#"""
#	_name = "ies.reminder.alarm"
#	_columns = {
#		"name": fields.char("Name", 32, help="A model can have different alarms for the same record as long as they have different names"),
#		"rule_id": fields.many2one("ies.reminder.rule", "Reminder", required=True),
#		"model_id": fields.many2one("ir.model", "Model database ID", required=True, help="Model of the object on which the reminder is set"),
#		"res_id": fields.integer("Record database ID", required=True, help="ID of the object on which the reminder is set"),
#		"mail_template_id": fields.integer("Template database ID", help="Template ID, used to send the mail when the alarm triggers"),
#		"time": fields.datetime("Time of event", required=True, help="Time at which the alarm is triggered"),
#		"trigger": fields.datetime("Time of alarm", required=True),
#	}
#	
#	# HELPERS
#	def _calc_trigger_time(self, cr, uid, rule_id, time_string, context=None):
#		rule = self.pool.get("ies.reminder.rule").browse(cr, uid, rule_id, context)
#		time = datetime.strptime(time_string, "%Y-%m-%d")
#		if rule.uom == "minutes":
#			delta = timedelta(minutes=rule.delta)
#		elif rule.uom == "hours":
#			delta = timedelta(hours=rule.delta)
#		elif rule.uom == "days":
#			delta = timedelta(days=rule.delta)
#			
#		if rule.occurs == "before":
#			trigger = time - delta
#		else: # rule.occurs == "after"
#			trigger = time + delta
#		return datetime.strftime(trigger, "%Y-%m-%d %H:%M:%S")
#	
#	def _get_model_id(self, cr, uid, model, context=None):
#		mid = self.pool.get("ir.model").search(cr, uid, [("model","=",model)], context=context)
#		if not mid:
#			raise osv.except_osv(("ies.reminder.alarm.get_model_id()"), ("Unknown model name"))
#		return mid[0]
#	
#	def _qsearch(self, cr, uid, model, rid, context=None):
#		mid = self._get_model_id(cr, uid, model, context)
#		domain = [("model_id","=",mid), ("res_id","=",rid)]
#		alarm_ids = self.search(cr, uid, domain, context=context)
#		return alarm_ids[0] if alarm_ids else 0
#
#	def _get_mail_server_id(self, cr, uid, template, context=None):
#		if template.mail_server_id and template.mail_server_id.id:
#			return template.mail_server_id.id
#		server = self.pool.get("ir.mail_server")
#		ids = srv.search(cr, uid, [], order="priority", context=context)
#		return ids[0] if ids else 0
#
#	
#	# CREATION
#	def set_from_rule(self, cr, uid, rule_id, model, res_id, time, template_id, context=None):
#		"""
#Creates/updates the alarm for the object of model 'model' with id 'res_id'
#If 'rule_id' is False, the alarm is silently removed (if it exists)
#"""
#		assert isinstance(rule_id, (int, long)), "ies.reminder.alarm.set_from_rule(): rule_id not an integer"
#		if not rule_id or not time:
#			self.remove(cr, uid, model, res_id, context)
#			return False
#		
#		vals = {"rule_id": rule_id, "time": time}
#		id = self._qsearch(cr, uid, model, res_id, context)
#		if id:
#			vals["trigger"] = self._calc_trigger_time(cr, uid, rule_id, time, context)
#			self.write(cr, uid, [id], vals, context)
#		else:
#			vals["mail_template_id"] = template_id
#			vals["model_id"] = self._get_model_id(cr, uid, model, context)
#			vals["res_id"] = res_id
#			id = self.create(cr, uid, vals, context)
#		return id
#
#	def remove(self, cr, uid, model, res_id, context=None):
#		id = self._qsearch(cr, uid, model, res_id, context)
#		if not id:
#			return False
#		return self.unlink(cr, uid, [id], context)
#		
#	def create(self, cr, uid, vals, context=None):
#		vals["trigger"] = self._calc_trigger_time(cr, uid, vals["rule_id"], vals["time"], context)
#		return super(ReminderAlarm, self).create(cr, uid, vals, context)
#
#
#	# CRON STUFF
#	def check_alarms(self, cr, uid, context=None):
#		ids = self.search(cr, uid, [], context=context)
#		now = datetime.now()
#		delete_ids = []
#		for this in self.browse(cr, uid, ids, context):
#			# Check if the record referenced by the alarm still exists
#			if not self.pool.get(this.model_id.model).search(cr, uid, [("id","=",this.res_id)], context=context):
#				delete_ids.append(this.id)
#				continue
#			trigger = datetime.strptime(this.trigger, "%Y-%m-%d %H:%M:%S")
#			if now >= trigger:
#				if self.triggerauto(cr, uid, this, context): # Always true...
#					delete_ids.append(this.id)
#		if delete_ids:
#			self.unlink(cr, uid, delete_ids, context)
#
#	def triggerauto(self, cr, uid, alarm, context=None):
#		rid = alarm.res_id
#		template_id = alarm.mail_template_id
#		self.pool.get("email.template").send_mail(cr, uid, template_id, rid, True, context)
#		return True
#
#
#	def trigger(self, cr, uid, alarm, context=None):
#		model = alarm.model_id.model
#		rid = alarm.res_id
#		tid = alarm.mail_template_id
#		template = self.pool.get("email.template").browse(cr, uid, tid, context)
#		
#		email = self.pool.get("email.template")
#		mail_subj = email.render_template(cr, uid, template.subject, model, rid, context)
#		mail_body = email.render_template(cr, uid, template.body_html, model, rid, context)
#		mail_from = email.render_template(cr, uid, template.email_from, model, rid, context)
#		mail_to   = email.render_template(cr, uid, template.email_to, model, rid, context)
#		if not mail_to:
#			return False
#
#		msg = self.pool.get("mail.message")
#		vals = {
#			"mail_message_id": msg.create(cr, uid, {"type": "email", "subject": mail_subj}, context),
#			"mail_server_id": template.mail_server_id.id if template.mail_server_id else 0,
#			"state": "outgoing",
#			"auto_delete": template.auto_delete,
#			"email_from": mail_from,
#			"email_to": mail_to,
#			"body_html": mail_body,
#		}
#		mail = self.pool.get("mail.mail")
#		mail_id = mail.create(cr, uid, vals, context)
#		mail.send(cr, uid, [mail_id], context)
#		return True
#
#



