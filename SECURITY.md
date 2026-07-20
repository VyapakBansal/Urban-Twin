# Security Notes — Urban Twin

Working notes for Week 1–2. This is a portfolio learning project, not a production threat model — but we apply **OWASP** and **STRIDE** deliberately so decisions are explainable in interviews.

---

## Principles we follow now

1. **Secrets never in git** — `.env` is gitignored; only `.env.example` (no real keys) is committed.
2. **Least privilege locally** — DB credentials are local Docker defaults (`urban`/`urban`), not reused in cloud.
3. **No secret in logs** — HTTP clients must not log URLs that embed API keys (OpenWeather `appid` query param).
4. **Honest scope** — auth, multi-tenant isolation, and hardened Kafka are out of scope for v1; we document residual risk instead of pretending it isn’t there.

---

## STRIDE (current local architecture)

| Threat | Where it shows up | Mitigation now | Residual / later |
|---|---|---|---|
| **S**poofing | Anyone who can reach local ports can pretend to be a client | Bind WebSocket bridge to `127.0.0.1` only | Cloud: TLS + auth on `/ws/live` if exposed |
| **T**ampering | Kafka messages / DB rows altered on the host | Single-user laptop trust boundary; no untrusted network peers | Cloud: VPC, IAM, Kafka ACLs, DB TLS |
| **R**epudiation | Hard to prove who ingested what | Structured logs with timestamps; DB `ingested_at` | Cloud: centralized audit logs |
| **I**nformation disclosure | API keys in `.env`, logs, or git; PostGIS data | `.env` ignored; redact `appid` from HTTP logs; never commit `.env` | Secrets Manager / Terraform variables; rotate keys if leaked |
| **D**enial of service | Overpass / OpenWeather / local Kafka flooded | Poll interval (≥5 min); single broker learning setup | Rate limits (slowapi) on REST; quotas in cloud |
| **E**levation of privilege | N/A for v1 (no user roles) | No auth surface yet by design | If auth is added: least-privilege roles, no shared admin DB user in app |

Trust boundary today: **your laptop**. Docker services and Python processes are inside that boundary. Crossing to the public internet (Week 4–5 deploy) expands the model — re-run STRIDE then.

---

## OWASP Top 10 (mapped to what we’ve built)

| OWASP | Relevance | What we do |
|---|---|---|
| **A01 Broken Access Control** | No user accounts in v1 | Do not expose bridge/API publicly without auth later |
| **A02 Cryptographic Failures** | API keys, future TLS | Secrets in env only; plan HTTPS on deploy |
| **A03 Injection** | SQL / Overpass / query params | SQLAlchemy/parameterized queries; Pydantic validation on readings; no raw SQL from user input |
| **A04 Insecure Design** | Kafka without auth locally | Acceptable on localhost; document that cloud Kafka needs auth |
| **A05 Security Misconfiguration** | Default DB password, open ports | Local-only defaults; host port 5433/9092/8001 — don’t publish them on a public IP |
| **A06 Vulnerable Components** | Dependencies | Pin via `pyproject.toml`; refresh before deploy |
| **A07 Identification & Auth Failures** | Out of scope v1 | Explicit non-goal; don’t ship a “fake” login |
| **A08 Software & Data Integrity** | Model artifacts / Terraform state later | S3 versioning + remote state locks (Week 4) |
| **A09 Security Logging & Failures** | Key leakage via logs | Suppress httpx URL logging for OpenWeather; don’t paste keys into chats/screenshots |
| **A10 SSRF** | Ingestion calls fixed OpenWeather URL | Base URL is constant in code; lat/lon from config, not raw client input |

---

## Concrete controls already in the repo

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

OpenWeather keys can appear in terminal output if logged. If that happened:

1. Rotate the key at [OpenWeather API keys](https://home.openweathermap.org/api_keys)
2. Update local `.env` only
3. Treat old key as compromised

---

## Week 4+ checklist (before public demo)

- [ ] No secrets in Terraform state committed to git  
- [ ] CloudWatch / billing alarm (cost + abuse signal)  
- [ ] TLS on public HTTPS endpoints  
- [ ] REST rate limiting (slowapi) as in PRD  
- [ ] Revisit STRIDE with AWS VPC as the new trust boundary  
- [ ] Confirm Kafka and Postgres are not world-reachable  
