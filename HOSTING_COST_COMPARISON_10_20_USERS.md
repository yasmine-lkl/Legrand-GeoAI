# Legrand GeoAI — Hosting Cost Study (10–20 users)

**Date:** 2026-04-09  
**Scope:** Production hosting cost estimate for your current stack (Next.js frontend, FastAPI backend, PostgreSQL, Redis, Ollama inference, Chroma/vector data).  
**Goal:** Most performant practical deployment for 10–20 internal users.

---

## 1) Workload assumptions used for pricing

To keep pricing consistent across providers, the same baseline was used:

- **Users:** 10–20 active users
- **Concurrent usage:** 3–8 users at busy moments
- **Availability target:** business-critical (single region + backups)
- **Inference:** self-hosted Ollama (GPU-backed in performance profile)
- **Storage:** 200 GB total (documents, vectors, DB, logs, backups)
- **Internet egress:** 200 GB/month
- **Hours/month:** 730

### Recommended architecture (performance-first)

- **Node A (App/API):** Next.js + FastAPI (CPU)
- **Node B (Inference):** Ollama on 1× T4/A10-class GPU
- **Managed PostgreSQL**
- **Managed Redis**
- **Object/block storage for docs and backups**

---

## 2) Pricing sources used

Because some official pages are calculator-driven/dynamic, this document uses public list pricing pages + instance catalogs, then computes monthly totals from hourly rates.

- AWS EC2 on-demand pricing: https://aws.amazon.com/ec2/pricing/on-demand/
- AWS RDS PostgreSQL pricing: https://aws.amazon.com/rds/postgresql/pricing/
- AWS ElastiCache pricing: https://aws.amazon.com/elasticache/pricing/
- GCP instance catalog (hourly list rows): https://instances.vantage.sh/gcp
- Azure instance catalog (hourly list rows): https://instances.vantage.sh/azure
- AWS GPU instance row (g4dn.xlarge): https://instances.vantage.sh/aws/ec2/g4dn.xlarge

> Notes:
> - Prices vary by **region**, discounts, committed-use plans, taxes, and currency.
> - Numbers below are **EUR estimates**, excluding VAT/taxes.
> - FX assumption used for conversion: **$1.00 = €0.92** (snapshot estimate date: 2026-04-09).

---

## 3) Monthly estimate by provider (performance profile)

## AWS (recommended cloud option)

Assumed components:
- GPU inference VM: **g4dn.xlarge** ($0.526/h) → **€353.26/mo**
- App/API VM (2–4 vCPU class): ~**€23/mo**
- RDS PostgreSQL (small production class): ~**€46/mo**
- ElastiCache Redis (small node): ~**€11/mo**
- Block/object storage + snapshots (200 GB mixed): ~**€18/mo**
- Egress (200 GB): ~**€17/mo**

**Estimated total AWS:** **~€469/month**

---

## Google Cloud (high performance, higher cost)

Assumed components:
- GPU inference VM: **A2 Highgpu 1g** ($0.8328/h from catalog) → **€560.22/mo**
- App/API VM (2–4 vCPU class): ~**€37/mo**
- Cloud SQL PostgreSQL (small production class): ~**€78/mo**
- Memorystore Redis (small): ~**€32/mo**
- Persistent storage + snapshots (200 GB mixed): ~**€17/mo**
- Egress (200 GB): ~**€22/mo**

**Estimated total GCP:** **~€746/month**

---

## Microsoft Azure (strong enterprise integration)

Assumed components:
- GPU inference VM (T4/A10 class, region-dependent): ~**$0.60/h** → **€403/mo**
- App/API VM (B/D-series small production): ~**€46/mo**
- Azure Database for PostgreSQL Flexible Server: ~**€69/mo**
- Azure Cache for Redis (entry production): ~**€37/mo**
- Managed disk/blob + backups (200 GB mixed): ~**€23/mo**
- Egress (200 GB): ~**€16/mo**

**Estimated total Azure:** **~€594/month**

---

## 4) On-premises estimate

### Single-server production baseline (good performance, lowest recurring cost)

Example hardware (1 server):
- CPU: Ryzen 9 / Xeon equivalent
- RAM: 64 GB ECC preferred
- GPU: RTX 4070 Ti Super (or RTX 4080 class)
- Storage: 2 TB NVMe (RAID/backup strategy)
- UPS + basic firewall/network gear

Estimated CAPEX:
- Server + GPU + RAM + storage + UPS/network: **€2,576 – €3,220**

Monthlyized over 36 months:
- Hardware amortization: **€72 – €89/mo**
- Power (average 250–350W, €0.17–€0.23/kWh): **€32 – €60/mo**
- Internet/static IP/security services: **€28 – €74/mo**
- Offsite backup/storage: **€14 – €37/mo**
- Maintenance/spares allowance: **€18 – €46/mo**

**Estimated on-prem monthly effective cost:** **~€166 – €304/month**

> Important: This is cheapest over time but has operational overhead and single-site failure risk unless you add redundancy.

---

## 5) Comparison table

| Option | Monthly estimate (EUR) | Performance for 10–20 users | Ops complexity | Reliability/HA path | Notes |
|---|---:|---|---|---|---|
| AWS | **~€469** | High (T4 GPU + managed services) | Medium | Excellent (mature managed stack) | Best cloud price/performance here |
| Azure | **~€594** | High | Medium | Excellent | Great with Microsoft ecosystem/compliance |
| GCP | **~€746** | Very high | Medium | Excellent | Strong AI ecosystem, higher monthly cost in this sizing |
| On-prem (single server) | **~€166–€304** | High (if sized well) | High | Medium (depends on your own redundancy) | Lowest recurring spend, highest ops burden |

---

## 6) Recommendation (most performant and practical)

## Primary recommendation: **AWS performance profile (~€469/mo)**

Why:
1. Best cloud balance of **cost + GPU performance** for your workload size.
2. Easy scale path (upgrade GPU class, add second app node, enable Multi-AZ DB).
3. Managed Postgres + Redis reduces incidents and admin effort.

### Suggested production shape for your project

- **GPU node:** g4dn.xlarge (Ollama + models)
- **App node:** small ARM/x86 compute for Next.js + FastAPI
- **DB:** RDS PostgreSQL single-AZ initially; move Multi-AZ when user load or SLA increases
- **Cache:** ElastiCache small node
- **Storage:** object store for documents + lifecycle + backup
- **Monitoring:** managed logs/metrics + alerting

---

## 7) If you optimize for lowest total spend

Choose **on-prem** only if you can operate it (patching, backups, UPS, monitoring, incident response).  
If you want low ops effort + good performance, choose **AWS cloud**.

---

## 8) Cost optimization levers (all providers)

1. Use 1-year committed discounts after first stable month (often 20–40% savings).
2. Keep GPU node fixed-size; autoscale only API node.
3. Store documents in object storage, not expensive DB volumes.
4. Compress logs + retain only operationally necessary windows.
5. Move embeddings/LLM to a lighter model for off-peak or background jobs.

---

## 9) Final decision guide

- Need fastest launch with least risk: **AWS**
- Need tight Microsoft enterprise integration: **Azure**
- Need GCP-native AI ecosystem despite higher baseline cost: **GCP**
- Need lowest recurring cost and accept infrastructure ownership: **On-prem**

---

## 10) Confidence + validation checklist

This estimate is a planning-grade model for your exact project architecture. Before procurement, validate with:

- Region-specific calculators (same region for all services)
- Exact DB/Redis tier and backup retention
- Real egress profile after 1 week pilot
- Final GPU class after load tests with your real prompts/documents

If needed, I can generate a **second version** of this document with:
- **Low-cost profile (CPU-only inference)**
- **High-availability profile (multi-zone + failover + DR)**
- **1-year and 3-year TCO side-by-side**
