# -*- coding: utf-8 -*-
"""Entrypoint and lifecycle hooks for the payment_qr_ganadero addon."""

from . import controllers, models


def _post_init_hook(env):
    """Ensure the provider has a cryptographic JWT secret after installation."""
    provider = env.ref(
        'payment_qr_ganadero.payment_provider_qr_ganadero', raise_if_not_found=False
    )
    if provider and hasattr(provider, '_qr_ganadero_ensure_jwt_secret'):
        provider._qr_ganadero_ensure_jwt_secret()


def _uninstall_hook(env):
    """Disable and unpublish the QR Ganadero provider before module uninstall."""
    provider = env.ref(
        'payment_qr_ganadero.payment_provider_qr_ganadero', raise_if_not_found=False
    )
    if provider:
        provider.write({'state': 'disabled', 'is_published': False})

