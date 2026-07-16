import asyncio
import sys
import logging
from dr3.storage.database import Database
from dr3.search.sites_db import SitesDatabase
from dr3.investigation.orchestrator import InvestigationOrchestrator
from dr3.core.enums import QueryType
from dr3.config import Config

logging.basicConfig(level=logging.WARNING)

async def run_audit():
    query = "zuck"
    
    db = Database("test.db")
    sites_db = SitesDatabase().load_from_file(str(Config.SITES_FILE))
    orchestrator = InvestigationOrchestrator(db, sites_db)
    
    entities = []
    relationships = []
    
    with open("audit_trace.txt", "w", encoding="utf-8") as f:
        f.write("\n--- STAGE 1: User Query & Setup ---\n")
        f.write(f"Input Query: {query}\n")
        f.write("Database & Sites DB Initialized.\n")
        f.write("\n--- STAGE 2: Social Discovery Engine & OSINT Providers ---\n")
        f.write("Starting Pipeline...\n")
        
        async def progress_cb(msg):
            msg_type = msg.get("type", "progress")
            if msg_type == "progress":
                f.write(f"[PROGRESS] {msg.get('phase')}: {msg.get('message')}\n")
            elif msg_type == "node_added":
                node = msg.get("node", {})
                entities.append(node)
                f.write(f"[NODE] {node.get('label')} ({node.get('platform')})\n")
            elif msg_type == "edge_added":
                edge = msg.get("edge", {})
                relationships.append(edge)
                f.write(f"[EDGE] {edge.get('source')} -> {edge.get('target')} ({edge.get('type')})\n")
            elif "node" in msg:
                node = msg.get("node", {})
                entities.append(node)
                f.write(f"[NODE] {node.get('label')} ({node.get('platform')})\n")
            elif "edge" in msg:
                edge = msg.get("edge", {})
                relationships.append(edge)
                f.write(f"[EDGE] {edge.get('source')} -> {edge.get('target')} ({edge.get('type')})\n")
            f.flush()

        inv = await orchestrator.run(query=query, query_type=QueryType.USERNAME, max_depth=1, max_nodes=5, progress_callback=progress_cb)

        f.write("\n--- PIPELINE COMPLETE ---\n")
        f.write(f"Entities in Graph: {len(inv.nodes)}\n")
        f.write(f"Relationships in Graph: {len(inv.edges)}\n")

        ig_node = next((n for n in inv.nodes.values() if n.platform.lower() == "instagram"), None)

        if ig_node:
            f.write("\n[VERIFICATION] ✓ Instagram account appears.\n")
            f.write("[VERIFICATION] ✓ Entity is created.\n")
            db_inv = db.get_investigation(inv.id)
            if db_inv:
                f.write("[VERIFICATION] ✓ Database contains it.\n")
            else:
                f.write("[VERIFICATION] ❌ Database DOES NOT contain the investigation.\n")
                
            if len(inv.edges) > 0:
                f.write("[VERIFICATION] ✓ Relationship engine generates nodes.\n")
            else:
                f.write("[VERIFICATION] ❌ Relationship engine generated ZERO edges.\n")
        else:
            f.write("\n[VERIFICATION] ❌ Instagram account did NOT appear in final graph.\n")

if __name__ == "__main__":
    asyncio.run(run_audit())
