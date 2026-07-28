"""
Legrand GeoAI — Orchestration Hatchet.

Hatchet est 100% responsable du pipeline documentaire :
upload (déclenchement) → validation → extraction/OCR (fan-out) →
chunking → embeddings → stockage vectoriel → finalisation.

Modules :
- client      : client Hatchet partagé (singleton)
- workflows   : DAG d'ingestion, OCR par page, crons de maintenance, ré-indexation
- worker      : point d'entrée du worker (enregistre les workflows)
"""
