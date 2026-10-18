"""Synthetic company data (rules: public/synthetic data only)."""
from .graph import g, db, slug

def nodes(gr, label, rows):
    gr.query(f"UNWIND $rows AS r MERGE (n:{label} {{name:r.name}}) SET n += r", {"rows": rows})

def edges(gr, la, rel, lb, pairs):
    gr.query(f"UNWIND $rows AS r MATCH (a:{la} {{name:r[0]}}),(b:{lb} {{name:r[1]}}) "
             f"MERGE (a)-[:{rel}]->(b)", {"rows": [list(p) for p in pairs]})

SERVICES = [("web-frontend",1),("checkout-api",1),("payments-svc",1),("auth-svc",1),("inventory-svc",2),
            ("search-svc",2),("recommendations-svc",3),("notifications-svc",3),("postgres-main",1),
            ("redis-cache",2),("kafka-bus",2)]
DEPENDS = [("web-frontend","checkout-api"),("web-frontend","auth-svc"),("web-frontend","search-svc"),
 ("checkout-api","payments-svc"),("checkout-api","inventory-svc"),("checkout-api","auth-svc"),
 ("checkout-api","notifications-svc"),("payments-svc","postgres-main"),("payments-svc","kafka-bus"),
 ("auth-svc","postgres-main"),("auth-svc","redis-cache"),("inventory-svc","postgres-main"),
 ("inventory-svc","kafka-bus"),("search-svc","redis-cache"),("recommendations-svc","redis-cache"),
 ("recommendations-svc","search-svc"),("notifications-svc","kafka-bus")]
TEAMS = {"Payments":["payments-svc","checkout-api"],"Platform":["postgres-main","redis-cache","kafka-bus","auth-svc"],
         "Growth":["search-svc","recommendations-svc","web-frontend"],"Fulfilment":["inventory-svc","notifications-svc"]}
PEOPLE = {"Asha":"Platform","Ben":"Platform","Gus":"Platform","Chen":"Payments","Dara":"Payments",
          "Eli":"Growth","Hana":"Growth","Farah":"Fulfilment"}
# name, service, author, ts, summary
DEPLOYS = [("deploy-4700","postgres-main","Ben","2026-09-02","Reduce connection pool to 20"),
 ("deploy-4760","redis-cache","Gus","2026-09-19","Lower maxmemory on session cache"),
 ("deploy-4790","kafka-bus","Gus","2026-09-30","Cut topic retention to 48h"),
 ("deploy-4801","payments-svc","Dara","2026-10-07","Retry logic change without idempotency"),
 ("deploy-4821","postgres-main","Ben","2026-10-12","Raise pool max to 50"),
 ("deploy-4833","payments-svc","Chen","2026-10-14","Idempotency keys v2"),
 ("deploy-4840","redis-cache","Gus","2026-10-15","Eviction policy allkeys-lru"),
 ("deploy-4845","auth-svc","Asha","2026-10-16","Rotate JWT signing keys"),
 ("deploy-4850","kafka-bus","Gus","2026-10-17","Partition rebalance")]
# name, sev, date, title, cause deploy, [services], [resolvers], runbook
INCIDENTS = [("INC-101",1,"2026-09-03","Connection exhaustion on primary DB","deploy-4700",["postgres-main","payments-svc","auth-svc"],["Ben","Asha"],"RB-pg-pool"),
 ("INC-102",2,"2026-09-20","Cache eviction storm","deploy-4760",["redis-cache","auth-svc","search-svc"],["Gus","Asha"],"RB-redis-evict"),
 ("INC-103",2,"2026-10-01","Consumer lag after retention cut","deploy-4790",["kafka-bus","notifications-svc","payments-svc"],["Gus"],"RB-kafka-lag"),
 ("INC-104",1,"2026-10-08","Double charges at checkout","deploy-4801",["checkout-api","payments-svc"],["Chen","Dara"],"RB-idempotency")]
RUNBOOKS = {"RB-pg-pool":"postgres-main","RB-redis-evict":"redis-cache","RB-kafka-lag":"kafka-bus","RB-idempotency":"payments-svc"}
DOCS = [("RFC-27 Connection pooling","https://docs.example.com/rfc-27"),("Postmortem INC-102","https://docs.example.com/pm-102"),
        ("Postmortem INC-103","https://docs.example.com/pm-103"),("Postmortem INC-104","https://docs.example.com/pm-104"),
        ("RFC-31 Kafka retention","https://docs.example.com/rfc-31")]
# name, title/rationale, service, person, doc, date
DECISIONS = [("DEC-1","Cap Postgres pool at 20 per service","Prevents one service starving the DB","postgres-main","Ben","RFC-27 Connection pooling","2026-08-20"),
 ("DEC-2","Idempotency keys on all payment retries","Retries caused double charges","payments-svc","Chen","Postmortem INC-104","2026-10-09"),
 ("DEC-3","LRU eviction for session cache","Storm came from unbounded sessions","redis-cache","Gus","Postmortem INC-102","2026-09-22"),
 ("DEC-4","Cap Kafka retention at 48h","Reduce storage cost","kafka-bus","Gus","RFC-31 Kafka retention","2026-09-25"),
 ("DEC-5","Restore Kafka retention to 7 days","48h starved slow consumers","kafka-bus","Gus","Postmortem INC-103","2026-10-02")]

def seed(tenant):
    name = f"brain_{slug(tenant)}"
    try: db().select_graph(name).delete()
    except Exception: pass
    gr = db().select_graph(name)
    for lbl in ("Service","Person","Team","Deploy","Incident","Decision","Document","Runbook"):
        try: gr.query(f"CREATE INDEX FOR (n:{lbl}) ON (n.name)")
        except Exception: pass
    nodes(gr,"Service",[{"name":n,"tier":t} for n,t in SERVICES])
    nodes(gr,"Team",[{"name":t} for t in TEAMS]); nodes(gr,"Person",[{"name":p} for p in PEOPLE])
    nodes(gr,"Deploy",[{"name":d[0],"ts":d[3],"summary":d[4]} for d in DEPLOYS])
    nodes(gr,"Incident",[{"name":i[0],"sev":i[1],"date":i[2],"title":i[3]} for i in INCIDENTS])
    nodes(gr,"Runbook",[{"name":r} for r in RUNBOOKS])
    nodes(gr,"Document",[{"name":n,"url":u} for n,u in DOCS])
    nodes(gr,"Decision",[{"name":d[0],"title":d[1],"rationale":d[2],"date":d[6]} for d in DECISIONS])
    edges(gr,"Service","DEPENDS_ON","Service",DEPENDS)
    edges(gr,"Team","OWNS","Service",[(t,s) for t,ss in TEAMS.items() for s in ss])
    edges(gr,"Person","MEMBER_OF","Team",PEOPLE.items())
    edges(gr,"Deploy","DEPLOYED_TO","Service",[(d[0],d[1]) for d in DEPLOYS])
    edges(gr,"Deploy","AUTHORED_BY","Person",[(d[0],d[2]) for d in DEPLOYS])
    edges(gr,"Incident","CAUSED_BY","Deploy",[(i[0],i[4]) for i in INCIDENTS])
    edges(gr,"Incident","AFFECTED","Service",[(i[0],s) for i in INCIDENTS for s in i[5]])
    edges(gr,"Person","RESOLVED","Incident",[(p,i[0]) for i in INCIDENTS for p in i[6]])
    edges(gr,"Incident","FOLLOWED","Runbook",[(i[0],i[7]) for i in INCIDENTS])
    edges(gr,"Runbook","DOCUMENTS","Service",RUNBOOKS.items())
    edges(gr,"Decision","ABOUT","Service",[(d[0],d[3]) for d in DECISIONS])
    edges(gr,"Decision","MADE_BY","Person",[(d[0],d[4]) for d in DECISIONS])
    edges(gr,"Decision","SOURCED_FROM","Document",[(d[0],d[5]) for d in DECISIONS])
    edges(gr,"Decision","SUPERSEDES","Decision",[("DEC-5","DEC-4")])
    return {"tenant": tenant, "graph": name}
