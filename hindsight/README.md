# Hindsight — Graph-Native Autonomous On-Call Copilot & SRE Swarm
<img width="800" height="450" alt="Hindsight-demo-ezgif com-video-to-gif-converter" src="https://github.com/user-attachments/assets/dc46b4c9-eae6-41de-a0b5-82e722de07ff" />

> **WeMakeDevs & FalkorDB Hackathon Submission**  
> **Tracks Entered:**  
> 🏆 **Track 1:** Agents That Act on Connected Data  
> 🏆 **Track 2:** Agent Memory & Coordination  
> 🏆 **Track 3:** Company Brain  

---

## 🎯 What is Hindsight?
When a critical production outage strikes at 3 AM, on-call engineers face the same 5 high-stress questions:
1. **What broke?** (Which recent deployment or change in the dependency chain caused the failure?)
2. **What's the blast radius?** (Which downstream tier-1/tier-2 services are transitively impacted?)
3. **Who do I page?** (Who has resolved this specific failure mode before, and which team owns the affected service?)
4. **Has this happened before?** (What incident precedents and active runbooks exist?)
5. **Why was it built this way?** (What architectural RFC decisions and postmortems justify this configuration?)

Traditional RAG and vector databases hallucinate, fail at multi-hop graph traversals, and cannot trace recursive service dependencies. 

**Hindsight solves this by placing FalkorDB at the dead center of incident response.**
> **Rule 3 Compliance:** Remove FalkorDB and the product does nothing. Every single copilot action, root-cause calculation, and multi-agent coordination step is executed as a Cypher query or native FalkorDB graph algorithm (`algo.pageRank`, `shortestPath`, variable-length traversals).

---

## 🎥 Demo Video 




## 🚀 Quickstart (1 Minute Local Setup)

### Option A: Docker Compose (Recommended)
```bash
# 1. Start FalkorDB (:6379), FalkorDB Visual Browser (:3001), and Hindsight App (:8000)
docker compose up --build

# 2. Open the Mission Control Dashboard
open http://localhost:8000
```

### Option B: Bare Metal (Without Docker)
```bash
docker run -d -p 6379:6379 -p 3001:3000 --name falkordb falkordb/falkordb:latest
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🧠 Multi-Graph Architecture (Isolation & Multitenancy)

Hindsight leverages FalkorDB's multi-graph capability to maintain strict physical isolation between company knowledge, private user memories, and multi-agent coordination state:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Company Brain Graph: brain_<tenant>                                │
│                                                                        │
│   (Team) ──[:OWNS]──> (Service) <──[:DEPENDS_ON*]── (Service)          │
│      ▲                                                    ▲            │
│  [:MEMBER_OF]                                      [:DEPLOYED_TO]      │
│      │                                                    │            │
│   (Person) <──[:AUTHORED_BY]──────────────────────── (Deploy)          │
│      │                                                    ▲            │
│  [:RESOLVED]                                       [:CAUSED_BY]        │
│      ▼                                                    │            │
│  (Incident) ──[:AFFECTED]──> (Service)                    │            │
│      │                                                    │            │
│  [:FOLLOWED]                                              │            │
│      ▼                                                    │            │
│  (Runbook) ──[:DOCUMENTS]──> (Service)                    │            │
│                                                           │            │
│  (Decision) ──[:ABOUT]──> (Service)                       │            │
│      ├──[:MADE_BY]──> (Person)                            │            │
│      ├──[:SOURCED_FROM]──> (Document / RFC)               │            │
│      └──[:SUPERSEDES]──> (Older Decision)                 │            │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ 2. Isolated Agent Memory Graph: mem_<tenant>_<user>                    │
│                                                                        │
│   (Episode) ──[:MENTIONS]──> (Entity) <──[:ABOUT]── (Fact {current})   │
│                                                        │               │
│                                                 [:SUPERSEDES]          │
│                                                        ▼               │
│                                              (Historical Fact)         │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ 3. Multi-Agent Shared Coordination Graph: shared_<tenant>              │
│                                                                        │
│   (Handoff: Triage ➔ Investigator) ──[:FOR]──> (Case: <case_id>)       │
│   (Handoff: Investigator ➔ Scribe) ──[:FOR]──> (Case: <case_id>)       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Core Cypher Queries & Graph Algorithms (`app/tools.py`)

| Tool Name | FalkorDB Cypher Technique | Real-World SRE Purpose |
| :--- | :--- | :--- |
| **`blast_radius`** | Variable-length path traversal `-[:DEPENDS_ON*1..4]->` with `min(length(p))` | Instantly identifies every downstream service impacted by a dependency failure. |
| **`recent_changes`** | Upstream transitive walk `*0..3` joined to `Deploy` and `Author` | Discovers suspect deployments authored by engineers in the failure tree. |
| **`who_knows`** | Graph aggregation: `Person→RESOLVED→Incident→AFFECTED→Service` + `Team→OWNS` | Recommends specific engineers with historical MTTR resolution experience. |
| **`critical_services`** | **`CALL algo.pageRank('Service', 'DEPENDS_ON')`** | Calculates topological centrality to discover single points of failure across infrastructure. |
| **`path_between`** | **`shortestPath((x)-[*..6]-(y))`** | Explains multi-hop connectivity between any two entities in the company graph. |
| **`decision_trace`** | Lineage traversal: `Decision→SOURCED_FROM→Document` + `SUPERSEDES` | Traces architecture decisions back to RFCs; warns if a decision was superseded. |
| **`recall` / `remember`** | Dual-nature memory: `Episode` (interaction log) + versioned `Fact` (`SUPERSEDES`) | Prevents duplicate investigations; persists engineer preferences across sessions. |

---

## 🏆 Hackathon Track Alignment

### 1. Track 01 — Agents That Act on Connected Data
- LLM autonomous tool calling selecting multi-hop graph queries.
- Graph traversals directly determine on-call decisions and blast radius mitigation.
- Complete explainability: every answer displays the exact FalkorDB Cypher queries and node traversal paths in the UI.

### 2. Track 02 — Agent Memory & Coordination
- **Tenant & User Memory Isolation:** `mem_<tenant>_<user>` ensures each SRE's context remains private.
- **Fact Versioning via Graph:** New knowledge automatically links `(new_fact)-[:SUPERSEDES]->(old_fact)`, invalidating stale facts without loss of history.
- **Autonomous Swarm Coordination:** 3 specialized agents (**Triage Agent** ➔ **Investigator Agent** ➔ **Scribe Agent**) coordinate exclusively through handoff nodes in `shared_<tenant>`.

### 3. Track 03 — Company Brain
- Unified enterprise graph connecting Services, Deploys, Incidents, Runbooks, People, Teams, RFCs, and Decisions.
- Every architectural choice is linked to source documentation (`RFC-27`, Postmortems).
- Graph-native ownership and domain knowledge mapping (`who_knows`).

---

## 📋 Hackathon Rule Disclosures
- **Primary Database:** FalkorDB (low-latency Graph Database).
- **Synthetic Data:** All services, engineers, deployments, incidents, and decisions are synthetic and provided in `app/seed.py`.
- **AI Tooling Disclosure (Rule 11):** AI assistant tooling (Claude) was utilized as a help.

