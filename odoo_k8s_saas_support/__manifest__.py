{
    'name': 'Odoo K8s SaaS — Support Hours',
    'version': '18.0.1.0.0',
    'summary': 'Support hour tracking per subscription: helpdesk tickets, '
               'monthly allowance per instance, and add-on hour packages',
    'category': 'Technical',
    'author': 'AEI Software',
    'license': 'LGPL-3',
    'depends': [
        'odoo_k8s_saas_subscription',
        'helpdesk_mgmt',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/products.xml',
        'views/helpdesk_ticket_views.xml',
        'views/sale_subscription_views.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
