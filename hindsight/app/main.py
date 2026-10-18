from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .graph import g, run
from .seed import seed
from . import agent

app = FastAPI(title="Hindsight")
class Ask(BaseModel): question: str; tenant: str = "acme"; user: str = "asha"
class Inc(BaseModel): service: str; tenant: str = "acme"; user: str = "asha"
class Seed(BaseModel): tenant: str = "acme"

@app.post("/api/seed")
def _seed(b: Seed): return seed(b.tenant)

@app.get("/api/graph")
def graph(tenant: str = "acme"):
    q = """MATCH (a)-[r]->(b) RETURN a.name AS a, labels(a)[0] AS al, type(r) AS rel, b.name AS b, labels(b)[0] AS bl"""
    return run(g("brain", tenant), q)

@app.post("/api/ask")
def ask(b: Ask): return agent.ask(b.question, b.tenant, b.user)

@app.post("/api/incident")
def incident(b: Inc): return agent.incident(b.service, b.tenant, b.user)

@app.get("/api/memory")
def memory(tenant: str = "acme", user: str = "asha"):
    gr = g("mem", tenant, user)
    try:
        return {"facts": run(gr, "MATCH (n:Entity)<-[:ABOUT]-(f:Fact) RETURN n.name AS entity, f.attribute AS attribute, f.value AS value, f.current AS current ORDER BY f.ts DESC LIMIT 20"),
                "episodes": run(gr, "MATCH (e:Episode) RETURN e.question AS question, e.ts AS ts ORDER BY ts DESC LIMIT 10")}
    except Exception: return {"facts": [], "episodes": []}

@app.get("/api/node")
def node_details(name: str, tenant: str = "acme"):
    gr = g("brain", tenant)
    try:
        info = run(gr, "MATCH (n {name:$name}) RETURN labels(n)[0] AS label, properties(n) AS props", {"name": name})
        edges = run(gr, "MATCH (n {name:$name})-[r]-(m) RETURN type(r) AS rel, labels(m)[0] AS target_label, m.name AS target, startNode(r) = n AS outgoing LIMIT 25", {"name": name})
        return {"node": info[0] if info else None, "edges": edges}
    except Exception as e:
        return {"error": str(e), "edges": []}

@app.get("/api/handoffs")
def handoffs(tenant: str = "acme"):
    try:
        return run(g("shared", tenant), "MATCH (h:Handoff)-[:FOR]->(c:Case) RETURN c.id AS case, h.frm AS frm, h.to AS to, h.summary AS summary, h.ts AS ts ORDER BY h.ts DESC LIMIT 20")
    except Exception:
        return []

app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
def index(): return FileResponse("static/index.html")
