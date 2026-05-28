# lore — Backlog

Features planned for future phases. Phase 1 scope is tracked in the implementation plan.

---

## Phase 2 — Automation & Notifications

- [ ] **GitLab webhook source plugin** — trigger `lore analyze` automatically on PR opened/merged to release branch
- [ ] **Slack output plugin** — post analysis summary + risk level to a configured Slack channel
- [ ] **Email output plugin** — send change report to configured recipients on HIGH risk changes
- [ ] **CI/CD integration** — run lore as a pipeline step, fail pipeline on HIGH risk without manual approval gate

---

## Phase 3 — Broader Code Analysis

- [ ] **JPA / Hibernate entity parser** — detect schema changes from `@Entity`, `@Column`, `@Table` annotations
- [ ] **MyBatis mapper parser** — extract schema usage from mapper XML files
- [ ] **ORM model parser** — support SQLAlchemy, Django ORM, ActiveRecord model definitions
- [ ] **Apollo / Consul config change analysis** — detect new/changed config keys and generate summaries
- [ ] **Kubernetes ConfigMap analysis** — track config changes in K8s YAML

---

## Phase 4 — Knowledge Graph & AI Assistant

- [ ] **Cross-service impact analysis** — given a schema change, identify all services that reference the affected table/column across multiple repos
- [ ] **AI Q&A over Lark Wiki** — query accumulated lore knowledge ("what does the `status` column in `orders` mean?")
- [ ] **Kafka / MQ Topic relationship map** — visualize which services produce/consume which topics
- [ ] **Auto-generate Release Notes** — summarize all changes merged to release branch into a human-readable release note
- [ ] **AI Code Reviewer suggestions** — flag schema changes that violate team conventions (e.g. missing index on FK column)

---

## Phase 5 — Governance & Audit

- [ ] **Architecture governance rules** — configurable rules engine (e.g. "all tables must have `created_at`", "no VARCHAR > 255 without justification")
- [ ] **Security audit** — flag columns that may contain PII based on naming (email, phone, ssn, dob)
- [ ] **Scheduled full-scan** — weekly re-scan of entire migration history to detect drift between `lore-schema.json` and actual migrations
- [ ] **Multi-repo support** — run lore across multiple repos and merge into a single unified ERD and knowledge base

---

## Improvements & Tech Debt

- [x] **MySQL / MariaDB introspection** — `lore init` supports `mysql://` and `jdbc:mysql://` via `pymysql` (shipped)
- [ ] **YAML-format Liquibase parser** — file header regex detects `.yaml/.yml` but parsing still falls through to XML; actual YAML changeset parsing not implemented
- [ ] **Lark China region support** — `LARK_BASE_URL` configures display URLs only; Lark API calls are still hardcoded to `open.larksuite.com`; needs dynamic endpoint routing for `open.feishu.cn`
- [ ] **`lore diff` command** — show what changed in `lore-schema.json` between two points in time without triggering a full analyze run
- [ ] **Config-driven model override** — allow per-repo override of model routing thresholds in `lore.yaml`
- [ ] **Prompt caching warm-up** — pre-cache system prompt on startup to reduce first-run latency
