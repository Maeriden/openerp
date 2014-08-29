# -*- coding: utf-8 -*-
{
    'name': 'IES Marketing Management',
    'version': '20140211',
    'category': 'Sales Management',
    'sequence': 100, # settare > 100. Traduzioni lette in sequenza.
    'summary': 'IES Consulting marketing customization',
    'description': """
Customizzazione marketing per IES Consulting
===========================================================================

* Aggiunge uno storico di azioni programmate alle Opportunità
* Aggiunge il menu Riesami, con campi in Opportunità, Ordini di vendita e Contratti
* Modifica la percentuale di successo delle opportunità in un campo di selezione (basso-medio-alto)
* Aggiunge un campo di affidabilità cliente (scarsa-media-alta)
""",
    'author': 'Daniele Bondì @ Eikony',
    'website': 'http://www.eikony.com',
    'depends': [
    	"base",
    	"base_calendar",
    	"web",
    	"mail",
    	"email_template",
    	"crm",
    	"sale",
    	"sale_crm",
    	"product",
    	"account",
    	"account_followup",
    	"analytic",
    	"account_analytic_analysis",
    	"hr",
    ],
    
    "data": [
		#Security
		"security/res.groups.xml",
		"security/ir.rule.xml",
		"security/ir.ui.menu.xml",
		"security/ir.model.access.csv",
		"security/ir.model.access.xml",
		
		#Data
		"data/ir.cron_data.xml",
		"data/res.users_data.xml",
		"data/res.country.state_data.xml",
		"data/res.alarm_data.xml",
		"data/mail.template_data.xml",
		"data/mail.subtype_data.xml",
		"data/product.category_data.xml",
		
		"data/reminder_data.xml",
		"data/defaults_data.xml",

		#Modifications
		"res.partner_view.xml",
		"crm.lead_view.xml",
		"sale_view.xml",
		"analytic_view.xml",
		
		"review_view.xml",
		"interview_view.xml",
		"invoice_view.xml",
		"defaults_view.xml",
		"revenue.shares_view.xml",
		"reminder_view.xml",
		
	#	"workflow/review_workflow.xml", #Incomplete
    ],
    
    "js": [
        "static/src/js/percentage.js",
    ],
    "qweb": [
    	"static/src/xml/percentage.xml",
    ],
    "css": [
    	"static/src/css/percentage.css",
    	"static/src/css/table.css",
    ],
    
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
}
