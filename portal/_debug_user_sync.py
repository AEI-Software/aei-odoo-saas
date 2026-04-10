"""Debug script: investigate user_count sync issue."""
import psycopg2
import os

host = os.getenv("POSTGRES_HOST", "postgres.aeisoftware.svc.cluster.local")
port = os.getenv("POSTGRES_PORT", "5002")
user = os.getenv("POSTGRES_ADMIN_USER", "postgres")
pwd  = os.getenv("POSTGRES_ADMIN_PASSWORD", "")

conn = psycopg2.connect(host=host, port=port, dbname="admin", user=user, password=pwd)
cur = conn.cursor()

# 1) saas_instance records
cur.execute("""
    SELECT id, tenant_id, state, user_count, subscription_id
    FROM saas_instance
    WHERE state NOT IN ('deleted')
    ORDER BY id
""")
rows = cur.fetchall()
print("=== saas_instance (non-deleted) ===")
for r in rows:
    print(f"  id={r[0]} tenant={r[1]} state={r[2]} users={r[3]} sub={r[4]}")

# 2) Cron status - look for SaaS crons
cur.execute("""
    SELECT id, ir_actions_server_id, active, interval_number, interval_type, lastcall, nextcall
    FROM ir_cron
    ORDER BY id
""")
crons = cur.fetchall()

# Get server action names
cur.execute("""
    SELECT c.id, s.name, c.active, c.interval_number, c.interval_type, c.lastcall, c.nextcall
    FROM ir_cron c
    JOIN ir_act_server s ON s.id = c.ir_actions_server_id
    WHERE s.name LIKE '%SaaS%' OR s.name LIKE '%User%' OR s.name LIKE '%Subscription%'
    ORDER BY c.id
""")
saas_crons = cur.fetchall()
print("\n=== SaaS-related cron jobs ===")
for c in saas_crons:
    print(f"  id={c[0]} name={c[1]} active={c[2]} every={c[3]} {c[4]} last={c[5]} next={c[6]}")

# 3) Check PORTAL_URL env var that the cron uses
print(f"\n=== Environment ===")
print(f"  POSTGRES_HOST={host}")
print(f"  POSTGRES_PORT={port}")
print(f"  POSTGRES_USER={user}")

# 4) Check portal URL config from admin DB
cur.execute("""
    SELECT key, value FROM ir_config_parameter
    WHERE key LIKE '%portal%' OR key LIKE '%saas%'
""")
params = cur.fetchall()
print("\n=== ir.config.parameter (portal/saas) ===")
for p in params:
    print(f"  {p[0]} = {p[1]}")

conn.close()
print("\nDone.")
