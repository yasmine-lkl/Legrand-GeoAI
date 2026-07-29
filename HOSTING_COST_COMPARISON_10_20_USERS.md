# Legrand GeoAI — Hosting Cost Study (10–20 users)

**Date:** 2026-04-09 · **Architecture review:** 2026-07-29
**Scope:** Production hosting cost estimate for your current stack (Next.js frontend, FastAPI backend, PostgreSQL, Redis, Ollama inference, Chroma/vector data).
**Goal:** Most performant practical deployment for 10–20 internal users.

>  **Read § 0 first.** This study was priced against an earlier version of the
> stack. The architecture has since changed (Redis dropped, Hatchet added, GPU
> sizing measured). § 0 restates the assumptions and adjusts the totals; the
> original per-provider breakdowns below are kept unchanged for traceability.

---

## 0) Architecture update since this study was written

**What changed in the stack**

| Component priced below | Current reality (2026-07-29) |
|---|---|
| Redis / managed cache | **Removed.** Orchestration is Hatchet (`hatchet-lite`), whose message queue is backed by PostgreSQL. No Redis anywhere in `docker-compose.yml`. |
| — | **Added: Hatchet engine + a second PostgreSQL database** (isolated from the app DB) + a dedicated `hatchet-worker` container running the ingestion DAG. |
| "Ollama on 1× T4/A10-class GPU" | Still correct, and now backed by measurement — see the GPU sizing note below. |
| Single app node running Next.js + FastAPI | Now **three** app-side containers: `frontend`, `backend` (API + reranker on CPU), `hatchet-worker` (Docling + OCR + VLM calls). The worker is memory-hungry (8 GB limit) but its heavy compute is delegated to the GPU node via Ollama. |

**Net effect on the monthly estimates**

| Provider | As priced below | Adjustment | Adjusted |
|---|---:|---|---:|
| AWS | ~€469 | −€11 (drop ElastiCache) · +€12 (upsize app node for worker + Hatchet engine; Hatchet's DB is a second database on the same RDS instance) | **~€470** |
| Azure | ~€594 | −€37 (drop Azure Cache) · +€15 | **~€572** |
| GCP | ~€746 | −€32 (drop Memorystore) · +€15 | **~€729** |
| On-prem (single server) | ~€166–304 | unchanged (everything is colocated) | **~€166–304** |

The adjustment is close to neutral: removing the managed cache roughly pays for
the larger app node. **The comparison and the recommendation below still hold.**

**GPU sizing — measured, not estimated**

Measurements were taken on the development machine (RTX 4060 Laptop, 8 GB) and
are documented in [PRESENTATION_TECHNIQUE.md § 11](PRESENTATION_TECHNIQUE.md#11-performance--chiffres-mesurés).

| VRAM | Verdict for this workload |
|---|---|
| 8 GB | Works: `qwen3:8b` (num_ctx 12288, KV cache `q8_0`) + BGE-M3 + `qwen2.5vl:7b` **sequentially**. Vision OCR ≈ 120 s/page; `OLLAMA_NUM_PARALLEL` must stay at 1. Adequate for dev, tight for production. |
| **16–24 GB (T4 16 GB / A10 24 GB / RTX 4090)** | **Recommended production target.** LLM + embeddings + VLM stay resident, `OLLAMA_NUM_PARALLEL > 1` becomes possible, vision OCR gets substantially faster. This is what the g4dn.xlarge (T4, 16 GB) line item below buys. |
| 48 GB (RTX 6000 Ada / A6000) | Needed only for `qwen3:32b`. Better answer quality, materially higher cost. |

A useful non-obvious finding: during vision inference the GPU is **compute-bound,
not VRAM-bound**. Raising concurrency on a small card does not increase
throughput — it pushes pages past the 300 s timeout and **drops pages**. So VRAM
headroom buys resident models and parallel *chat* generations, not faster OCR of
a single page; faster OCR requires a genuinely faster card.

**One cost lever this study does not capture**

The reranker (`bge-reranker-v2-m3`, CrossEncoder) currently runs on **CPU** in
the backend container, at ~0.75 s per candidate — about 12 s of the ~18 s
time-to-first-token. Moving it to the GPU node would cut that to 1–2 s. This
argues for either a GPU with headroom beyond the LLM's needs, or a CPU class on
the app node chosen for single-thread performance rather than core count.

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

- **Node A (App/API):** Next.js + FastAPI (CPU) — *plus the Hatchet engine and
  the `hatchet-worker` ingestion process; see § 0*
- **Node B (Inference):** Ollama on 1× T4/A10-class GPU
- **Managed PostgreSQL** — *two databases on the same instance: app + Hatchet*
- ~~**Managed Redis**~~ — *no longer used; Hatchet's queue is PostgreSQL-backed (§ 0)*
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
- ~~ElastiCache Redis (small node): ~**€11/mo**~~ *(no longer needed — § 0)*
- Block/object storage + snapshots (200 GB mixed): ~**€18/mo**
- Egress (200 GB): ~**€17/mo**

**Estimated total AWS:** **~€469/month** · *adjusted for the current stack:*
***~€470/month*** *(§ 0)*

---

## Google Cloud (high performance, higher cost)

Assumed components:
- GPU inference VM: **A2 Highgpu 1g** ($0.8328/h from catalog) → **€560.22/mo**
- App/API VM (2–4 vCPU class): ~**€37/mo**
- Cloud SQL PostgreSQL (small production class): ~**€78/mo**
- ~~Memorystore Redis (small): ~**€32/mo**~~ *(no longer needed — § 0)*
- Persistent storage + snapshots (200 GB mixed): ~**€17/mo**
- Egress (200 GB): ~**€22/mo**

**Estimated total GCP:** **~€746/month** · *adjusted:* ***~€729/month*** *(§ 0)*

---

## Microsoft Azure (strong enterprise integration)

Assumed components:
- GPU inference VM (T4/A10 class, region-dependent): ~**$0.60/h** → **€403/mo**
- App/API VM (B/D-series small production): ~**€46/mo**
- Azure Database for PostgreSQL Flexible Server: ~**€69/mo**
- ~~Azure Cache for Redis (entry production): ~**€37/mo**~~ *(no longer needed — § 0)*
- Managed disk/blob + backups (200 GB mixed): ~**€23/mo**
- Egress (200 GB): ~**€16/mo**

**Estimated total Azure:** **~€594/month** · *adjusted:* ***~€572/month*** *(§ 0)*

---

## 4) On-premises estimate

### Single-server production baseline (good performance, lowest recurring cost)

Example hardware (1 server):
- CPU: Ryzen 9 / Xeon equivalent — prioritise single-thread performance (CPU reranker, § 0)
- RAM: 64 GB ECC preferred (the `hatchet-worker` container alone is capped at 8 GB)
- GPU: RTX 4070 Ti Super **16 GB** (or RTX 4080 / 4090 class) — 16 GB is the
  practical floor for production; 8 GB works but forces sequential inference (§ 0)
- Storage: 2 TB NVMe (RAID/backup strategy) — allow ~35 GB for Docker images + model weights
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

| Option | As priced | Adjusted (§ 0) | Performance for 10–20 users | Ops complexity | Reliability/HA path | Notes |
|---|---:|---:|---|---|---|---|
| AWS | ~€469 | **~€470** | High (T4 16 GB + managed services) | Medium | Excellent (mature managed stack) | Best cloud price/performance here |
| Azure | ~€594 | **~€572** | High | Medium | Excellent | Great with Microsoft ecosystem/compliance |
| GCP | ~€746 | **~€729** | Very high | Medium | Excellent | Strong AI ecosystem, higher monthly cost in this sizing |
| On-prem (single server) | ~€166–304 | **~€166–€304** | High (if sized well) | High | Medium (depends on your own redundancy) | Lowest recurring spend, highest ops burden |

> **Non-financial argument that outweighs the table.** With a self-hosted LLM
> there is **no per-token cost**: spend is fixed regardless of usage. A SaaS
> alternative bills per request, so its cost grows with adoption — precisely
> when the tool starts being useful. Add to that the reason the project exists:
> plans, site coordinates and client data **cannot** leave the network.

---

## 6) Recommendation (most performant and practical)

## Primary recommendation: **AWS performance profile (~€469/mo)**

Why:
1. Best cloud balance of **cost + GPU performance** for your workload size.
2. Easy scale path (upgrade GPU class, add second app node, enable Multi-AZ DB).
3. Managed Postgres + Redis reduces incidents and admin effort.

### Suggested production shape for your project

- **GPU node:** g4dn.xlarge (T4 16 GB — Ollama: LLM + BGE-M3 + VLM)
- **App node:** x86 compute for Next.js + FastAPI + Hatchet engine +
  `hatchet-worker`. Favour **single-thread performance** over core count: the
  CrossEncoder reranker is CPU-bound and sets time-to-first-token (§ 0).
- **DB:** RDS PostgreSQL single-AZ initially, hosting **two databases** (app +
  Hatchet); move Multi-AZ when user load or SLA increases
- ~~**Cache:** ElastiCache small node~~ — not used (§ 0)
- **Storage:** block volume for uploads + ChromaDB (both need POSIX access from
  the containers), object store for backups + lifecycle
- **Monitoring:** managed logs/metrics + alerting, wired to
  `GET /api/health/ready` (returns 503 with per-dependency detail)

> Note on storage: `uploads_data` (source-of-truth files) and `chromadb_data`
> (embedded `PersistentClient`) are **filesystem** volumes, not object storage.
> Object storage is for backups. Backing up `pg_data` + `uploads_data` is
> sufficient — the vector index rebuilds via collection re-indexing.

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

This estimate is a planning-grade model for your project architecture. Before procurement, validate with:

- Region-specific calculators (same region for all services)
- Exact DB tier and backup retention (**two databases** on one instance: app + Hatchet)
- Real egress profile after 1 week pilot
- Final GPU class after load tests with your real prompts/documents —
  specifically: time-to-first-token on chat, and seconds/page on your worst
  scanned PDF (the two numbers users actually feel)
- App-node CPU choice validated against reranker latency, not just core count
- Disk sizing: Docker images ~15–20 GB (the backend image bakes Docling,
  EasyOCR, BGE-M3 tokenizer and the reranker for offline operation) + 6–20 GB of
  Ollama model weights, on top of documents and vectors

Not yet modelled, available on request:
- **Low-cost profile (CPU-only inference)** — note that vision OCR becomes
  impractical without a GPU
- **High-availability profile (multi-zone + failover + DR)**
- **1-year and 3-year TCO side-by-side**
- **48 GB GPU profile** for `qwen3:32b`
