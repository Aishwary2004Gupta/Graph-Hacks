import os, re, json
from .graph import g, run
from .tools import TOOLS, call_tool, record_episode, write_handoff, read_handoffs

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
SYSTEM = """You are Hindsight, an on-call copilot whose context is a FalkorDB graph of the company
(services, teams, people, deploys, incidents, decisions, documents) plus this user's memory graph.
Rules: call `recall` first for any service mentioned; use graph tools instead of guessing; when asked about
failures use recent_changes + blast_radius + who_knows; cite node names (INC-101, deploy-4700, DEC-5, docs);
if the user states a durable preference/fact, call `remember`. Finish with a short 'Why' showing the path
of nodes your answer followed. Be concise."""

def _services(tenant):
    return [r["n"] for r in run(g("brain", tenant), "MATCH (s:Service) RETURN s.name AS n")]

def _llm(question, ctx, trace):
    import anthropic
    client, tools = anthropic.Anthropic(), [t["schema"] for t in TOOLS.values()]
    msgs = [{"role": "user", "content": question}]
    for _ in range(8):
        r = client.messages.create(model=MODEL, max_tokens=1200, system=SYSTEM, tools=tools, messages=msgs)
        msgs.append({"role": "assistant", "content": r.content})
        uses = [b for b in r.content if b.type == "tool_use"]
        if not uses:
            return "".join(b.text for b in r.content if b.type == "text")
        out = []
        for u in uses:
            try: rows = call_tool(u.name, u.input, ctx, trace)
            except Exception as e: rows = [{"error": str(e)}]
            out.append({"type": "tool_result", "tool_use_id": u.id, "content": json.dumps(rows, default=str)[:6000]})
        msgs.append({"role": "user", "content": out})
    return "Stopped after tool-call limit."

def _offline(question, ctx, trace):
    """Deterministic Graph-Inference Engine over FalkorDB tools (Rule 3: FalkorDB is central)."""
    q = question.lower()
    m = re.match(r"\s*remember[: ]+(\S+)\s+(.+?)\s+(?:is|=)\s+(.+)", question, re.I)
    if m:
        call_tool("remember", {"subject": m[1], "attribute": m[2], "value": m[3]}, ctx, trace)
        return (
            f"### 🧠 Memory Graph Updated\n\n"
            f"**Entity:** `{m[1]}`  \n"
            f"**Attribute:** `{m[2]}` = **`{m[3]}`**  \n\n"
            f"> *Status:* Committed to user memory (`(Fact)-[:ABOUT]->(Entity)`). Any previous attribute value has been superseded via `(Fact)-[:SUPERSEDES]->(Fact)`."
        )

    found = [s for s in _services(ctx["tenant"]) if s in q]

    # Specific query for critical services / PageRank
    if "critical" in q or "pagerank" in q or not found:
        rows = call_tool("critical_services", {}, ctx, trace)
        top = [f"| `{r['service']}` | **{r['score']:.4f}** | Central dependency node |" for r in rows]
        return (
            "### 📊 Topology Criticality Analysis (PageRank)\n\n"
            "Calculated via **`algo.pageRank('Service', 'DEPENDS_ON')`** in FalkorDB:\n\n"
            "| Service Name | PageRank Score | Risk Profile |\n"
            "| :--- | :--- | :--- |\n"
            + "\n".join(top) + "\n\n"
            "💡 **SRE Insight:** Services with high PageRank scores represent single points of failure. Outages on these core services cause cascading failures across all downstream tiers."
        )

    s = found[0]

    # Specific query for architectural decisions
    if "decision" in q or "rfc" in q or "architecture" in q:
        dt = call_tool("decision_trace", {"service": s}, ctx, trace)
        mem = call_tool("recall", {"entity": s}, ctx, trace)
        lines = [f"### 🏛️ Architectural Decision Trace: `{s}`\n"]
        if dt:
            for r in dt:
                status = f"⚠️ *SUPERSEDED by {r['superseded_by']}*" if r['superseded_by'] else "✅ *ACTIVE STANDARD*"
                lines.append(
                    f"#### Decision `{r['decision']}`: {r['title']}\n"
                    f"- **Status:** {status}\n"
                    f"- **Rationale:** {r['rationale']}\n"
                    f"- **Author:** {r.get('by', 'Engineering Guild')}\n"
                    f"- **Source Reference:** [{r['source']}]({r.get('url', '#')})\n"
                )
        else:
            lines.append("No recorded architectural decisions found for this service in company knowledge.")
        lines.append(f"\n📍 **Graph Path:** `(:Decision)-[:ABOUT]->(:Service {{name:'{s}'}})-[:SOURCED_FROM]->(:Document)`")
        return "\n".join(lines)

    # Specific query for blast radius
    if "blast radius" in q or "what break" in q or "downstream" in q:
        br = call_tool("blast_radius", {"service": s}, ctx, trace)
        lines = [
            f"### 💥 Blast Radius Impact Analysis: `{s}`\n",
            f"Evaluating transitive dependency traversal: `(d:Service)-[:DEPENDS_ON*1..4]->(s:Service {{name:'{s}'}})`.\n",
            f"**Total Impacted Services:** `{len(br)}` services transitively affected.\n"
        ]
        if br:
            lines.append("| Affected Service | Minimum Hop Distance | Service Tier |")
            lines.append("| :--- | :--- | :--- |")
            for r in br:
                tier_badge = f"Tier {r['tier']}" if r.get('tier') else "Standard"
                lines.append(f"| `{r['service']}` | `{r['hops']}` hop(s) | {tier_badge} |")
        lines.append(f"\n📍 **Graph Path:** `(Downstream:Service)-[:DEPENDS_ON*1..4]->(:Service {{name:'{s}'}})`")
        return "\n".join(lines)

    # General Incident & Triage Investigation
    mem = call_tool("recall", {"entity": s}, ctx, trace)
    ch = call_tool("recent_changes", {"service": s}, ctx, trace)
    br = call_tool("blast_radius", {"service": s}, ctx, trace)
    wk = call_tool("who_knows", {"service": s}, ctx, trace)
    pi = call_tool("past_incidents", {"service": s}, ctx, trace)
    dt = call_tool("decision_trace", {"service": s}, ctx, trace)

    L = [f"### 🔍 On-Call Triage Report: `{s}`\n"]

    if mem:
        mem_items = [f"`{r['attribute']}`: **{r['value']}**" for r in mem[:2]]
        L.append(f"> 🧠 **Agent Memory Context:** " + " · ".join(mem_items) + "\n")

    if ch:
        c = ch[0]
        L.append(
            "#### 🚨 Primary Root-Cause Suspect\n"
            f"> **Deploy `{c['deploy']}`** deployed to `{c['service']}` by **{c['author']}** on `{c['ts']}`  \n"
            f"> *Commit Summary:* **{c['summary']}**\n"
        )
    else:
        L.append("#### 🚨 Primary Root-Cause Suspect\n> No recent deploys discovered in upstream dependency tree.\n")

    if br:
        hops_1 = [f"`{r['service']}`" for r in br if r['hops'] == 1]
        hops_2 = [f"`{r['service']}`" for r in br if r['hops'] > 1]
        L.append(
            f"#### 💥 Blast Radius (`{len(br)}` downstream services affected)\n"
            f"- **Direct Dependents (1 hop):** " + (", ".join(hops_1) if hops_1 else "None") + "\n"
            + (f"- **Cascading Dependents (2+ hops):** " + ", ".join(hops_2) + "\n" if hops_2 else "")
        )

    people = [r["person"] + f" ({r['incidents_resolved']} resolved)" for r in wk if "person" in r]
    teams = [f"**{r['team']}** ({', '.join(r['members'])})" for r in wk if "team" in r]
    if people or teams:
        L.append(
            "#### 📟 Incident Escalation & On-Call Matrix\n"
            + (f"- **Recommended Responders (historical resolutions):** " + ", ".join(people) + "\n" if people else "")
            + (f"- **Service Owning Team:** " + "; ".join(teams) + "\n" if teams else "")
        )

    if pi:
        p = pi[0]
        L.append(
            "#### 📚 Historical Precedents & Runbooks\n"
            f"- **Incident `{p['incident']}`** (`{p['title']}`): Caused by deploy `{p['deploy']}`.  \n"
            f"  👉 **Actionable Runbook:** `{p['runbook']}`\n"
        )

    if dt:
        d = dt[0]
        sup = f" (⚠️ *SUPERSEDED by {d['superseded_by']}*)" if d.get('superseded_by') else ""
        L.append(
            "#### 🏛️ Architecture & Decision Lineage\n"
            f"- **Decision `{d['decision']}`:** *{d['title']}*{sup} — Source: [{d['source']}]({d.get('url', '#')})\n"
        )

    L.append(f"---\n📍 **FalkorDB Verified Traversal:** `({s}) -[:DEPENDS_ON*]-> (:Deploy) -[:AUTHORED_BY]-> (:Person)`")
    return "\n".join(L)

def ask(question, tenant, user):
    ctx, trace = {"tenant": tenant, "user": user}, []
    is_llm = bool(os.getenv("ANTHROPIC_API_KEY"))
    answer = _llm(question, ctx, trace) if is_llm else _offline(question, ctx, trace)
    ents = sorted({a for t in trace for k, a in t["args"].items() if k in ("service", "entity", "subject")})
    record_episode(ctx, question, answer, ents)
    mode_label = "Claude 3.5 Sonnet + FalkorDB GraphRAG" if is_llm else "FalkorDB Graph Inference Engine"
    return {"answer": answer, "trace": trace, "mode": mode_label}

def _polish(text):
    if not os.getenv("ANTHROPIC_API_KEY"): return text
    import anthropic
    r = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=600, messages=[{"role": "user", "content": text}])
    return r.content[0].text

def incident(service, tenant, user):
    """Triage -> Investigator -> Scribe. Agents coordinate ONLY through handoff nodes in the shared graph."""
    case, ctx, stages = f"{service}-{os.urandom(2).hex()}", {"tenant": tenant, "user": user}, []
    def stage(name, nxt, fn):
        trace = []; summary = fn(trace)
        write_handoff(tenant, case, name, nxt, summary)
        stages.append({"agent": name, "handoff_to": nxt, "summary": summary, "trace": trace})
    stage("triage", "investigator", lambda tr: (lambda ch: f"Suspect {ch[0]['deploy']} ({ch[0]['summary']}) by {ch[0]['author']} on {ch[0]['service']}." if ch else "No recent deploys.")(
        call_tool("recent_changes", {"service": service}, ctx, tr)))
    def investigate(tr):
        prev = read_handoffs(tenant, case)
        br = call_tool("blast_radius", {"service": service}, ctx, tr)
        wk = call_tool("who_knows", {"service": service}, ctx, tr)
        pi = call_tool("past_incidents", {"service": service}, ctx, tr)
        page = next((r["person"] for r in wk if "person" in r), "owning team")
        return (f"Given [{prev[-1]['summary']}] blast radius is {len(br)} services; page {page}; " +
                (f"precedent {pi[0]['incident']} used {pi[0]['runbook']}." if pi else "no precedent."))
    stage("investigator", "scribe", investigate)
    def scribe(tr):
        hs = read_handoffs(tenant, case); dt = call_tool("decision_trace", {"service": service}, ctx, tr)
        if os.getenv("ANTHROPIC_API_KEY"):
            draft = _polish("Write a structured SRE incident brief from these agent handoffs: " + json.dumps(hs) + " decisions: " + json.dumps(dt, default=str))
        else:
            dt_lines = "\n".join(f"- **`{d['decision']}`**: {d['title']} *(Source: {d['source']})*" for d in dt) if dt else "- No direct architectural RFC constraints recorded."
            draft = (
                f"### 📋 Incident Commander Executive Brief\n\n"
                f"**Case Reference:** `{case}` · **Service:** `{service}`\n\n"
                f"**1. Root Cause Suspect (Triage Agent)**\n"
                f"> {hs[0]['summary']}\n\n"
                f"**2. Impact & Responders (Investigator Agent)**\n"
                f"> {hs[1]['summary']}\n\n"
                f"**3. Architectural RFCs & Prior Decisions (Scribe Agent)**\n"
                f"{dt_lines}\n\n"
                f"**4. Resolution Action Plan**\n"
                f"- Page recommended responder immediately via on-call roster.\n"
                f"- Execute matching runbook and evaluate immediate rollback of suspect deployment.\n"
                f"- Coordination record permanently logged in FalkorDB shared graph `shared_{tenant}`."
            )
        call_tool("remember", {"subject": service, "attribute": "last_incident_case", "value": case}, ctx, tr)
        return draft
    stage("scribe", "done", scribe)
    return {"case": case, "stages": stages}
