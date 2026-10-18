"""Agent tools. Every tool is a Cypher query or a FalkorDB graph algorithm."""
import time
from .graph import g, run

TOOLS = {}
def tool(desc, props, req):
    def deco(fn):
        TOOLS[fn.__name__] = {"fn": fn, "schema": {"name": fn.__name__, "description": desc,
            "input_schema": {"type": "object", "properties": props, "required": req}}}
        return fn
    return deco

SVC = {"service": {"type": "string", "description": "service name, e.g. postgres-main"}}
def B(ctx, q, p=None): return run(g("brain", ctx["tenant"]), q, p)
def M(ctx, q, p=None): return run(g("mem", ctx["tenant"], ctx["user"]), q, p)

@tool("What breaks if this service fails: services that transitively depend on it, by hop distance.", SVC, ["service"])
def blast_radius(ctx, service):
    q = """MATCH p=(d:Service)-[:DEPENDS_ON*1..4]->(s:Service {name:$service})
RETURN d.name AS service, d.tier AS tier, min(length(p)) AS hops ORDER BY hops, tier"""
    return q, B(ctx, q, {"service": service})

@tool("Recent deploys to this service or anything it depends on (likely root-cause suspects).", SVC, ["service"])
def recent_changes(ctx, service):
    q = """MATCH (s:Service {name:$service})-[:DEPENDS_ON*0..3]->(u:Service)<-[:DEPLOYED_TO]-(d:Deploy)-[:AUTHORED_BY]->(a:Person)
RETURN DISTINCT u.name AS service, d.name AS deploy, d.ts AS ts, d.summary AS summary, a.name AS author
ORDER BY ts DESC LIMIT 5"""
    return q, B(ctx, q, {"service": service})

@tool("Who to page: people who resolved incidents on this service, plus its owning team.", SVC, ["service"])
def who_knows(ctx, service):
    q1 = """MATCH (p:Person)-[:RESOLVED]->(i:Incident)-[:AFFECTED]->(s:Service {name:$service})
RETURN p.name AS person, count(i) AS incidents_resolved ORDER BY incidents_resolved DESC LIMIT 5"""
    q2 = """MATCH (t:Team)-[:OWNS]->(s:Service {name:$service}) OPTIONAL MATCH (p:Person)-[:MEMBER_OF]->(t)
RETURN t.name AS team, collect(p.name) AS members"""
    return q1 + "\n" + q2, B(ctx, q1, {"service": service}) + B(ctx, q2, {"service": service})

@tool("Past incidents touching this service with the deploy that caused them and the runbook used.", SVC, ["service"])
def past_incidents(ctx, service):
    q = """MATCH (i:Incident)-[:AFFECTED]->(s:Service {name:$service})
OPTIONAL MATCH (i)-[:CAUSED_BY]->(d:Deploy) OPTIONAL MATCH (i)-[:FOLLOWED]->(r:Runbook)
RETURN i.name AS incident, i.title AS title, i.sev AS sev, d.name AS deploy, d.summary AS cause, r.name AS runbook
ORDER BY i.date DESC"""
    return q, B(ctx, q, {"service": service})

@tool("Decisions about this service traced to source documents; flags decisions that were superseded.", SVC, ["service"])
def decision_trace(ctx, service):
    q = """MATCH (d:Decision)-[:ABOUT]->(s:Service {name:$service})
OPTIONAL MATCH (d)-[:SOURCED_FROM]->(doc:Document) OPTIONAL MATCH (d)-[:MADE_BY]->(p:Person)
OPTIONAL MATCH (n:Decision)-[:SUPERSEDES]->(d)
RETURN d.name AS decision, d.title AS title, d.rationale AS rationale, p.name AS by,
       doc.name AS source, doc.url AS url, n.name AS superseded_by ORDER BY d.date DESC"""
    return q, B(ctx, q, {"service": service})

@tool("Rank the most critical services using PageRank over the dependency graph.", {}, [])
def critical_services(ctx):
    q = """CALL algo.pageRank('Service','DEPENDS_ON') YIELD node, score
RETURN node.name AS service, score ORDER BY score DESC LIMIT 5"""
    return q, B(ctx, q)

@tool("Shortest connection between any two entities (service, person, incident...) in the company graph.",
      {"a": {"type": "string"}, "b": {"type": "string"}}, ["a", "b"])
def path_between(ctx, a, b):
    q = """MATCH (x {name:$a}), (y {name:$b})
MATCH p=shortestPath((x)-[*..6]-(y))
RETURN [n IN nodes(p) | n.name] AS path, [r IN relationships(p) | type(r)] AS via, length(p) AS hops LIMIT 1"""
    return q, B(ctx, q, {"a": a, "b": b})

@tool("Recall what this user previously learned or asked about an entity (per-user memory graph).",
      {"entity": {"type": "string"}}, ["entity"])
def recall(ctx, entity):
    q1 = """MATCH (n:Entity {name:$e})<-[:ABOUT]-(f:Fact {current:true})
RETURN 'fact' AS kind, f.attribute AS attribute, f.value AS value, f.ts AS ts"""
    q2 = """MATCH (n:Entity {name:$e})<-[:MENTIONS]-(ep:Episode)
RETURN 'episode' AS kind, ep.question AS attribute, ep.answer AS value, ep.ts AS ts ORDER BY ts DESC LIMIT 3"""
    try: rows = M(ctx, q1, {"e": entity}) + M(ctx, q2, {"e": entity})
    except Exception: rows = []
    return q1 + "\n" + q2, rows

@tool("Store a durable fact in memory. A newer value for the same attribute supersedes the old one.",
      {"subject": {"type": "string"}, "attribute": {"type": "string"}, "value": {"type": "string"}},
      ["subject", "attribute", "value"])
def remember(ctx, subject, attribute, value):
    gr, ts = g("mem", ctx["tenant"], ctx["user"]), int(time.time())
    olds = run(gr, "MATCH (:Entity {name:$s})<-[:ABOUT]-(o:Fact {attribute:$a, current:true}) SET o.current=false RETURN id(o) AS oid",
               {"s": subject, "a": attribute})
    new = run(gr, "MERGE (n:Entity {name:$s}) CREATE (f:Fact {attribute:$a, value:$v, current:true, ts:$ts})-[:ABOUT]->(n) RETURN id(f) AS fid",
              {"s": subject, "a": attribute, "v": value, "ts": ts})[0]["fid"]
    for o in olds:
        run(gr, "MATCH (f),(o) WHERE id(f)=$f AND id(o)=$o CREATE (f)-[:SUPERSEDES]->(o)", {"f": new, "o": o["oid"]})
    return "MERGE Entity; CREATE Fact-[:ABOUT]->Entity; Fact-[:SUPERSEDES]->old Fact", \
           [{"stored": f"{subject}.{attribute}={value}", "superseded": len(olds)}]

def record_episode(ctx, question, answer, entities):
    run(g("mem", ctx["tenant"], ctx["user"]),
        """CREATE (ep:Episode {question:$q, answer:$a, ts:$ts})
WITH ep UNWIND $ents AS e MERGE (n:Entity {name:e}) CREATE (ep)-[:MENTIONS]->(n)""",
        {"q": question, "a": answer[:1500], "ts": int(time.time()), "ents": entities or ["general"]})

def call_tool(name, args, ctx, trace):
    cypher, rows = TOOLS[name]["fn"](ctx, **args)
    touched = sorted({v for r in rows for x in r.values() for v in (x if isinstance(x, list) else [x]) if isinstance(v, str)})
    trace.append({"tool": name, "args": args, "cypher": cypher, "rows": rows, "touched": touched})
    return rows

# --- multi-agent shared state (Track 2): handoffs live in a graph every agent reads/writes ---
def write_handoff(tenant, case, frm, to, summary):
    run(g("shared", tenant), "MERGE (c:Case {id:$c}) CREATE (h:Handoff {frm:$f, to:$t, summary:$s, ts:$ts})-[:FOR]->(c)",
        {"c": case, "f": frm, "t": to, "s": summary, "ts": int(time.time() * 1000)})

def read_handoffs(tenant, case):
    return run(g("shared", tenant), "MATCH (h:Handoff)-[:FOR]->(:Case {id:$c}) RETURN h.frm AS frm, h.to AS to, h.summary AS summary ORDER BY h.ts", {"c": case})
