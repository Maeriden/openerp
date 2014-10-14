# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class Contract(osv.Model):
    _name = "account.analytic.account"
    _inherit = "account.analytic.account"
    _columns = {
        "date_create": fields.date("Creation date"),
        "review_id": fields.many2one("ies.review", "Review"),
        "schedule_line_ids": fields.one2many("ies.invoice.schedule.line", "contract_id", string="Invoicing plan"),
        "dropbox_link": fields.char("Dropbox link", 256, help="Dropbox URL of a publicly accessible document"),
    }

    _defaults = {
        "date_create": fields.date.context_today,
    }

    def _default_reminder_rule_id(self, cr, uid, context=None):
        rem = self.pool.get("ies.defaults").browse(cr, uid).contract_expiration_reminder_id
        return rem.id if rem else 0

    def _default_mail_template_id(self, cr, uid, context=None):
        template = self.pool.get("ies.defaults").browse(cr, uid).contract_expiration_template_id
        return template.id if template else 0

    def default_get(self, cr, uid, fields, context=None):
        defaults = super(Contract, self).default_get(cr, uid, fields, context)
        if "reminder_id" in fields:
            defaults["reminder_id"] = self._default_reminder_rule_id(cr, uid)
        return defaults

    def create(self, cr, uid, vals, context=None):
        id = super(Contract, self).create(cr, uid, vals, context)
        rule_id = self._default_reminder_rule_id(cr, uid, context)
        if rule_id:
            rule = self.pool.get("ies.reminder.rule")
            rule.set_watcher(cr, uid, rule_id, self._name, [id], "date", "alarm_expiration", context)
        return id

    def write(self, cr, uid, ids, vals, context=None):
        ret = super(Contract, self).write(cr, uid, ids, vals, context)
        rule = self.pool.get("ies.reminder.rule")
        rule_id = self._default_reminder_rule_id(cr, uid, context)
        if rule_id:
            rule.set_watcher(cr, uid, rule_id, self._name, ids, "date", "alarm_expiration", context)
        else:
            rule.remove_watcher(cr, uid, self._name, ids, "date", context)
        return ret

    def copy(self, cr, uid, id, defaults, context=None):
        new_id = super(Contract, self).copy(cr, uid, id, defaults, context)

        rule = self.pool.get("ies.reminder.rule")
        rule_id = self._default_reminder_rule_id(cr, uid, context)
        if rule_id: #create() called?
            rule.set_watcher(cr, uid, rule_id, self._name, [new_id], "date", "alarm_expiration", context)
        else:
            rule.remove_watcher(cr, uid, self._name, ids, "date", context)

        return new_id

    def unlink(self, cr, uid, ids, context=None):
        rule = self.pool.get("ies.reminder.rule")
        rule.remove_watcher(cr, uid, self._name, ids, "date", context)
        return super(Contract, self).unlink(cr, uid, ids, context)

    def btn_copy_renew(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "ies.Contract.btn_copy_renew(): len(ids) != 1"
        this = self.browse(cr, uid, ids[0], context)
        defaults = {
            "name": this.name + " (renewed)", #Doesn't work
            "code": this.code, #Doesn't work
            "date_start": this.date,
            "date": None,
            "date_create": fields.date.context_today(self, cr, uid, context),
            "schedule_line_ids": [],
        }
        new_id = self.copy(cr, uid, ids[0], defaults, context)
        sale_order = self.pool.get("sale.order")
        so_ids = sale_order.search(cr, uid, [("project_id", "=", ids[0])], context=context)
        for so_id in so_ids:
            sale_order.copy(cr, uid, so_id, {"project_id": new_id}, context)

        view = self.pool.get("ir.model.data").get_object_reference(cr, uid, "ies", "contract_form")
        return {
            "type": 'ir.actions.act_window',
            "name": "Contract",
            "res_model": 'account.analytic.account',
            "view_mode": 'form',
            "res_id": new_id,
            "view_id": view[1],
            "target": 'current',
            "nodestroy": True,
        }

    #FIXME: error opening form view for create
    def btn_open_invoices(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "ies.Contract.btn_open_invoices(): len(ids) != 1"
        this = self.browse(cr, uid, ids[0], context)
        model_data = self.pool.get("ir.model.data")

        try:
            tree_id = model_data.get_object_reference(cr, uid, "account", "invoice_tree")[1]
            form_id = model_data.get_object_reference(cr, uid, "account", "invoice_form")[1]
            return {
                "name": "Invoices",
                "type": 'ir.actions.act_window',
                "view_type": 'form',
                "view_mode": 'tree,form',
                "res_model": 'account.invoice',
                "domain": [
                    ("type", "=", "out_invoice"), "|",
                    ("contract_id", "=", this.id), ("origin", "=", this.code),
                ],
                'context': dict(context,
                    default_contract_id=this.id,
                    default_origin=this.code,
                    default_partner_id=this.partner_id.id,
                    default_type="out_invoice",
                    type="out_invoice",
                    journal_type="sale"
                ),
                'views': [(tree_id, 'tree'), (form_id, 'form')],
            }
        except:
            pass

    def alarm_expiration(self, cr, uid, id, field, context=None):
        tid = self._default_mail_template_id(cr, uid, context)
        if tid:
            template = self.pool.get("email.template")
            template.send_mail(cr, uid, tid, id, True, context)



class InvoicingScheduleLine(osv.Model):
    INVOICE_STATES = [
        ('draft','Draft'),
        ('proforma','Pro-forma'),
        ('proforma2','Pro-forma'),
        ('open','Open'),
        ('paid','Paid'),
        ('cancel','Cancelled'),
    ]

    _name = "ies.invoice.schedule.line"
    _order = "date asc"
    _columns = {
        "contract_id": fields.many2one("account.analytic.account", "Contract", ondelete="cascade"),
        "invoice_id": fields.many2one("account.invoice", "Invoice"),
        "name": fields.char("Phase", 64, required=True),
        "date": fields.date("Projected date", required=True),
        "state": fields.related("invoice_id", "state", type="selection", selection=INVOICE_STATES, string="State", store=True),
        "date_emission": fields.related("invoice_id", "date_invoice", type="date", string="Emission date"),
        "amount": fields.float("Amount", digits=(16, 2)),
        "notes": fields.char("Notes", 128),
    }

    def _default_reminder_rule_id(self, cr, uid, context=None):
        rem = self.pool.get("ies.defaults").browse(cr, uid).invoice_schedule_reminder_id
        return rem.id if rem else 0

    def _default_mail_template_id(self, cr, uid, context=None):
        template = self.pool.get("ies.defaults").browse(cr, uid).invoice_schedule_template_id
        if template:
            return template.id
        try:
            model_data = self.pool.get("ir.model.data")
            return model_data.get_object_reference(cr, uid, "ies", "template_invoice_schedule_reminder")[1]
        except:
            return 0

    def create(self, cr, uid, vals, context=None):
        id = super(InvoicingScheduleLine, self).create(cr, uid, vals, context)
        rule_id = self._default_reminder_rule_id(cr, uid, context)
        if rule_id:
            rule = self.pool.get("ies.reminder.rule")
            rule.set_watcher(cr, uid, rule_id, self._name, [id], "date", "alarm_emission", context)
        return id

    def write(self, cr, uid, ids, vals, context=None):
        ret = super(InvoicingScheduleLine, self).write(cr, uid, ids, vals, context)
        rule = self.pool.get("ies.reminder.rule")
        rule_id = self._default_reminder_rule_id(cr, uid, context)
        if rule_id:
            rule.set_watcher(cr, uid, rule_id, self._name, ids, "date", "alarm_emission", context)
        else:
            rule.remove_watcher(cr, uid, self._name, ids, "date", context)
        return ret

# Deletion through a cascade delete doesn't call "unlink"
    def unlink(self, cr, uid, ids, context=None):
        lines = self.browse(cr, uid, ids, context)
        for this in lines:
            if this.invoice_id and this.invoice_id.state not in ["draft", "cancel"]:
                raise osv.except_osv("You can't cancel a schedule line if its invoice was already confirmed", "")
        rule = self.pool.get("ies.reminder.rule")
        rule.remove_watcher(cr, uid, self._name, ids, "date", context)
        return super(InvoicingScheduleLine, self).unlink(cr, uid, ids, context)

    def alarm_emission(self, cr, uid, id, field, context=None):
        tid = self._default_mail_template_id(cr, uid, context)
        if tid:
            self.pool.get("email.template").send_mail(cr, uid, tid, id, True, context)


    def btn_create_invoice(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "ies.InvoicingScheduleLine.btn_create_invoice(): len(ids) != 1"
        this = self.browse(cr, uid, ids[0], context)
        sale_order = self.pool.get("sale.order")

        assert this.contract_id, "ies.InvoicingScheduleLine.btn_create_invoice(): missing contract"
        if not this.contract_id.partner_id:
            raise osv.except_osv("Invoicing plan needs the contract partner to be set", "")

        so_ids = sale_order.search(cr, uid, [("project_id", "=", this.contract_id.id)], context=context)
        if not so_id:
            raise osv.except_osv("Invoicing plan needs a sale order linked to the contract", "")

        if context is None:
            context = {}

        client = this.contract_id.partner_id
        inv_vals = {
            "name": this.name,
            "type": "out_invoice",
            "partner_id": client.id,
            "account_id": client.property_account_receivable.id if client.property_account_receivable else 0,
            "contract_id": this.contract_id.id,
            "origin": this.contract_id.code,
            "invoice_line": [],
        }


        for line in sale_order.browse(cr, uid, so_ids[0], context).order_line:
            prod = line.product_id
            inv_vals["invoice_line"].append( (0, 0, {
                "product_id": prod.id,
                "name": this.name,
                "account_analytic_id": this.contract_id.id,
                "account_id": prod.categ_id.property_account_income_categ.id if prod.categ_id and prod.categ_id.property_account_income_categ else 0,
                "quantity": 1,
                "price_unit": this.amount,
                "invoice_line_tax_id": [(4, tax.id) for tax in prod.taxes_id],
            }))

        inv_ctx = dict(context, type="out_invoice")
        inv_id = self.pool.get("account.invoice").create(cr, uid, inv_vals, inv_ctx)
    #   invoice.button_reset_taxes(cr, uid, [inv_id], inv_ctx) #Copied from SO invoicing wizard

        sale_order.write(cr, uid, so_ids, {"invoice_ids": [(4, inv_id)]}, context)

        self.write(cr, uid, ids, {"invoice_id": inv_id}, context)

        try:
            view = self.pool.get("ir.model.data").get_object_reference(cr, uid, "account", "invoice_form")
            return {
                "type": 'ir.actions.act_window',
                "name": "Invoice",
                "res_model": 'account.invoice',
                "view_mode": 'form',
                "res_id": inv_id,
                "view_id": view[1],
                "context": inv_ctx,
                "target": 'current',
                "nodestroy": True,
            }
        except:
            return True

    def btn_view_invoice(self, cr, uid, ids, context=None):
        assert len(ids) == 1, "ies.InvoicingScheduleLine.btn_view_invoice(): len(ids) != 1"
        try:
            view = self.pool.get("ir.model.data").get_object_reference(cr, uid, "account", "invoice_form")
            return {
                "type": 'ir.actions.act_window',
                "name": "Invoice",
                "res_model": 'account.invoice',
                "res_id": self.browse(cr, uid, ids[0], context).invoice_id.id,
                "view_type": 'form',
                "view_mode": 'form',
                "view_id": view[1],
                "context": dict(context, type="out_invoice"),
                "target": 'current',
                "nodestroy": True,
            }
        except:
            raise osv.except_osv("Can't display invoice from here", "Error retrieving the form view")

