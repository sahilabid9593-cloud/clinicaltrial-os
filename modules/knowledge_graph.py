import networkx as nx
import sqlite3
import json

def build_graph():
    print("Building knowledge graph...")
    G = nx.DiGraph()
    
    conn = sqlite3.connect("database/trials.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nct_id, title, sponsor, phase, disease, status 
        FROM trials
    """)
    rows = cursor.fetchall()
    conn.close()
    
    for nct_id, title, sponsor, phase, disease, status in rows:
        # Add trial node
        G.add_node(nct_id, type="trial", 
                   label=title[:40] if title else "", 
                   status=status or "")
        
        # Connect sponsor to trial
        if sponsor:
            G.add_node(sponsor, type="sponsor")
            G.add_edge(sponsor, nct_id, relation="sponsors")
        
        # Connect trial to disease
        if disease:
            G.add_node(disease, type="disease")
            G.add_edge(nct_id, disease, relation="studies")
        
        # Connect trial to phase
        if phase:
            G.add_node(phase, type="phase")
            G.add_edge(nct_id, phase, relation="in_phase")

    print(f"Graph built successfully:")
    print(f"  Total nodes: {G.number_of_nodes()}")
    print(f"  Total edges: {G.number_of_edges()}")
    return G

def find_sponsor_trials(sponsor_name, G):
    print(f"\nTrials by sponsor containing: {sponsor_name}")
    results = []
    for node in G.nodes():
        if sponsor_name.lower() in str(node).lower():
            for trial in G.successors(node):
                if G.nodes[trial].get("type") == "trial":
                    results.append({
                        "nct_id": trial,
                        "title": G.nodes[trial].get("label", ""),
                        "status": G.nodes[trial].get("status", "")
                    })
    for r in results[:5]:
        print(f"  {r['nct_id']} - {r['title']} ({r['status']})")
    return results

def get_graph_stats(G):
    sponsors = [n for n,d in G.nodes(data=True) if d.get("type")=="sponsor"]
    trials = [n for n,d in G.nodes(data=True) if d.get("type")=="trial"]
    diseases = [n for n,d in G.nodes(data=True) if d.get("type")=="disease"]
    
    print(f"\n--- GRAPH STATISTICS ---")
    print(f"  Trials:   {len(trials)}")
    print(f"  Sponsors: {len(sponsors)}")
    print(f"  Diseases: {len(diseases)}")
    print(f"  Total connections: {G.number_of_edges()}")
    return {"trials": len(trials), "sponsors": len(sponsors), "diseases": len(diseases)}

if __name__ == "__main__":
    G = build_graph()
    get_graph_stats(G)
    find_sponsor_trials("novo", G)