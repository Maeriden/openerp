# -*- coding: utf-8 -*-

from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.addons import decimal_precision as dp

from res_partner import ResPartner
from sale import SaleOrder
from helpers import ids_

#import sys
#sys.stdout = open("/home/dan/dev/openerp/ies.log", "w", 0)

#Copied from the sale.order class
def get_default_currency(model, cr, uid, context=None):
	company_id = model.pool.get('res.users').browse(cr, uid, uid, context).company_id.id
	shop_ids = model.pool.get('sale.shop').search(cr, uid, [('company_id','=',company_id)], context=context)
	if not shop_ids:
		return 0
	shop = model.pool.get('sale.shop').browse(cr, uid, shop_ids[0], context)
	if not (shop.pricelist_id and shop.pricelist_id.currency_id):
		return 0
	return shop.pricelist_id.currency_id.id


#TODO: stati opportunità:
#Nuovo		No riesame
#Qualif.	Riesame creato, definizione in corso
#Propos.	Riesame convalidato, proposta creata
#Negoz.		Nuova revisione riesame dopo rifiuto
#Vinto.		Contratto creato
#Perso.		Riesame annullato
class Review(osv.Model):
	"""
Review document for IES marketing procedure.
	"""
	_name = "ies.review"
	_inherit = ["mail.thread"]
	_description = "Review"
	#When a field changes (and a message is posted about it?),
	#the function linked to each subtype is called to determine wheter
	#the subtype applies to the message
	_track = {
		"state": {
			"ies.mt_review_state": lambda self,cr,u,obj,ctx=None: True,
		},
	}
	
	STATES = [
		("draft", "Draft"),
		("head", "Head check"),
		("manager", "Manager check"),
		("approved", "Approved"),
		("proposal", "Proposal"),
		("contract", "Contract"),
		("cancel", "Canceled"),
	]
	LMH = [
		("low",  "Low"),
		("mid",  "Medium"),
		("high", "High"),
	]
	YESNO = [
		("yes", "Yes"),
		("no", "No"),
	]
	
	def _review_from_lines(self, cr, uid, ids, context=None):
		res = {}
		for task in self.pool.get("ies.review.service.line").browse(cr, uid, ids, context):
			res[task.review_id.id] = True # Any value will do
		return res.keys()
	
	QUESTION_COUNT = 7
	
	def _risk(self, cr, uid, ids, field, args, context=None):
		fields = ["question_"+str(i+1) for i in range(self.QUESTION_COUNT)]
		res = {}
		for questions in self.read(cr, uid, ids, fields, context):
			id = questions.pop("id")
			score = sum( [float(v) for v in questions.values()] )
			res[id] = score / self.QUESTION_COUNT
		return res
	
	def _cost_revenue(self, cr, uid, ids, fields, args, context=None):
		res = {}
		for this in self.browse(cr, uid, ids, context):
			res[this.id] = vals = {"tpc": 0.0}
			for task in this.service_line_ids:
				vals["tpc"] += task.price * task.quantity
			tpc = vals["tpc"]
			vals["vadded_va"] = va  = this.pnv - tpc
			vals["vadded"]          = va / tpc if tpc else 0.0
			vals["sga_va"]    = sga = this.pnv * this.sga
			vals["fee_va"]    = fee = this.pnv * this.fee
			vals["fom_va"]    = fom = this.pnv - tpc - sga - fee
			vals["fom"]             = fom / this.pnv if this.pnv else 0.0
		return res
	
	def _total_price(self, cr, uid, ids, field, args, context=None):
		res = {}
		for this in self.browse(cr, uid, ids, context):
			res[this.id] = this.pnv + this.travel_expenses
		return res
		
	_rec_name = "name"
	_order = "date desc"
	_columns = {
		"user_id": fields.many2one("res.users", "Creator", readonly=True),
	# Dati riesame
		"state": fields.selection(STATES, "Stage", track_visibility="onchange"),
		"previous_id": fields.many2one("ies.review", "Previous revision"),
		
		"name": fields.char("Service", 128, required=True),
		"date": fields.date("Date"),
		"revision": fields.integer("Revision"),
		"opportunity_id": fields.many2one("crm.lead", "Opportunity"),#, domain="[('state','=','opportunity')]"),
		"order_id": fields.many2one("sale.order", "Proposal"),
		"contract_id": fields.many2one("account.analytic.account", "Contract"),
		
	# Dati cliente
		"partner_id": fields.many2one("res.partner", "Customer", required=True, domain="[('customer','=',True)]"),
		"address": fields.related("partner_id", "street", type="char", string="Legal address"),
		"dimension": fields.related("partner_id", "dimension", type="char", string="Dimension"),
		"reliability": fields.related("partner_id", "reliability", type="selection", selection=ResPartner.RELIABILITY, string="Reliability"),
		"op_venues": fields.related("partner_id", "operative_venues", type="char", string="Operative venues"),
		"partner_info": fields.related("partner_id", "comment", type="text", string="Other info"),
		"referent_id": fields.many2one("res.partner", "Referent", domain="[('is_company','=',False), ('parent_id','=',partner_id)]"),
		
	# Dati contratto
		"completion_time": fields.char("Completion time", 64),
		"output": fields.char("Service output", 128, help="In qualitative and quantitative terms"),
		"average_market_price": fields.char("Average market price", 128),
		"prospect_perceived_value": fields.selection(LMH, "Value perceived by the prospect"),
		"client_profitability": fields.selection(LMH, "Client profitability over time"),
		"info": fields.char("Other info", 256),
		
	# Dati economici
	# *_va fields are monetary values. Corresponding unsuffixed fields are percentages
		"service_line_ids": fields.one2many("ies.review.service.line", "review_id", "Production costs"),
		"gm_id": fields.many2one("res.partner", "General manager"),
		"fee_partner_id": fields.many2one("hr.employee", "Fee recipient"),
		"pnv": fields.float("Price excluding VAT", track_visibility="onchange"),
		"sga": fields.float("SG&A expenses %"), #Selling, General and Administrative Expenses
		"fee": fields.float("Commercial fee %"),
		"travel_expenses": fields.float("Travel expenses"),
		"notes1": fields.char("SGA notes", 64),
		"notes2": fields.char("Fee notes", 64),
		"notes3": fields.char("Margin notes", 64),
		"notes4": fields.char("Travel notes", 64),
		"notes5": fields.char("Total notes", 64),
		"currency_id": fields.many2one("res.currency"),
	
		"tpc": fields.function(_cost_revenue, type="float", string="Total production cost", track_visibility="onchange", store={
			"ies.review.service.line": (_review_from_lines, ["price", "quantity"], 10),
		}, multi="all"),
		"vadded": fields.function(_cost_revenue, type="float", string="Value added %", digits=(8, 4), store={
			"ies.review": (ids_, ["pnv"], 10),
			"ies.review.service.line": (_review_from_lines, ["price", "quantity"], 10),
		}, multi="all"),
		"vadded_va": fields.function(_cost_revenue, type="float", string="Value added", store={
			"ies.review": (ids_, ["pnv"], 10),
			"ies.review.service.line": (_review_from_lines, ["price", "quantity"], 10),
		}, multi="all"),
		"sga_va": fields.function(_cost_revenue, type="float", string="SG&A expenses", store={
			"ies.review": (ids_, ["pnv", "sga"], 5),
		}, multi="all"),
		"fee_va": fields.function(_cost_revenue, type="float", string="Commercial fee", store={
			"ies.review": (ids_, ["pnv", "fee"], 5),
		}, multi="all"),
		"fom": fields.function(_cost_revenue, type="float", string="1st operative margin %", digits=(8, 4), store={
			"ies.review": (ids_, ["pnv", "sga", "fee"], 20),
			"ies.review.service.line": (_review_from_lines, ["price", "quantity"], 20),
		}, multi="all"),
		"fom_va": fields.function(_cost_revenue, type="float", string="1st operative margin", store={
			"ies.review": (ids_, ["pnv", "sga", "fee"], 20),
			"ies.review.service.line": (_review_from_lines, ["price", "quantity"], 20),
		}, multi="all"),
		"gtp": fields.function(_total_price, type="float", string="Gross total price", track_visibility="onchange", store={
			"ies.review": (ids_, ["pnv", "travel_expenses"], 50),
		}),
			
	# Dati tecnici
		"question_1": fields.boolean("The service is based on a method"),
		"question_2": fields.boolean("The method was tested"),
		"question_3": fields.boolean("The service has already been successfully done"),
		"question_4": fields.boolean("Involved resources have adequate experience"),
		"question_5": fields.boolean("Involved resources were tested in previous services"),
		"question_6": fields.boolean("The project manager has adequate experience"),
		"question_7": fields.boolean("Completion time is compatible with resources' obligations"),
		"risk": fields.function(_risk, type="float", string="Risk", track_visibility="onchange", help="Low: >90%; Mid: 60%-90%; High: <60%"),
		"final_opinion": fields.text("Final opinion"),
		
	# Controllo qualita'
		"quality_plan_id": fields.many2one("ies.quality.plan", "Quality check plan", readonly=True),
		"quality_stage_ids": fields.related("quality_plan_id", "stage_ids", type="one2many", relation="ies.quality.plan.stage", string="Plan stages", readonly=True),
	}
	_defaults = {
		"user_id": lambda s,cr,uid,ctx=None: uid,
		"state": STATES[0][0],
		"date": fields.date.context_today,
		"revision": 1,
		"currency_id": get_default_currency,
	}
	
	def _default_product_category(self, cr, uid, context=None):
		categ = self.pool.get("ies.defaults").browse(cr, uid).review_product_category_id
		if categ:
			return categ.id
		return self.pool.get("product.product")._default_category(cr, uid, context)
	
	def default_get(self, cr, uid, fields, context=None):
		vals = super(Review, self).default_get(cr, uid, fields, context)
		if "message_follower_ids" in fields:
			followers = self.pool.get("ies.defaults").browse(cr, uid).review_follower_ids
			vals["message_follower_ids"] = [(4, partner.id) for partner in followers]
		return vals
	
	def create(self, cr, uid, vals, context=None):
		id = super(Review, self).create(cr, uid, vals, context)
		pid = self.pool.get("ies.quality.plan").create(cr, uid, {"review_id": id}, context)
		self.write(cr, uid, [id], {"quality_plan_id": pid}, context)
		return id


	def _update_opportunity(self, cr, uid, this, stage, context=None):
		if this.opportunity_id:
			vals = {
				"review_id": this.id,
				"planned_revenue": this.gtp
			}
			domain = [("name", "=", stage), ("type", "in", ["opportunity", "both"])]
			stage_ids = self.pool.get("crm.case.stage").search(cr, uid, domain, context=context)
			if stage_ids:
				vals["stage_id"] = stage_ids[0]
			
			self.pool.get("crm.lead").write(cr, uid, [this.opportunity_id.id], vals, context)
	
	def _create_product(self, cr, uid, this, context=None):
		vals = {
			"name": this.name,
			"type": "service",
			"default_code": "CAfR", #Created automatically from review
			"standard_price": this.tpc,
			"list_price": this.gtp,
			"categ_id": self._default_product_category(cr, uid, context),
		}
		product = self.pool.get("product.product")
		id = product.create(cr, uid, vals, context)
		return product.browse(cr, uid, id, context)

	def _create_proposal(self, cr, uid, this, context=None):
		product = self._create_product(cr, uid, this, context)
		partner = self.pool.get("res.partner")
		vals = {
			"review_id": this.id,
			"user_id": this.user_id.id if this.user_id else uid,
			"partner_id": this.partner_id.id,
			"partner_invoice_id": partner.address_get(cr, uid, [this.partner_id.id], ["invoice"])["invoice"],
			"partner_shipping_id": partner.address_get(cr, uid, [this.partner_id.id], ["delivery"])["delivery"],
			"pricelist_id": this.partner_id.property_product_pricelist.id if this.partner_id.property_product_pricelist else 0,
			"order_line": [(0, 0, {
				"name": this.name,
				"product_id": product.id,
				"price_unit": this.gtp,
				"type": "make_to_order",
			})],
		}
		return self.pool.get("sale.order").create(cr, uid, vals, context)

	def _send_task_mails(self, cr, uid, this, context=None):
		ids = [task.id for task in this.service_line_ids]
		self.pool.get("ies.review.service.line").send_mail(cr, uid, ids, context)


	def btn_lock(self, cr, uid, ids, context=None):
		user_groups = self.pool.get("res.users").browse(cr, uid, uid, context).groups_id
		data = self.pool.get("ir.model.data")
		manager_gid = data.get_object_reference(cr, uid, "base", "group_sale_manager")[1]
		state = "head"
		for g in user_groups:
			if g.id == manager_gid:
				state = "manager"
		self.write(cr, uid, ids, {"state": state}, context)
	
	def btn_manager_approve(self, cr, uid, ids, context=None):
		for this in self.browse(cr, uid, ids, context):
			if not this.service_line_ids:
				raise osv.except_osv("There isn't any service specification", this.name)
		self.write(cr, uid, ids, {"state": "approved"}, context)
		
	def btn_reject(self, cr, uid, ids, context=None):
		self.write(cr, uid, ids, {"state": "draft"}, context)

	def btn_create_proposal(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "ies.review.btn_create_proposal(): len(ids) != 1"
		this = self.browse(cr, uid, ids[0], context)
		assert not this.order_id, "btn_create_proposal(): order_id already exists"
		assert this.partner_id, "btn_create_proposal(): None partner_id"
		assert this.partner_id.name, "btn_create_proposal(): None partner_id.name"
		assert this.name, "btn_create_proposal(): name empty"
		
		order_id = self._create_proposal(cr, uid, this, context)
		self.write(cr, uid, ids, {"order_id": order_id, "state": "proposal"}, context)
		self._update_opportunity(cr, uid, this, "Proposition", context)
		
		view = self.pool.get('ir.model.data').get_object_reference(cr, uid, "sale", "view_order_form")
		return {
			"type": 'ir.actions.act_window',
			"name": "Proposal",
			"res_model": 'sale.order',
			"res_id": order_id,
			"view_type": 'form',
			"view_mode": 'form',
			"view_id": view[1],
			"target": 'current',
			"nodestroy": True,
		} if view else True

	# Creates contract and call sale.order confirmation function
	def btn_create_contract(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "ies.review.btn_create_contract(): len(ids) != 1"
		this = self.browse(cr, uid, ids[0], context)
		assert this.order_id, "btn_create_contract(): None order_id"
		assert this.partner_id, "btn_create_contract(): None partner_id"
		assert this.partner_id.name, "btn_create_contract(): None partner_id.name"
		assert this.name, "btn_create_contract(): name empty"
		
		vals = {
			"name": this.name,
			"type": "contract",
			"user_id": this.user_id.id if this.user_id else 0,
			"partner_id": this.partner_id.id if this.partner_id else 0,
			"review_id": this.id,
			"fix_price_invoices": True,
			"amount_max": this.gtp,
		}
		cid = self.pool.get("account.analytic.account").create(cr, uid, vals, context)
		
		sale_order = self.pool.get("sale.order")
		sale_order.write(cr, uid, [this.order_id.id], {"project_id": cid}, context)
		sale_order.action_button_confirm(cr, uid, [this.order_id.id], context)
		
		self.write(cr, uid, ids, {"contract_id": cid, "state": "contract"}, context)
		self._update_opportunity(cr, uid, this, "Won", context)
		
		try:
			view = self.pool.get('ir.model.data').get_object_reference(cr, uid, "ies", "contract_form")
			return {
				"type": 'ir.actions.act_window',
				"name": "Contract",
				"res_model": 'account.analytic.account',
				"res_id": cid,
				"view_mode": 'form',
				"view_id": view[1],
				"target": 'current',
				"nodestroy": True,
			}
		except:
		   	return True
	
	def btn_tasks_email(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "ies.review.btn_send_assignment_mails(): len(ids) != 1"
		this = self.browse(cr, uid, ids[0], context)
		self._send_task_mails(cr, uid, this, context)

	# Invalidates review and proposal
	def btn_cancel_review(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "ies.review.btn_cancel_revision(): len(ids) != 1"
		this = self.browse(cr, uid, ids[0], context)
		
		if this.order_id:
			self.pool.get("sale.order").action_cancel(cr, uid, [this.order_id.id], context)
		
		self._update_opportunity(cr, uid, this, "Lost", context)
		
		return self.write(cr, uid, ids, {"state": "cancel"}, context)
		
	# Copies the review, increments revision number and invalidates this review
	def btn_new_revision(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "ies.review.btn_new_revision(): len(ids) != 1"
		this = self.browse(cr, uid, ids[0], context)
		oppor_id = this.opportunity_id.id if this.opportunity_id else 0
		defaults = {
			"revision": this.revision + 1,
			"opportunity_id": oppor_id,
			"order_id": 0,
			"contract_id": 0,
		}
		new_id = self.copy(cr, uid, this.id, defaults, context)
		self.write(cr, uid, ids, {"previous_id": new_id}, context)
		that = self.browse(cr, uid, new_id, context)
		self._update_opportunity(cr, uid, that, "Negotiation", context)
		
		try:
			view = self.pool.get('ir.model.data').get_object_reference(cr, uid, "ies", "review_form")
			return {
				"type": 'ir.actions.act_window',
				"name": "Contract",
				"res_model": 'ies.review',
				"res_id": new_id,
				"view_type": "form",
				"view_mode": "form",
				"view_id": view[1],
				"target": 'current',
				"nodestroy": True,
			}
		except:
			return True

##
#\brief Fills fields with partner data (resets referent)
	def onchange_partner(self, cr, uid, ids, partner_id, context=None):
		vals = {}
		if partner_id:
			partner = self.pool.get("res.partner").browse(cr, uid, partner_id, context)
			vals["address"] = partner.street
			vals["dimension"] = partner.dimension
			vals["op_venues"] = partner.operative_venue_ids
			vals["reliability"] = partner.reliability
			vals["partner_info"] = partner.comment
		else:
			vals["address"] = ""
			vals["dimension"] = ""
			vals["op_venues"] = ""
			vals["reliability"] = ""
			vals["partner_info"] = ""
		vals["referent_id"] = 0
		return {"value": vals}


#Calculates the total price of the lines
#0: create with dic field:val and link
#1: update with dic field:val and link
#2: unlink() (delete)
#3: remove (erase link)
#4: (re)link to unmodified id
#5: unlink() all
#6: 5+4 (6, 0, [IDs])


################################################################################
################################################################################
class Service(osv.Model):
	_name = "ies.review.service.line"
	
	def _total(self, cr, uid, ids, name, args, context=None):
		res = {}
		for this in self.browse(cr, uid, ids, context):
			res[this.id] = this.price * this.quantity
		return res
	
	_columns = {
		"review_id": fields.many2one("ies.review", "Review", ondelete="cascade"),
		"name": fields.char("Name", 32),
		"role": fields.char("Role", 32),
		"partner_id": fields.many2one("res.partner", "Resource", domain="[('customer', '=', False)]"),
		"output": fields.char("Output", 64),
		"price": fields.float("Cost", digits=(16, 2)),
		"uom_id": fields.many2one("product.uom", "Unit of measure"),
		"quantity": fields.integer("Quantity"),
		"total": fields.function(_total, type="float", string="Total cost", digits=(16, 2), store={
			"ies.review.service.line": (ids_, ["price", "quantity"], 10)
		}),
		"notes": fields.char("Notes", 128),
		"notified": fields.boolean("Resource notified by email"),
	}
	
	_defaults = {
		"uom_id": lambda s,cr,u,ctx=None: s.pool.get("sale.order.line")._get_uom_id(cr, u, ctx),
		"quantity": 1,
	}
	
	def _default_mail_template_id(self, cr, uid, context=None):
		template = self.pool.get("ies.defaults").browse(cr, uid).review_task_template_id
		return template.id if template else 0
	
	def send_mail(self, cr, uid, ids, context=None):
		tid = self._default_mail_template_id(cr, uid, context)
		if not tid:
			raise osv.except_osv("Email notification impossible", "Email template is not set")
		template = self.pool.get("email.template")
		for this in self.browse(cr, uid, ids, context):
			if not this.notified:
				template.send_mail(cr, uid, tid, this.id, True, context)
		self.write(cr, uid, ids, {"notified": True}, context)
		
	def onchange_price(self, cr, uid, ids, price, qty, context=None):
		return {"value": {"total": price*qty}}



################################################################################
################################################################################
class QualityCheckPlan(osv.Model):
	_name = "ies.quality.plan"
	_description = "Quality check plan"
	_columns = {
		"review_id": fields.many2one("ies.review", "Review", ondelete="cascade"),
		"name": fields.char("Name", 16, readonly=True, help="For m2o label display only"),
		"date": fields.date("Creation date"),
		"date_start": fields.date("Starting date"),
		"date_end": fields.date("Ending date"),
		"prepared_id": fields.many2one("res.users", "Prepared by"),
		"approved_id": fields.many2one("res.users", "Approved by"),
		"stage_ids": fields.one2many("ies.quality.plan.stage", "plan_id", "Stages"),
	}
	_defaults = {
		"name": "Related plan",
		"date": fields.date.context_today,
		"prepared_id": lambda self, cr, uid, ctx=None: uid,
	}

class QualityPlanStage(osv.Model):
	RESULT = [
		("good", "Passed"),
		("half", "Barely passed"),
		("fail", "Not passed"),
	]
	_name = "ies.quality.plan.stage"
	_description = "A step in a quality check plan"
	_order = "date asc"
	_columns = {
		"plan_id": fields.many2one("ies.quality.plan", ondelete="cascade"),
		"name": fields.char("Stage", 128, required=True),
		"date": fields.date("Date"),
		"consultant_id": fields.many2one("hr.employee", "Consultant"),
		"responsible_id": fields.many2one("hr.employee", "Responsible"),
		"modality": fields.char("Modality", 256),
		"report": fields.text("Report"),
		"result": fields.selection(RESULT, "Result"),
		"notes": fields.char("Notes", 128),
		"next_id": fields.many2one("ies.quality.plan.stage", "Next", domain="[('plan_id','=',plan_id)]"),
		"notes": fields.char("Notes", size=256),
	}


