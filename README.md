# Hindsight — an on-call copilot whose context is a graph (FalkorDB)

**Tracks entered: 1 (Agents That Act on Connected Data), 2 (Agent Memory & Coordination), 3 (Company Brain).**

An incident agent that answers "what broke, what's the blast radius, who do I page, has this happened before, and
why was it built this way?" by walking a FalkorDB graph — and shows the exact Cypher + node path behind every answer.
**Remove FalkorDB and the product does nothing**: every tool is a Cypher query or graph algorithm.

## Run (local, 1 minute)
```bash
export ANTHROPIC_API_KEY=sk-...        # optional; without it a deterministic planner drives the same graph tools
docker compose up --build              # FalkorDB :6379, Browser :3001, app :8000
open http://localhost:8000             # graph auto-seeds with synthetic data
```
Without Docker: `docker run -p 6379:6379 falkordb/falkordb`, `pip install -r requirements.txt`, `uvicorn app.main:app`.

## Graph data model (one isolated graph per tenant / per user)
**`brain_<tenant>`** — company knowledge
```
(Team)-[:OWNS]->(Service)   (Person)-[:MEMBER_OF]->(Team)   (Service)-[:DEPENDS_ON]->(Service)
(Deploy)-[:DEPLOYED_TO]->(Service)   (Deploy)-[:AUTHORED_BY]->(Person)
(Incident)-[:AFFECTED]->(Service)   (Incident)-[:CAUSED_BY]->(Deploy)   (Incident)-[:FOLLOWED]->(Runbook)
(Person)-[:RESOLVED]->(Incident)   (Runbook)-[:DOCUMENTS]->(Service)
(Decision)-[:ABOUT]->(Service)  -[:MADE_BY]->(Person)  -[:SOURCED_FROM]->(Document)  (Decision)-[:SUPERSEDES]->(Decision)
```
**`mem_<tenant>_<user>`** — private memory: `(Episode)-[:MENTIONS]->(Entity)`, `(Fact)-[:ABOUT]->(Entity)`, `(Fact)-[:SUPERSEDES]->(Fact)`
**`shared_<tenant>`** — agent coordination: `(Handoff {frm,to,summary})-[:FOR]->(Case)`

## Cypher / algorithms the product depends on (`app/tools.py`)
| Tool | Technique |
|---|---|
| `blast_radius` | variable-length traversal `-[:DEPENDS_ON*1..4]->` + `min(length(p))` |
| `recent_changes` | `*0..3` upstream walk joined to Deploy → Author |
| `who_knows` | Person→RESOLVED→Incident→AFFECTED→Service aggregation + team ownership |
| `decision_trace` | Decision→SOURCED_FROM→Document, `SUPERSEDES` to flag stale decisions |
| `critical_services` | **`algo.pageRank('Service','DEPENDS_ON')`** |
| `path_between` | **`shortestPath((x)-[*..6]-(y))`** — the "Why" path |
| `recall` / `remember` | episodic + semantic memory, versioned facts via `SUPERSEDES` |

## Track mapping
1. **Act on connected data** — LLM chooses graph tools via tool-use; multi-hop reasoning; explainable trace in the UI.
2. **Memory & coordination** — per-user graphs (tenant isolation), episodic/semantic memory, Triage→Investigator→Scribe handoffs through the shared graph.
3. **Company brain** — services/people/deploys/incidents/decisions/docs in one graph; sources on every decision; `SUPERSEDES` keeps knowledge current.

