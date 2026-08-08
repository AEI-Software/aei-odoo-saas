# AEI Assistant — tenant AI agent in Discuss

> **Estado (2026-08-08):** Phase 1 (MVP) y Phase 2 (BYOK + billing hook) construidos y verificados
> en vivo sobre el testbed. Ver [Environment Status](Environment-Status.md) para qué está
> apuntando temporalmente a `feat/cloud-portability` en vez de `main`.

Cada tenant puede activar opcionalmente un agente de IA, accesible como una conversación normal
de Discuss (estilo OdooBot), que puede leer/escribir sobre los datos del tenant **dentro de los
permisos del usuario de Odoo que le escribe** — nunca como superusuario.

## Arquitectura

```
Usuario en Discuss DM "AEI Assistant"
        │ message_post (request normal de Odoo, corre como el usuario)
        ▼
saas_ai_agent (addon del tenant)
        │ postcommit hook → POST http://agent:8000/hook   (mismo namespace,
        │                                                    NetworkPolicy propia)
        ▼
agent (pod dedicado del tenant, FastAPI + Claude Agent SDK)
        │ GET http://odoo:8069/ai_agent/llm_config   → BYOK: key propia del tenant
        │ MCP sobre HTTP: http://odoo:8069/mcp
        │   Authorization: Bearer <key de muk_mcp, un solo turno, por usuario>
        ▼
        │ POST http://odoo:8069/ai_agent/reply   (HMAC)
        ▼
saas_ai_agent postea la respuesta como el partner bot → bus.bus → Discuss en vivo
```

**Un pod de agente dedicado por tenant** (no un servicio compartido multi-tenant, no un sidecar
dentro del pod de Odoo) — decisión tomada tras investigación delegada (ver memoria de proyecto
`ai-agent-per-tenant`), porque preserva el mismo límite de aislamiento que ya usa la plataforma
(namespace + NetworkPolicy por tenant) y permite actualizar/escalar el agente sin reiniciar Odoo.

## Componentes

| Componente | Repo / paquete | Qué hace |
|:---|:---|:---|
| `agent/` | `aei-odoo-saas` (raíz, hermano de `portal/`) | Contenedor FastAPI + [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview). `tools=[]` + `allowed_tools=["mcp__odoo__*"]` lo restringe exclusivamente a las tools MCP (verificado en vivo: `allowed_tools` solo no basta — el harness expone Bash/Task/WebSearch por defecto salvo que `tools` los desactive). Guardrail `PreToolUse` (no `can_use_tool`, que queda *shadowed* por `bypassPermissions` y por wildcards en `allowed_tools`) bloquea `res.users`/`ir.module.module`/etc. antes de que la llamada MCP siquiera se envíe. |
| `saas_ai_agent/` | `aei-odoo-saas-agent` (entregado por git-clone) | Addon Odoo del lado del tenant: partner bot "AEI Assistant" (mismo patrón que `mail`/OdooBot), hook de `discuss_channel.message_post`, minteo de keys de `muk_mcp` de un solo turno por usuario, guardrails ORM de capa 1 (`res.users.create/write`, `ir.module.module.button_*`) gateados por el context key `mcp_name` que `muk_mcp` estampa en cada request MCP, settings BYOK, menú "AEI Assistant" para descubrir el chat. |
| `muk_mcp` + `muk_web_utils` | `aei-odoo-saas-agent` | Servidor MCP de terceros (MuK), ya vendorizado en `external_addons/` del monorepo — resuelve RBAC casi gratis: cada key está atada a un `res.users` específico y las tools MCP respetan ACLs/record rules normales de Odoo. |
| `AEI-Software/aei-odoo-saas-agent` | repo nuevo, público | Repo dedicado de entrega de addons para tenants que activan el add-on — **no** apuntar `addons_repos_json` al monorepo `aei-odoo-saas` directamente: el init container `clone-addons` simlinkea *cualquier* carpeta con `__manifest__.py`, así que expondría addons solo-admin como `odoo_k8s_saas`. Público a propósito (nada sensible adentro; los secretos van por K8s Secret/BYOK, nunca en código) para no necesitar un `git-credentials` Secret por tenant. |

## RBAC

`muk_mcp` autentica por `Authorization: Bearer <key>` y liga la request a `mcp_key.user_id` — cada
tool call MCP corre como ese usuario específico, con sus ACLs y record rules normales, nunca como
superusuario. Verificado en vivo: un usuario restringido (`base.group_user` únicamente) puede leer
`res.partner` vía el agente, pero un intento de `create_records` sobre `res.users` es bloqueado por
el ACL estándar de Odoo — **antes** de llegar a cualquier guardrail propio.

Cada mensaje del usuario mintea una key **nueva, de un solo turno** (`saas_ai_agent.session._issue_key`)
en vez de reusar una — `muk_mcp` solo guarda el hash SHA-256, nunca el plaintext, así que no hay
nada que reusar entre requests HTTP separadas sin inventar almacenamiento de plaintext (peor
trade-off de seguridad que rotar).

## Guardrails (requisitos: no instalar apps, no crear usuarios)

Dos capas activas (una tercera, a nivel de prompt, es UX — no seguridad):

1. **ORM, autoritativa** (`saas_ai_agent/models/guardrails.py`): overrides de
   `res.users.create/write` e `ir.module.module.button_install/button_upgrade/button_uninstall/...`
   que lanzan `UserError` **solo si** `self.env.context.get('mcp_name')` está seteado — lo que
   `muk_mcp` estampa en *cada* request MCP y ninguna otra vía (UI normal, XML-RPC, cron). Verificado
   en vivo con `create_records` sobre `res.users` vía el agente real.
2. **Dispatch, defensa en profundidad** (`agent/main.py`, hook `PreToolUse`): rechaza la tool call
   antes de enviarla, con un mensaje legible que el LLM puede repetirle al usuario.

## BYOK (Bring Your Own Key)

El tenant configura su propia API key de proveedor de IA en **Settings > AEI Assistant**
(`saas_ai_agent/models/res_config_settings.py`) — la plataforma **nunca** paga ni ve el uso de LLM.
El pod `agent` la obtiene por turno vía `GET /ai_agent/llm_config` (autenticado con
`AGENT_WEBHOOK_SECRET`) en vez de una variable de entorno estática: un cambio de key en Settings
aplica en el siguiente mensaje, sin redeploy.

Proveedores soportados (todos exponen un endpoint compatible con `/v1/messages` de Anthropic, así
que el SDK los usa vía `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` sin cambios):

| Proveedor | Endpoint |
|:---|:---|
| Anthropic | nativo (sin `base_url`) |
| DeepSeek | `https://api.deepseek.com/anthropic` |
| Moonshot / Kimi | `https://api.moonshot.ai/anthropic` |
| Custom / self-hosted (Ollama, etc.) | URL propia del tenant |

## Trial fallback + proactive welcome

New tenants don't have to configure BYOK before getting any value: the platform can supply its own
default key (currently DeepSeek), used only until the tenant sets their own, within a per-tenant
USD budget Odoo tracks itself (`aei_assistant_trial_cap_usd`, default $1, Settings > AEI Assistant
— shown only while unconfigured). The key lives **only** in each tenant's `agent-secret` K8s Secret
(`DEFAULT_LLM_*`, injected from the portal's own env — `agent_secret_manifest()`), never in any
tenant's Odoo database: `GET /ai_agent/llm_config` hands back a `trial_available` boolean and a
running spend total, nothing else, when no BYOK key is set. The agent pod reports each trial turn's
real SDK-billed cost (`ResultMessage.total_cost_usd`) back via `/ai_agent/reply`; Odoo accumulates it.

The first time a user opens the "AEI Assistant" menu, the agent introduces itself proactively
(same `/hook` path, `welcome: true`, a canned prompt instead of user text) instead of waiting for
the first message — mirrors OdooBot's own unprompted greeting.

## Billing

`odoo_k8s_saas_subscription`: producto `product_aei_assistant` + cron diario
`_cron_update_aei_assistant_line` (mismo patrón que el cron ya existente de usuarios extra,
`_cron_update_extra_user_line`) — crea/actualiza/elimina una línea de suscripción según si algún
`saas.instance` vinculado tiene `ai_agent_enabled`. Precio por plantilla:
`aei_assistant_price` (default 85 Bs/mes, ver investigación de modelo de negocio delegada a Fable 5)
o `aei_assistant_included` (gratis, ej. para diferenciar el plan Enterprise). El toggle
enable/disable en `saas.instance` (`action_enable_ai_agent`/`action_disable_ai_agent`) solo maneja
el workload K8s — la facturación la sincroniza el cron, misma división de responsabilidades que
usuarios extra.

## Cómo probarlo

Desde el admin (`staging.aeisoftware.com`, ver [Environment Status](Environment-Status.md)):

1. Abrir el `saas.instance` del tenant (estado `Ready`).
2. Botón **🤖 Enable AI Agent** en el header.
3. Dentro de la instancia del tenant: **Settings > AEI Assistant** → pegar una API key propia.
4. Menú **AEI Assistant** (grid de apps, arriba a la izquierda) → abre el DM automáticamente.

Ver [Portal API Reference](Portal-API-Reference.md#post-apiv1instancestenant_idagentenable) para
los endpoints subyacentes.

## Bugs reales encontrados solo probando en vivo

Vale la pena leerlos antes de tocar este código — ninguno era obvio desde el diseño:

- `allowed_tools` del SDK **no** restringe exclusivamente — solo auto-aprueba tools ya cargadas;
  hace falta `tools=[]` para desactivar los built-ins (Bash, Task, WebSearch...) del todo.
- `can_use_tool` queda **shadowed** silenciosamente por `permission_mode="bypassPermissions"` y por
  cualquier wildcard en `allowed_tools` — hay que usar un hook `PreToolUse` en su lugar.
- PVC mount sin `fsGroup` en el `securityContext` del pod → `PermissionError` escribiendo al
  volumen (el volumen monta como `root:root`, el proceso corre como `uid 1000` no-root).
- `ResourceQuota` de PVCs se evalúa **antes** que el chequeo de "ya existe" — reintentar un
  `enable_agent` sobre un tenant que ya tiene el PVC (a tope de cuota) tira 403, no el 409 limpio
  que `apply_manifest()` ya maneja.
- `apply_manifest()` no-opea silenciosamente sobre un Secret que ya existe — hay que leer el valor
  real después (`read_namespaced_secret()`), nunca confiar en el valor recién generado, o el
  `odoo` Deployment puede terminar con un `AGENT_WEBHOOK_SECRET` que no coincide con el real.
- `/mnt/extra-addons` es efímero — el init container `clone-addons` lo repuebla en **cada**
  reinicio del pod desde `addons_repos_json`, así que un addon copiado a mano (`kubectl cp`)
  desaparece en el próximo restart aunque la DB siga pensando que está instalado.
- `res.partner.im_search` (buscador de "nuevo mensaje directo" de Discuss) solo busca
  `res.users`, nunca `res.partner` sueltos — un partner-bot sin login real (como el de
  AEI Assistant, a propósito) nunca aparece ahí. Por eso existe el menú dedicado.
- Un PVC recién borrado sigue leyéndose como "existe" mientras Longhorn termina de desmontarlo
  (`metadata.deletion_timestamp` seteado, objeto todavía presente) — un disable seguido
  inmediatamente de un enable puede saltarse la recreación del PVC y dejar el pod del agente en
  `Pending`. Mitigado tratando un PVC con `deletion_timestamp` como ausente.
- Probar `action_open_ai_assistant_chat()` desde `odoo shell` sin `.with_user(usuario)` deja
  `self.env.user` apuntando al usuario por defecto de la shell, no al usuario que se pasó como
  argumento — crea el canal para la identidad equivocada. No es un bug real (en producción el
  `ir.actions.server` del menú siempre llama `env.user.action_open_ai_assistant_chat()`, así que
  `self` y `env.user` son el mismo registro), pero confunde el debugging si no se tiene en cuenta.
- Un `kubectl exec ... odoo shell` interrumpido a medias (por un timeout de la herramienta, por
  ejemplo) puede dejar una transacción Postgres "idle in transaction" colgada, y todo `odoo -u`
  posterior contra ese tenant falla con `SerializationFailure: could not serialize access due to
  concurrent update` — parece un bug de código pero es una conexión huérfana. Diagnóstico:
  `pg_stat_activity` filtrado por `datname`, `pg_terminate_backend(<pid>)` la que esté
  `idle in transaction`.

Más detalle operativo (comandos exactos, nombres de pods, etc.) en la memoria de proyecto
`ai-agent-per-tenant` (`/home/kali/.claude/projects/-home-kali-aeisoftware-aei-odoo-saas/memory/`).
