# Security — Urban Twin

Urban Twin is a neighbourhood digital twin demo, not a multi-tenant production service. This document records the threat model and controls that apply to the current architecture.

---

## Principles

1. **Secrets never in git** — `.env` is gitignored; only `.env.example` (no real keys) is committed.
2. **Least privilege locally** — DB credentials are local Docker defaults (`urban`/`urban`), not reused in cloud.
3. **No secrets in logs** — HTTP clients must not log URLs that embed API keys (e.g. OpenWeather `appid`).
4. **Honest scope** — auth, multi-tenant isolation, and hardened Kafka are out of scope for v1; residual risk is documented instead of implied away.

---

## STRIDE (local architecture)

| Threat | Where it shows up | Mitigation now | Residual / later |
|---|---|---|---|
| **S**poofing | Anyone who can reach local ports can pretend to be a client | Bind WebSocket bridge to `127.0.0.1` only | Cloud: TLS + auth on `/ws/live` if exposed |
| **T**ampering | Kafka messages / DB rows altered on the host | Single-user host trust boundary; no untrusted network peers | Cloud: VPC, IAM, Kafka ACLs, DB TLS |
| **R**epudiation | Hard to prove who ingested what | Structured logs with timestamps; DB `ingested_at` | Cloud: centralized audit logs |
| **I**nformation disclosure | API keys in `.env`, logs, or git; PostGIS data | `.env` ignored; redact `appid` from HTTP logs; never commit `.env` | Secrets Manager / Terraform variables; rotate keys if leaked |
| **D**enial of service | Overpass / OpenWeather / local Kafka / REST flooded | Poll interval (≥5 min); single broker; **slowapi** rate limit on REST | Quotas in cloud; WAF later |
| **E**levation of privilege | N/A for v1 (no user roles) | No auth surface yet by design | If auth is added: least-privilege roles, no shared admin DB user in app |

Trust boundary for local development: the machine running Docker and the Python processes. Publishing services to the public internet expands the model — re-run STRIDE before a public deploy.

### Frontend controls (browser)

| Control | Why |
|---|---|
| Allowlisted `VITE_API_BASE` / `VITE_WS_URL` | Reject odd schemes/hosts (misconfig → unexpected exfil) |
| `credentials: "omit"` on REST | No cookie session surface in v1 |
| Abortable fetches | Cancel in-flight work on unmount |
| Validated WebSocket payloads | Ignore oversized / unknown reading types |
| Display sanitization (`safeText`) | Strip control chars from API strings before render |
| Referrer policy | Limit cross-origin referrer leakage |
| Production CSP (nginx later) | Prefer server headers; Cesium needs `blob:` workers + `wasm-unsafe-eval` — do **not** use a tight meta CSP in Vite or the globe goes black |

Map tiles use public Carto/OSM URLs — **no Mapbox token required**. Adding Mapbox would introduce another secret (A02) and paid dependency without improving the Cesium 3D twin.

---

## OWASP Top 10 (mapped)

| OWASP | Relevance | What we do |
|---|---|---|
| **A01 Broken Access Control** | No user accounts in v1 | Do not expose bridge/API publicly without auth |
| **A02 Cryptographic Failures** | API keys, future TLS | Secrets in env only; plan HTTPS on deploy |
| **A03 Injection** | SQL / Overpass / query params | SQLAlchemy/parameterized queries; Pydantic validation on readings; no raw SQL from user input |
| **A04 Insecure Design** | Kafka without auth locally | Acceptable on localhost; cloud Kafka needs auth |
| **A05 Security Misconfiguration** | Default DB password, open ports | Local-only defaults; do not publish 5433/9092/8001 on a public IP |
| **A06 Vulnerable Components** | Dependencies | Pin via `pyproject.toml`; refresh before deploy |
| **A07 Identification & Auth Failures** | Out of scope v1 | Explicit non-goal |
| **A08 Software & Data Integrity** | Model artifacts / Terraform state | Version artifacts; remote state locks for cloud |
| **A09 Security Logging & Failures** | Key leakage via logs | Suppress httpx URL logging for OpenWeather |
| **A10 SSRF** | Ingestion calls fixed provider URLs | Base URLs are constant in code; lat/lon from config, not raw client input |

---

## Controls in the repo

| Control | Location |
|---|---|
| `.env` gitignored | `.gitignore` |
| Example env without secrets | `.env.example` |
| Validated reading payloads | `urban_twin/ingestion/normalize.py` (Pydantic) |
| ORM instead of string-built SQL | `urban_twin/db/`, Alembic migrations |
| WebSocket bind localhost default | `urban_twin/websocket_bridge/main.py` |
| No API key in HTTP access logs | Ingestion configures httpx logger → WARNING |

---

## If a key was exposed

1. Rotate the key at the provider (e.g. [OpenWeather API keys](https://home.openweathermap.org/api_keys))
2. Update local `.env` only
3. Treat the old key as compromised

---

## Public deploy checklist

- [ ] Local pipeline green (ingest → Kafka → WS + API + forecast)
- [ ] Cloud **budget alert** set before first paid resource
- [ ] No secrets in Terraform state committed to git (`*.tfvars` gitignored)
- [ ] REST rate limiting (slowapi) verified
- [ ] Kafka and Postgres bound to localhost on the VM (not world-reachable)
- [ ] SSH locked to a `/32` CIDR
- [ ] Destroy or stop resources when not in use
