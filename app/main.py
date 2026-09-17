import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from app.models.request import InvestigationRequest, ApprovalRequest
from app.graph.graph import investigation_graph

load_dotenv()

app = FastAPI(
    title="AI CI/CD Failure Investigator",
    description="Autonomous CI failure diagnosis and remediation",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def get_index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/investigate")
def investigate(req: InvestigationRequest):
    thread_id = f"{req.repository.replace('/', '-')}-{req.workflow_run_id}"

    initial_input = {
        "repository": req.repository,
        "run_id": req.workflow_run_id,
        "additional_evidence": {},
        "iteration_count": 0,
        "max_iterations": 2,
    }

    def generate_events():
        config = {"configurable": {"thread_id": thread_id}}
        final_state = {}

        try:
            # Emit starting event
            yield json.dumps({
                "step": "collect_evidence",
                "status": "Collecting Evidence",
                "detail": f"Fetching GitHub Actions logs and commit diff for run #{req.workflow_run_id}...",
                "thread_id": thread_id,
            }) + "\n"

            # Stream LangGraph node updates
            for chunk in investigation_graph.stream(initial_input, config=config, stream_mode="updates"):
                for node_name, node_output in chunk.items():
                    final_state.update(node_output)

                    detail = ""
                    status = node_output.get("status", node_name)
                    if node_name == "collect_evidence":
                        status = "Evidence Collected"
                        detail = "Workflow run logs and commit metadata successfully gathered."
                    elif node_name == "investigate":
                        status = "Investigating Failure"
                        detail = f"AI multi-turn analysis iteration #{node_output.get('iteration_count', 1)}..."
                    elif node_name == "fetch_file":
                        status = "Inspecting Files"
                        files = list((node_output.get("additional_evidence") or {}).keys())
                        detail = f"Fetched repository file: {files[-1] if files else 'code'}"
                    elif node_name == "search_repo":
                        status = "Searching Repository"
                        detail = "Queried repository symbols."
                    elif node_name == "final_rca":
                        status = "Root Cause Diagnosed"
                        detail = "Finalized Root Cause Analysis (RCA)."
                    elif node_name == "retrieve_rag":
                        status = "Azure AI Search (RAG)"
                        detail = "Queried Azure AI Search for matching historical remediations."
                    elif node_name == "generate_fix":
                        status = "Patch Generated"
                        detail = "Synthesized minimal, surgical patch to resolve the failure."

                    payload = {
                        "step": node_name,
                        "status": status,
                        "detail": detail,
                        "thread_id": thread_id,
                    }
                    if "final_rca" in node_output:
                        payload["rca"] = node_output["final_rca"]
                    if "rag_context" in node_output:
                        payload["rag_context"] = node_output["rag_context"]
                    if "proposed_fix" in node_output and node_output["proposed_fix"]:
                        payload["proposed_fix"] = node_output["proposed_fix"].model_dump()

                    yield json.dumps(payload) + "\n"

            # Final complete event
            complete_payload = {
                "step": "complete",
                "status": "Awaiting Approval",
                "detail": "Investigation complete. Review the diagnosed RCA and proposed fix below.",
                "thread_id": thread_id,
                "rca": final_state.get("final_rca"),
                "rag_context": final_state.get("rag_context"),
                "proposed_fix": (
                    final_state.get("proposed_fix").model_dump()
                    if final_state.get("proposed_fix")
                    else None
                ),
            }
            yield json.dumps(complete_payload) + "\n"

        except Exception as e:
            yield json.dumps({"step": "error", "error": str(e), "thread_id": thread_id}) + "\n"

    return StreamingResponse(generate_events(), media_type="application/x-ndjson")


@app.post("/api/approve")
def approve(req: ApprovalRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    if not req.approved:
        return {"status": "rejected", "message": "Fix was rejected by user"}

    try:
        # Resumes the paused graph from checkpoint to execute create_pr
        result = investigation_graph.invoke(None, config=config)

        return {
            "status": result.get("status"),
            "branch_name": result.get("branch_name"),
            "pr_url": result.get("pr_url"),
            "pr_number": result.get("pr_number"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
