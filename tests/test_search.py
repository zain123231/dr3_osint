import asyncio
import logging

from dr3.core.enums import QueryType
from dr3.investigation.orchestrator import InvestigationOrchestrator
from dr3.search.sites_db import SitesDatabase
from dr3.storage.database import Database
import dr3.config as config

logging.basicConfig(level=logging.INFO)

async def test_pipeline():
    print("--- 1. Initialize DB and Sites DB ---")
    db = Database(str(config.Config.DB_PATH))
    
    sites_db = SitesDatabase()
    sites_db.load_from_file(str(config.Config.SITES_FILE))
    print(f"Loaded {len(sites_db.enabled_sites)} sites.")

    print("--- 2. Initialize Orchestrator ---")
    orchestrator = InvestigationOrchestrator(db, sites_db)

    print("--- 3. Running Investigation for target: zuck ---")
    
    async def progress_callback(update):
        print(f"[PROGRESS] Phase: {update['phase']} | Progress: {update['progress']}% | Msg: {update['message']}")
        print(f"           Nodes: {update['discovered_nodes']} | Edges: {update['discovered_edges']}")

    try:
        inv = await orchestrator.run(
            query="zuck",
            query_type=QueryType.USERNAME,
            max_depth=2,
            max_nodes=10,
            progress_callback=progress_callback
        )
        
        print("\n--- 4. Final Output ---")
        print(f"Nodes count: {inv.node_count}")
        print(f"Edges count: {inv.edge_count}")
        print(f"Confirmed platforms count: {inv.confirmed_count}")
        
        if inv.identity_profile:
            print(f"Profile Primary Name: {inv.identity_profile.primary_name}")
            print(f"Overall Confidence: {inv.identity_profile.overall_confidence}")
        
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pipeline())
