from typing import List, Dict, Any

def generate_workflow_graph(
    tasks: List[Dict[str, Any]],
    decisions: List[Dict[str, Any]],
    conflicts: List[Dict[str, Any]],
    dependencies: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate an interactive React Flow DAG with nodes and edges.
    Calculates 2D coordinates (x, y) for layout.
    """
    nodes = []
    edges = []
    
    x_spacing = 320
    y_spacing = 140
    current_x = 50
    current_y = 60
    
    node_id_map = {} # label/title -> node_id
    
    # 1. Add Task nodes
    for i, t in enumerate(tasks):
        node_id = f"task_{t.get('id', i+1)}"
        node_id_map[t['title'].lower()] = node_id
        
        # Color coding & status badge
        status = t.get("status", "Pending")
        priority = t.get("priority", "Medium")
        
        nodes.append({
            "id": node_id,
            "type": "customWorkflowNode",
            "data": {
                "category": "task",
                "label": t["title"],
                "owner": t.get("owner", "Unassigned"),
                "deadline": t.get("deadline_text") or "None",
                "status": status,
                "priority": priority,
                "evidence_timestamp": t.get("evidence_timestamp", 0.0),
                "evidence_quote": t.get("evidence_quote", ""),
                "is_blocked": status == "Blocked"
            },
            "position": {"x": current_x, "y": current_y + (i % 2) * 80}
        })
        current_x += x_spacing

    # 2. Add Decision nodes
    for j, d in enumerate(decisions):
        d_id = f"decision_{d.get('id', j+1)}"
        node_id_map[d['decision'].lower()] = d_id
        
        nodes.append({
            "id": d_id,
            "type": "customWorkflowNode",
            "data": {
                "category": "decision",
                "label": d.get("topic") or d["decision"][:35],
                "detail": d["decision"],
                "status": d.get("status", "Final"),
                "evidence_timestamp": d.get("evidence_timestamp", 0.0),
                "evidence_quote": d.get("evidence_quote", "")
            },
            "position": {"x": 50 + j * 320, "y": current_y + 240}
        })

    # 3. Add Conflict nodes if any
    for k, c in enumerate(conflicts):
        c_id = f"conflict_{c.get('id', k+1)}"
        nodes.append({
            "id": c_id,
            "type": "customWorkflowNode",
            "data": {
                "category": "conflict",
                "label": f"Conflict: {c['topic']}",
                "detail": f"{c['statement_a']} vs {c['statement_b']}",
                "status": "Needs Confirmation",
                "evidence_timestamp": c.get("timestamp_b", 0.0),
                "evidence_quote": c["statement_b"]
            },
            "position": {"x": 200 + k * 340, "y": current_y + 400}
        })

    # 4. Generate Edges
    # A. Use detected dependencies first
    connected_sources = set()
    connected_targets = set()

    for dep in dependencies:
        source_label = dep["source_label"].lower()
        target_label = dep["target_label"].lower()
        
        # Match node ids
        source_id = None
        target_id = None
        
        for k_label, nid in node_id_map.items():
            if k_label in source_label or source_label in k_label:
                source_id = nid
            if k_label in target_label or target_label in k_label:
                target_id = nid
                
        # If not matched directly, connect between consecutive task nodes
        if not source_id and len(tasks) > 0:
            source_id = f"task_{tasks[0].get('id', 1)}"
        if not target_id and len(tasks) > 1:
            target_id = f"task_{tasks[1].get('id', 2)}"
            
        if source_id and target_id and source_id != target_id:
            edge_id = f"e_{source_id}_{target_id}"
            if not any(e["id"] == edge_id for e in edges):
                edges.append({
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "label": dep.get("relation_type", "blocks"),
                    "animated": True,
                    "style": {"stroke": "#f59e0b", "strokeWidth": 2}
                })
                connected_sources.add(source_id)
                connected_targets.add(target_id)

    # B. If tasks exist but no edges formed yet, create a logical pipeline edge between consecutive tasks
    task_nodes = [n for n in nodes if n["data"]["category"] == "task"]
    for idx in range(len(task_nodes) - 1):
        s_id = task_nodes[idx]["id"]
        t_id = task_nodes[idx + 1]["id"]
        e_id = f"e_{s_id}_{t_id}"
        if not any(e["id"] == e_id for e in edges):
            edges.append({
                "id": e_id,
                "source": s_id,
                "target": t_id,
                "label": "sequence",
                "animated": False,
                "style": {"stroke": "#6366f1", "strokeWidth": 2}
            })
            connected_sources.add(s_id)
            connected_targets.add(t_id)

    # C. Link last relevant task to decisions (e.g. Training -> Architecture Decision)
    decision_nodes = [n for n in nodes if n["data"]["category"] == "decision"]
    if task_nodes and decision_nodes:
        # Find the last task node (e.g. Training)
        last_task_id = task_nodes[-1]["id"]
        for d_node in decision_nodes:
            e_id = f"e_{last_task_id}_{d_node['id']}"
            if not any(e["id"] == e_id for e in edges):
                edges.append({
                    "id": e_id,
                    "source": last_task_id,
                    "target": d_node["id"],
                    "label": "requires decision",
                    "animated": True,
                    "style": {"stroke": "#8b5cf6", "strokeWidth": 2}
                })

    # D. Link decisions (or tasks) to conflict nodes (e.g. Architecture Decision -> Report Conflict)
    conflict_nodes = [n for n in nodes if n["data"]["category"] == "conflict"]
    if conflict_nodes:
        source_for_conflict = decision_nodes[-1]["id"] if decision_nodes else (task_nodes[-1]["id"] if task_nodes else None)
        if source_for_conflict:
            for c_node in conflict_nodes:
                e_id = f"e_{source_for_conflict}_{c_node['id']}"
                if not any(e["id"] == e_id for e in edges):
                    edges.append({
                        "id": e_id,
                        "source": source_for_conflict,
                        "target": c_node["id"],
                        "label": "schedule discrepancy",
                        "animated": True,
                        "style": {"stroke": "#f43f5e", "strokeWidth": 2, "strokeDasharray": "4 4"}
                    })

    return {
        "nodes": nodes,
        "edges": edges
    }

