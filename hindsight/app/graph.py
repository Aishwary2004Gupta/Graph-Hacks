import os, re
from falkordb import FalkorDB

_db = None
def db():
    global _db
    if _db is None:
        _db = FalkorDB(host=os.getenv("FALKORDB_HOST", "localhost"),
                       port=int(os.getenv("FALKORDB_PORT", "6379")),
                       username=os.getenv("FALKORDB_USERNAME") or None,
                       password=os.getenv("FALKORDB_PASSWORD") or None)
    return _db

def slug(s): return re.sub(r"[^a-z0-9]", "", (s or "demo").lower()) or "demo"

def g(kind, tenant, user=None):
    """One isolated graph per (kind, tenant[, user]) -- FalkorDB multigraph."""
    return db().select_graph(f"{kind}_{slug(tenant)}" + (f"_{slug(user)}" if user else ""))

def run(graph, q, params=None):
    res = graph.query(q, params or {})
    cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
    return [dict(zip(cols, row)) for row in res.result_set]
