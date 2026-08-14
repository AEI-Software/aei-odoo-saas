# SBA PILOTO in-cluster (hito 14)

Facturador SIAT (AEI-Software/SBA) desplegado en el namespace `sba-piloto` de cotas-staging,
alcanzable SOLO desde los namespaces de tenants (`managed-by=saas-portal`) y desde `staging`.

- Imagen: `ghcr.io/aei-software/sba:<sha>` (workflow `docker-publish.yml` del repo SBA).
- BD: postgres:17 + restore de un `pg_dump -F c` de `sba_v1_staging` del VPS (el repo SBA NO
  puede bootstrapear su BD: seed git-ignorado, sin migraciones, schema Prisma incompleto).
- Certificados de firma: Secret `sba-sfl-key` montado en `/app/sfl/key/<NIT>/`. En staging del
  VPS solo existe el del NIT 494581027 (DEMO); URZACOM (155100020, CodMod=2) no tiene.
- La app escucha en **PORT=3001** (paridad con el compose del VPS). El egreso de los tenants hacia
  este ns lo habilita una regla propia en el template (`portal/k8s_utils/manifests.py`,
  namespaceSelector `app: sba` → 3001): con Cilium un `ipBlock` nunca matchea pods del cluster,
  así que el `0.0.0.0/0:443` de los tenants no sirve para llegar aquí (verificado en vivo).
- `/pub/*` sigue SIN auth: por eso no hay Ingress y la NetworkPolicy es obligatoria.
- PILOTO vs producción vive en la BD (`SFL_TabCon.CodAmb` por emisor + URLs en `SFL_TabPar`
  GruPar `1.2`); esta instancia nace del dump de staging → todo en CodAmb=2.

## Despliegue (resumen)

```bash
kubectl apply -f 00-namespace.yaml
# Secrets: se generan en el momento, NUNCA se commitean (ver deploy.md de la sesión 2026-08-14)
kubectl apply -f 02-postgres.yaml && kubectl -n sba-piloto rollout status deploy/db
# restore: pg_restore --no-owner del dump vía kubectl exec -i
kubectl apply -f 03-sba.yaml -f 04-netpol.yaml
```

Conexión de un tenant: ICP `l10n_bo_core.service_url = http://sba.sba-piloto.svc.cluster.local:3001`.
