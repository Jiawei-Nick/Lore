# lore — Project Goals

## North Star

**"Code as Documentation"** — engineering knowledge (schema, config, dependencies) evolves automatically with every code change, instead of depending on humans to keep docs up to date.

A developer opens a PR, lore reads the diff, understands what changed at the DB layer, explains the risk, and publishes a versioned report to Lark — without anyone writing a single doc entry by hand.

---

## End State

A developer on any service can:

1. Run `lore analyze` on any feature branch and immediately get a risk-rated explanation of what DB changes are included and what they affect.
2. Find the full schema history for any table in Lark — every change, every migration, every reviewer note — searchable and versioned.
3. Ask questions about the schema ("what does `status` in `orders` mean?", "which services write to `tb_wallet_*`?") and get answers from accumulated lore knowledge.
4. Receive automated alerts when a HIGH-risk migration lands, before it reaches production.

---

## Phase 1 — Core Pipeline (Implemented)

Local CLI trigger. Manual run per branch.

- [x] `lore init --db <url>` — one-time DB introspection → `lore-schema.json` + ERD parent page in Lark
- [x] `lore analyze --repo <path> --branch <name>` — diff → parse → Claude analyze → Lark child page
- [x] Parser support: Flyway, Liquibase XML, raw DDL
- [x] Claude model routing: Haiku for small/non-breaking, Sonnet for large/breaking changes
- [x] Schema store (`lore-schema.json`) incrementally updated on every run
- [x] Mermaid ERD auto-updated on Lark parent page after each run
- [x] MySQL introspection support alongside PostgreSQL
- [x] Connection profiles — `lore connections add/list/edit/remove`; `--save-as` and `--use` on `lore init`; interactive selection menu; stored in `~/.lore/connections.yaml`
- [x] `lore generate-erd` — category-based ERDs by table prefix; upload PNG and `.mmd` files to Lark Drive folders
- [x] `lore setup-erd-folders` — one-time creation of ERD Drive folders
- [x] Tenant base URL support via `LARK_BASE_URL` — no hardcoded hostnames
- [x] Report folder hierarchy — reports land in "Database Schema Change Report" > `{db_name}` sub-folder; flat layout for `test/*` branches
- [x] Lark API resilience — retry logic on all HTTP calls; HTTP 200 error body detection eliminates silent failures
- [x] Prompt caching — system prompt sent with `cache_control: ephemeral` on every run

---

## Phase 2 — Automation & Notifications

Eliminate manual trigger. lore runs itself.

- [ ] GitLab webhook source plugin — trigger `lore analyze` automatically on PR open/merge to release branch
- [ ] Slack output plugin — post risk summary to configured channel on every run
- [ ] Email output plugin — alert configured recipients on HIGH risk changes
- [ ] CI/CD integration — run lore as a pipeline step; fail build on HIGH risk without an explicit approval gate

---

## Phase 3 — Broader Code Analysis

Extend beyond SQL migration files.

- [ ] JPA / Hibernate entity parser — detect schema changes from `@Entity`, `@Column`, `@Table` annotations
- [ ] MyBatis mapper parser — extract schema usage from mapper XML
- [ ] ORM model parser — SQLAlchemy, Django ORM, ActiveRecord model definitions
- [ ] Apollo / Consul config change analysis — detect new/changed config keys, generate summaries
- [ ] Kubernetes ConfigMap analysis — track config changes in K8s YAML

---

## Phase 4 — Knowledge Graph & AI Assistant

Turn accumulated lore reports into a queryable knowledge base.

- [ ] Cross-service impact analysis — given a schema change, identify all services referencing the affected table/column across multiple repos
- [ ] AI Q&A over Lark Wiki — natural language queries over the accumulated schema knowledge
- [ ] Kafka / MQ topic relationship map — visualize which services produce/consume which topics
- [ ] Auto-generate release notes — summarize all changes merged to a release branch into a human-readable changelog
- [ ] AI code reviewer suggestions — flag schema changes that violate team conventions (missing FK index, VARCHAR > 255 without justification, etc.)

---

## Phase 5 — Governance & Audit

Enforce and enforce engineering standards automatically.

- [ ] Architecture governance rules — configurable rules engine (e.g. "all tables must have `created_at`")
- [ ] PII audit — flag columns that likely contain PII based on naming patterns (email, phone, ssn, dob)
- [ ] Scheduled full-scan — weekly re-scan of entire migration history to detect drift between `lore-schema.json` and actual DB
- [ ] Multi-repo support — run lore across multiple repos and merge into a single unified ERD and knowledge base

---

## Immediate Improvements (Tech Debt)

- [ ] YAML-format Liquibase parser — file header regex detects `.yaml/.yml` but YAML changeset parsing is not implemented
- [ ] Lark China region support — `LARK_BASE_URL` configures display URLs only; Lark API calls are still hardcoded to `open.larksuite.com`; needs dynamic endpoint routing for `open.feishu.cn`
- [ ] `lore diff` command — show what changed in `lore-schema.json` between two points in time without a full analyze run
- [ ] Config-driven model override — allow per-repo override of model routing thresholds in `lore.yaml`
- [x] Prompt caching — system prompt cached with `cache_control: ephemeral` (shipped in Phase 1)

---

## Success Criteria

Phase 1 is done when:
- `lore analyze` on a real repo branch produces a correct Lark child page with accurate risk rating and the parent page ERD is updated.

The project is complete when:
- No developer on the team manually writes a DB schema doc entry.
- The Lark Wiki is the authoritative, always-current source of truth for schema state.
- Any HIGH-risk migration triggers a notification before it can reach production unreviewed.
