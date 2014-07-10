# -*- coding: utf-8 -*-

from openerp.osv import fields, osv
import httplib as http #http://docs.python.org/2/library/httplib.html
import simplejson

class Feedback(osv.Model):
	_name = "ies.feedback"
	
	INTERVIEW_MODALITY = [
		("qp", "QuestionPro"),
		("call", "Telephone call"),
		("meet", "Meeting"),
	]
	RESULT = [
		("positive", "Positive"),
		("negative", "Negative"),
	]
	
	_columns = {
		"name": fields.char("Name", 64),
		"date": fields.date("Creation date", help="Date of creation of the document"),
		"review_id": fields.many2one("ies.review", "Review"),
		"contract_id": fields.many2one("account.analytic.account", "Contract", required=True, domain="[('type','=','contract')]"),
		"partner_id": fields.related("contract_id", "partner_id", type="many2one", relation="res.partner", string="Client"),
		"date_start": fields.related("contract_id", "date_start", type="date", string="Contract start"),
		"date_end": fields.related("contract_id", "date", type="date", string="Contract end"),
		"h_projected_date": fields.date("Projected date"),
		"h_date": fields.date("Date"),
		"h_modality": fields.selection(INTERVIEW_MODALITY, "Modality"),
		"h_result": fields.selection(RESULT, "Result"),
		"h_interviewer": fields.many2one("hr.employee", "Interviewer"),
		"h_question_ids": fields.one2many("ies.feedback.question", "interview_id", "Questions"),
		"h_qp_name": fields.char("QuestionPro survey name", 64),
		"f_projected_date": fields.date("Projected date"),
		"f_date": fields.date("Date"),
		"f_modality": fields.selection(INTERVIEW_MODALITY, "Modality"),
		"f_result": fields.selection(RESULT, "Result"),
		"f_interviewer": fields.many2one("hr.employee", "Interviewer"),
		"f_question_ids": fields.one2many("ies.feedback.question", "interview_id", "Questions"),
		"f_qp_name": fields.char("QuestionPro survey name", 64),
	}
	_defaults = {
		"date": fields.date.context_today,
	}
	
	def onchange_review(self, cr, uid, ids, review_id, context=None):
		vals = {}
		if review_id:
			rev = self.pool.get("ies.review").browse(cr, uid, review_id, context)
			vals["contract_id"] = rev.contract_id.id
		return {"value": vals}
	
	def onchange_contract(self, cr, uid, ids, contract_id, context=None):
		vals = {}
		if contract_id:
			contract = self.pool.get("account.analytic.account").browse(cr, uid, contract_id, context)
			vals["partner_id"] = contract.partner_id.id
			vals["date_start"] = contract.date_start
			vals["date_end"] = contract.date
		return {"value": vals}

	def btn_fetch_response(self, cr, uid, ids, context=None):
		assert len(ids) == 1, "Feedback.btn_fetch_response(): len(ids) != 1"
		if context is None or "qp_survey_name" not in context:
			raise osv.except_osv("Survey name is not set", "")
		self.questionpro_fetch_SOAP(self, cr, uid, ids[0], context["qp_survey_name"], context)
		del context["qp_survey_name"] #In case next call passes empty name. Ensures raising exception
	
	def questionpro_fetch_SOAP(self, cr, uid, id, name, context=None):
		raise NotImplementedError
		
	def questionpro_fetch_REST(self, cr, uid, id, name, context=None):
		API_URL = "/a/api/"
		API_METHOD = "questionpro.survey.surveyResponses"
		API_KEY = "?accessKey=dsnma"
		REQ_URL = API_URL + API_METHOD + API_KEY
		
		this = self.browse(cr, uid, id, context)
		body = simplejson.dumps({
			"id": name,
			"resultMode": 0,
			"startingResponseCounter": 0,
			})
		head = {
			"Accept": "application/json",
			"Content-type": "application/json",
		}
		conn = http.HTTPConnection("api.questionpro.com")
		conn.request("POST", REQ_URL, body, head)
		resp = conn.getresponse()
		conn.close()
		body = simplejson.loads(resp.read()) #read() returns a json-formatted string
		return True



class FeedbackQuestion(osv.Model):
	CHOICES = [
		("yes", "Yes"),
		("no", "No"),
		("idk", "I don't know"),
		("part", "Partially"),
	]
	SCORE = {
		"yes": 1,
		"no": 0,
		"idk": 0,
		"part": 0.5,
	}
	
	_name = "ies.feedback.question"
	_columns = {
		"interview_id": fields.many2one("ies.feedback", "Interview", ondelete="cascade"),
		"question": fields.char("Question"),
		"answer": fields.selection(CHOICES, "Answer"),
	}
