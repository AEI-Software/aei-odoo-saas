# -*- coding: utf-8 -*-
# Manifest for the Banco Ganadero QR Empresarial v1.17.4 payment provider.
{
    'name': 'Payment Provider: QR Banco Ganadero',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Pago por QR Empresarial v1.17.4 — Banco Ganadero (Bolivia)',
    'description': """
        Integra el servicio QR Empresarial v1.17.4 del Banco Ganadero de Bolivia
        con el e-commerce y motor de suscripciones SaaS de Odoo 18.
    """,
    'author': 'AEI Software',
    'website': 'https://aeisoftware.com',
    'depends': ['payment', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_provider_views.xml',
        'views/payment_qr_ganadero_templates.xml',
        'data/payment_provider_data.xml',
        'data/ir_cron_poll.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_qr_ganadero/static/src/js/qr_ganadero_form.js',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'uninstall_hook': '_uninstall_hook',
    'application': False,
    'installable': True,
    'license': 'LGPL-3',
}

