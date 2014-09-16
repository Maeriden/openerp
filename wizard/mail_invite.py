# -*- coding: utf-8 -*-

from openerp.osv import osv
from openerp.osv import fields
from openerp import tools
from openerp.tools.translate import _

class InviteNotify(osv.osv_memory):
	"""
Sends a notification to partners invited to follow documents
"""
	_name    = "mail.wizard.invite"
	_inherit = "mail.wizard.invite"
	_columns  = {"notify": fields.boolean("Notify partners")}
	_defaults = {"notify": True}
	
	def add_followers(self, cr, uid, ids, context=None):
		"""
Sends a message to the wall of invited partners.
SHOULD BE THE DEFAULT BEHAVIOR IN 8.0!
"""
		Mail = self.pool.get('mail.mail')
		User = self.pool.get("res.users")
		for this in self.browse(cr, uid, ids, context=context):
			res_model = self.pool.get(this.res_model)
			document = res_model.browse(cr, uid, this.res_id, context=context)

			# filter partner_ids to get the new followers, to avoid sending email to already following partners
			follower_ids = [partner.id for partner in this.partner_ids if partner.id not in document.message_follower_ids]
			res_model.message_subscribe(cr, uid, [this.res_id], follower_ids, context=context)

			# send an email only if a personal message exists
		#	if this.message and this.message != '<br>':  # when deleting the message, cleditor keeps a <br>
			# add signature
			signature = User.read(cr, uid, uid, fields=["signature"], context=context)["signature"]
			if signature:
			    this.message = tools.append_content_to_html(this.message, signature, plaintext=True, container_tag='div')
			# FIXME 8.0: use notification_email_send, send a wall message and let mail handle email notification + message box
			for follower_id in follower_ids:
				# the invite wizard should create a private message not related to any object -> no model, no res_id
				vals = {
					'model': this.res_model,
					'res_id': this.res_id,
					'subject': _('Invitation to follow %s') % document.name_get()[0][1],
					'body_html': '%s' % this.message,
					'auto_delete': True,
				#	"partner_ids": [(4, follower_id)], #Causes the message to appear in the "To: me" page
				}
				if this.notify:
					#THIS. THIS IS ALL THAT TAKES TO CREATE A NOTIFICATION
					vals["notified_partner_ids"] = [(4, follower_id)]
				mail_id = Mail.create(cr, uid, vals, context=context)
				Mail.send(cr, uid, [mail_id], recipient_ids=[follower_id], context=context)
				
		return {'type': 'ir.actions.act_window_close'}

