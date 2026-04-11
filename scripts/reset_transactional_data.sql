-- ============================================================
-- ODOO SAAS MVP — RESET DE DATOS TRANSACCIONALES v3
-- Conserva: usuarios, empresa, productos, proveedores de pago,
--            plan de cuentas, secuencias, journals, configuración.
-- Elimina:   pedidos, facturas, pagos, suscripciones, instancias K8s.
-- ============================================================
-- MODO DE USO (staging):
--   kubectl -n staging run db-reset --rm -i --restart=Never \
--     --image=postgres:16-alpine --env="PGPASSWORD=<pw>" -- \
--     psql -h postgres.aeisoftware.svc.cluster.local -p 5000 \
--     -U odoo -d staging < scripts/reset_transactional_data.sql
--
-- NOTA: No requiere superusuario. El orden de DELETE respeta FK.
-- ============================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1. MÓDULOS SAAS CUSTOM (sin CASCADE — tabla hoja)
-- ─────────────────────────────────────────────────────────────
DELETE FROM saas_instance;
ALTER SEQUENCE saas_instance_id_seq RESTART WITH 1;

-- ─────────────────────────────────────────────────────────────
-- 2. SUSCRIPCIONES
-- ─────────────────────────────────────────────────────────────
DELETE FROM sale_subscription_line;
DELETE FROM sale_subscription;
ALTER SEQUENCE sale_subscription_line_id_seq RESTART WITH 1;
ALTER SEQUENCE sale_subscription_id_seq RESTART WITH 1;

-- ─────────────────────────────────────────────────────────────
-- 3. PAGOS Y TRANSACCIONES
-- ─────────────────────────────────────────────────────────────
DELETE FROM account_payment;
DELETE FROM payment_transaction;
ALTER SEQUENCE account_payment_id_seq RESTART WITH 1;
ALTER SEQUENCE payment_transaction_id_seq RESTART WITH 1;

-- ─────────────────────────────────────────────────────────────
-- 4. CONTABILIDAD: RECONCILIACIONES → LÍNEAS → ASIENTOS
-- ─────────────────────────────────────────────────────────────
DELETE FROM account_partial_reconcile;
DELETE FROM account_full_reconcile;
DELETE FROM account_move_line;
DELETE FROM account_move;
DELETE FROM account_bank_statement_line;
DELETE FROM account_bank_statement;
ALTER SEQUENCE account_partial_reconcile_id_seq RESTART WITH 1;
ALTER SEQUENCE account_full_reconcile_id_seq RESTART WITH 1;
ALTER SEQUENCE account_move_line_id_seq RESTART WITH 1;
ALTER SEQUENCE account_move_id_seq RESTART WITH 1;
ALTER SEQUENCE account_bank_statement_id_seq RESTART WITH 1;
ALTER SEQUENCE account_bank_statement_line_id_seq RESTART WITH 1;

-- ─────────────────────────────────────────────────────────────
-- 5. VENTAS
-- ─────────────────────────────────────────────────────────────
DELETE FROM sale_order_line;
DELETE FROM sale_order;
ALTER SEQUENCE sale_order_line_id_seq RESTART WITH 1;
ALTER SEQUENCE sale_order_id_seq RESTART WITH 1;

-- ─────────────────────────────────────────────────────────────
-- 6. MENSAJERÍA: solo mensajes de los modelos transaccionales
--    (NO usamos CASCADE para no tocar config de mail_template)
-- ─────────────────────────────────────────────────────────────
DELETE FROM mail_notification
WHERE mail_message_id IN (
    SELECT id FROM mail_message
    WHERE model IN (
        'sale.order', 'sale.subscription', 'account.move',
        'account.payment', 'payment.transaction', 'saas.instance'
    )
);

DELETE FROM mail_message_res_partner_rel
WHERE mail_message_id IN (
    SELECT id FROM mail_message
    WHERE model IN (
        'sale.order', 'sale.subscription', 'account.move',
        'account.payment', 'payment.transaction', 'saas.instance'
    )
);

DELETE FROM mail_message
WHERE model IN (
    'sale.order', 'sale.subscription', 'account.move',
    'account.payment', 'payment.transaction', 'saas.instance'
);

DELETE FROM mail_followers
WHERE res_model IN (
    'sale.order', 'sale.subscription', 'account.move',
    'account.payment', 'payment.transaction', 'saas.instance'
);

DELETE FROM mail_activity
WHERE res_model IN (
    'sale.order', 'sale.subscription', 'account.move',
    'account.payment', 'payment.transaction', 'saas.instance'
);

-- ─────────────────────────────────────────────────────────────
-- 7. RESETEAR SECUENCIAS DE ODOO (numeración de documentos)
-- ─────────────────────────────────────────────────────────────
UPDATE ir_sequence SET number_next = 1
WHERE code IN (
    'sale.order',
    'account.payment.customer.invoice',
    'account.payment.customer.receipt',
    'account.payment.supplier.invoice',
    'account.payment.supplier.receipt',
    'sale.subscription',
    'saas.tenant.id'
);

COMMIT;

-- ─────────────────────────────────────────────────────────────
-- VERIFICACIÓN POST-RESET
-- ─────────────────────────────────────────────────────────────
SELECT 'saas_instance'      AS tabla, COUNT(*) AS registros FROM saas_instance
UNION ALL
SELECT 'sale_subscription',           COUNT(*) FROM sale_subscription
UNION ALL
SELECT 'payment_transaction',         COUNT(*) FROM payment_transaction
UNION ALL
SELECT 'account_move',                COUNT(*) FROM account_move
UNION ALL
SELECT 'account_payment',             COUNT(*) FROM account_payment
UNION ALL
SELECT 'sale_order',                  COUNT(*) FROM sale_order
ORDER BY tabla;
