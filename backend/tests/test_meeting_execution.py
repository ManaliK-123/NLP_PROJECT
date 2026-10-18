import pytest
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.models import Meeting, Project, Task, Decision, Conflict, Dependency, TranscriptSegment
from app.services.meeting_service import seed_demo_data_if_empty, process_meeting_pipeline
from app.nlp.task_detector import classify_utterance_type, detect_tasks
from app.nlp.deadline_detector import detect_deadline
from app.nlp.conflict_detector import detect_conflicts
from app.nlp.dependency_detector import detect_dependencies
from app.nlp.decision_detector import detect_decisions
from app.services.execution_radar import calculate_execution_radar
from app.services.qa_assistant import ask_meeting_assistant
from app.services.export_service import export_mom_csv, export_mom_pdf
from app.services.mom_generator import build_mom_document, generate_mom_markdown

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_nlp_utterance_classification():
    assert classify_utterance_type("Rahul will update the report.") == "task"
    assert classify_utterance_type("Rahul, complete dataset by Wednesday.") == "task"
    assert classify_utterance_type("Maybe Rahul can update the report.") == "suggestion"
    assert classify_utterance_type("Can Rahul update the report?") == "question"
    assert classify_utterance_type("Rahul updated the report.") == "completed"
    assert classify_utterance_type("The dataset has 10,000 samples.") == "discussion"

def test_deadline_detector():
    ref = datetime.datetime(2026, 10, 5, 12, 0)
    dl_info = detect_deadline("Rahul, complete dataset by Wednesday.", reference_date=ref)
    assert dl_info["deadline_status"] == "Exact"
    assert dl_info["deadline_normalized"] is not None

    dl_ambig = detect_deadline("We should finish this soon.", reference_date=ref)
    assert dl_ambig["deadline_status"] == "Ambiguous"

    dl_none = detect_deadline("This is a random comment.", reference_date=ref)
    assert dl_none["deadline_status"] == "Not specified"

def test_conflict_detector():
    segments = [
        {"start_time": 10.0, "speaker_label": "Rahul", "text": "Let's discuss that in Friday's meeting with the professor."},
        {"start_time": 15.0, "speaker_label": "Priya", "text": "Wait, actually, the report submission is Thursday, not Friday."}
    ]
    conflicts = detect_conflicts(segments)
    assert len(conflicts) >= 1
    assert "Friday" in conflicts[0]["statement_a"]
    assert "Thursday" in conflicts[0]["statement_b"]
    assert conflicts[0]["status"] == "Needs confirmation"

def test_dependency_detector():
    tasks = [
        {"id": 1, "title": "Complete dataset preprocessing", "evidence_quote": "Rahul, complete dataset by Wednesday.", "evidence_timestamp": 0.0},
        {"id": 2, "title": "Train baseline model", "evidence_quote": "After that, Priya will train the baseline model.", "evidence_timestamp": 3.8}
    ]
    segments = [
        {"start_time": 3.8, "speaker_label": "Rahul", "text": "Sure, I'll clean the labels. After that, Priya will train the baseline model."}
    ]
    deps = detect_dependencies(segments, tasks)
    assert len(deps) >= 1
    assert "dataset" in deps[0]["source_label"].lower()
    assert "model" in deps[0]["target_label"].lower()

def test_demo_seeding_and_execution_radar(test_db):
    demo_meeting = seed_demo_data_if_empty(test_db)
    assert demo_meeting is not None
    assert demo_meeting.title == "Sprint Planning & Architecture Sync #14"

    tasks = test_db.query(Task).filter(Task.meeting_id == demo_meeting.id).all()
    assert len(tasks) >= 3

    # Rahul task
    rahul_task = next((t for t in tasks if t.owner == "Rahul"), None)
    assert rahul_task is not None
    assert "dataset" in rahul_task.title.lower()

    # Priya task
    priya_task = next((t for t in tasks if t.owner == "Priya"), None)
    assert priya_task is not None
    assert "model" in priya_task.title.lower()

    # Ambiguity detection on unassigned task
    unassigned_task = next((t for t in tasks if t.owner == "Unassigned"), None)
    assert unassigned_task is not None
    assert unassigned_task.status == "Needs Clarification"

    # Execution radar check
    t_dicts = [t.__dict__ for t in tasks]
    d_dicts = [d.__dict__ for d in test_db.query(Decision).filter(Decision.meeting_id == demo_meeting.id).all()]
    c_dicts = [c.__dict__ for c in test_db.query(Conflict).filter(Conflict.meeting_id == demo_meeting.id).all()]
    radar = calculate_execution_radar(t_dicts, d_dicts, c_dicts, [])
    assert radar["health_status"] == "At Risk"
    assert len(radar["reasons"]) >= 1

def test_ask_the_meeting_grounded_qa(test_db):
    demo_meeting = seed_demo_data_if_empty(test_db)
    
    # 1. Ask about ownership
    res1 = ask_meeting_assistant(test_db, demo_meeting.id, "Who owns dataset preparation?")
    assert "Rahul" in res1["answer"]
    assert len(res1["evidence"]) > 0

    # 2. Ask about unresolved items
    res2 = ask_meeting_assistant(test_db, demo_meeting.id, "What is still unresolved?")
    assert len(res2["evidence"]) > 0

    # 3. Ask why At Risk
    res3 = ask_meeting_assistant(test_db, demo_meeting.id, "Why is the project marked At Risk?")
    assert "At Risk" in res3["answer"] or "conflict" in res3["answer"].lower()

def test_export_generation(test_db):
    demo_meeting = seed_demo_data_if_empty(test_db)
    mom = demo_meeting.mom_json
    assert mom is not None

    # CSV
    csv_str = export_mom_csv(mom)
    assert "Rahul" in csv_str
    assert "Priya" in csv_str

    # Markdown
    md_str = generate_mom_markdown(mom)
    assert "# Minutes of Meeting:" in md_str

    # PDF
    pdf_bytes = export_mom_pdf(mom)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

def test_required_demo_case_full_pipeline():
    """
    REQUIRED DEMO CASE VERIFICATION:
    Rahul: "Complete the dataset by Wednesday."
    Priya: "After Rahul finishes it, I will train the model."
    Rahul: "The architecture is still undecided."
    Priya: "Let's decide it in Friday's meeting."
    Rahul: "The report is due Thursday."
    Priya: "I thought it was Friday."
    """
    from app.nlp.extraction import extract_all_meeting_intelligence
    from app.workflow.generator import generate_workflow_graph

    segments = [
        {"start_time": 0.0, "end_time": 3.0, "speaker_label": "Rahul", "text": "Complete the dataset by Wednesday."},
        {"start_time": 3.5, "end_time": 7.0, "speaker_label": "Priya", "text": "After Rahul finishes it, I will train the model."},
        {"start_time": 7.5, "end_time": 10.5, "speaker_label": "Rahul", "text": "The architecture is still undecided."},
        {"start_time": 11.0, "end_time": 14.0, "speaker_label": "Priya", "text": "Let's decide it in Friday's meeting."},
        {"start_time": 14.5, "end_time": 17.5, "speaker_label": "Rahul", "text": "The report is due Thursday."},
        {"start_time": 18.0, "end_time": 21.0, "speaker_label": "Priya", "text": "I thought it was Friday."}
    ]

    ref = datetime.datetime(2026, 10, 5, 10, 0)
    res = extract_all_meeting_intelligence(segments, reference_date=ref)

    # 1. Rahul -> Dataset -> Wednesday
    rahul_task = next((t for t in res["tasks"] if t["owner"] == "Rahul"), None)
    assert rahul_task is not None, "Rahul task must be detected"
    assert "dataset" in rahul_task["title"].lower()
    assert rahul_task["deadline_text"] == "Wednesday"
    assert rahul_task["evidence_timestamp"] == 0.0

    # 2. Priya -> Model Training -> blocked by Dataset
    priya_task = next((t for t in res["tasks"] if t["owner"] == "Priya"), None)
    assert priya_task is not None, "Priya task must be detected"
    assert "train" in priya_task["title"].lower() or "model" in priya_task["title"].lower()
    assert priya_task["status"] == "Blocked"
    assert priya_task["evidence_timestamp"] == 3.5

    # 3. Architecture -> Unresolved / Undecided
    arch_dec = next((d for d in res["decisions"] if "architecture" in d["topic"].lower()), None)
    assert arch_dec is not None, "Architecture decision must be detected"
    assert arch_dec["status"] == "Undecided"
    assert arch_dec["evidence_timestamp"] == 7.5

    # 4. Report deadline -> Conflict: Thursday vs Friday
    assert len(res["conflicts"]) >= 1, "Conflict must be detected between Thursday and Friday"
    conf = res["conflicts"][0]
    assert "Thursday" in conf["statement_a"] or "Thursday" in conf["statement_b"]
    assert "Friday" in conf["statement_a"] or "Friday" in conf["statement_b"]
    assert conf["status"] == "Needs confirmation"
    assert conf["timestamp_a"] == 14.5
    assert conf["timestamp_b"] == 18.0

    # 5. Dependency -> Dataset blocks Model Training
    assert len(res["dependencies"]) >= 1
    dep = res["dependencies"][0]
    assert "dataset" in dep["source_label"].lower()
    assert "model" in dep["target_label"].lower() or "train" in dep["target_label"].lower()
    assert dep["relation_type"] == "blocks"

    # 6. Workflow -> Dataset -> Training -> Architecture Decision -> Report
    wf = generate_workflow_graph(res["tasks"], res["decisions"], res["conflicts"], res["dependencies"])
    node_categories = [n["data"]["category"] for n in wf["nodes"]]
    assert "task" in node_categories
    assert "decision" in node_categories
    assert "conflict" in node_categories

    edge_sources = [e["source"] for e in wf["edges"]]
    edge_targets = [e["target"] for e in wf["edges"]]
    assert len(wf["edges"]) >= 3, "Workflow must connect tasks, decisions, and conflicts"

    # 7. Execution Health -> At Risk
    radar = calculate_execution_radar(res["tasks"], res["decisions"], res["conflicts"], res["dependencies"])
    assert radar["health_status"] == "At Risk"
    assert any("conflict" in r.lower() for r in radar["reasons"])
    assert any("undecided" in r.lower() for r in radar["reasons"])
    assert any("blocked" in r.lower() for r in radar["reasons"])

def test_ambiguity_handling_preserves_uncertainty():
    """Verify that vague assignments and deadlines preserve uncertainty without hallucinating."""
    from app.nlp.task_detector import detect_tasks
    from app.nlp.ambiguity_detector import analyze_ambiguity

    segments = [
        {"start_time": 5.0, "speaker_label": "Speaker 1", "text": "Someone should look into the database performance soon."}
    ]
    raw = detect_tasks(segments)
    tasks = analyze_ambiguity(raw)
    assert len(tasks) == 1
    t = tasks[0]
    assert t["owner"] == "Unassigned"
    assert t["status"] == "Needs Clarification"
    assert t["deadline_status"] == "Ambiguous"
    assert len(t["ambiguities"]) >= 2
    types = [a["type"] for a in t["ambiguities"]]
    assert "Unassigned Owner" in types
    assert "Vague Deadline" in types

def test_cross_meeting_memory_and_decision_drift(test_db):
    """Verify cross-meeting memory, audit history, and decision drift."""
    from app.services.project_memory import get_project_memory_intelligence
    demo_meeting = seed_demo_data_if_empty(test_db)
    mem = get_project_memory_intelligence(test_db, demo_meeting.project_id)
    assert mem["total_meetings"] >= 2
    assert len(mem["decision_drifts"]) >= 1
    drift = mem["decision_drifts"][0]
    assert "Dataset" in drift["topic"]
    assert drift["previous_decision"] is not None
    assert drift["new_decision"] is not None
    assert len(mem["task_timeline"]) >= 3

