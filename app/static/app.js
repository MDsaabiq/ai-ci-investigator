let currentThreadId = null;

const form = document.getElementById("investigate-form");
const submitBtn = document.getElementById("submit-btn");
const btnText = document.getElementById("btn-text");
const btnSpinner = document.getElementById("btn-spinner");

const progressCard = document.getElementById("progress-card");
const statusBadge = document.getElementById("status-badge");
const statusDetail = document.getElementById("status-detail");

const rcaCard = document.getElementById("rca-card");
const rcaHypothesis = document.getElementById("rca-hypothesis");
const rcaEvidence = document.getElementById("rca-evidence");
const rcaFiles = document.getElementById("rca-files");
const ragContainer = document.getElementById("rag-container");
const ragContent = document.getElementById("rag-content");

const fixCard = document.getElementById("fix-card");
const fixExplanation = document.getElementById("fix-explanation");
const changesContainer = document.getElementById("changes-container");
const approveBtn = document.getElementById("approve-btn");
const rejectBtn = document.getElementById("reject-btn");

const resultCard = document.getElementById("result-card");
const resultBranch = document.getElementById("result-branch");
const resultPrLink = document.getElementById("result-pr-link");

// Steps in order
const STEPS = [
    "step-collect_evidence",
    "step-investigate",
    "step-final_rca",
    "step-retrieve_rag",
    "step-generate_fix"
];

function resetTimeline() {
    STEPS.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.className = "timeline-step";
        }
    });
}

function updateTimelineStep(activeStepName) {
    let activeId = `step-${activeStepName}`;
    if (activeStepName === "fetch_file" || activeStepName === "search_repo") {
        activeId = "step-investigate";
    }

    const activeIndex = STEPS.indexOf(activeId);
    if (activeIndex === -1) return;

    STEPS.forEach((id, idx) => {
        const el = document.getElementById(id);
        if (!el) return;

        if (idx < activeIndex) {
            el.className = "timeline-step done";
        } else if (idx === activeIndex) {
            el.className = "timeline-step active";
        } else {
            el.className = "timeline-step";
        }
    });
}

function completeTimeline() {
    STEPS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.className = "timeline-step done";
    });
}

// Handle Form Submission with Real-Time NDJSON Streaming
form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const repository = document.getElementById("repository").value.trim();
    const run_id = parseInt(document.getElementById("run_id").value);

    // Reset UI state
    rcaCard.classList.add("hidden");
    fixCard.classList.add("hidden");
    resultCard.classList.add("hidden");
    progressCard.classList.remove("hidden");
    resetTimeline();

    btnText.textContent = "Investigating...";
    btnSpinner.classList.remove("hidden");
    submitBtn.disabled = true;

    statusBadge.textContent = "Connecting...";
    statusDetail.textContent = `Initializing CI failure investigation for run #${run_id}...`;

    try {
        const response = await fetch("/api/investigate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                repository: repository,
                workflow_run_id: run_id,
            }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to start investigation");
        }

        // Stream reader for live updates
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep partial line

            for (const line of lines) {
                if (!line.trim()) continue;
                const data = JSON.parse(line);

                if (data.error) {
                    throw new Error(data.error);
                }

                handleStreamEvent(data);
            }
        }

    } catch (err) {
        statusBadge.textContent = "Error";
        statusDetail.textContent = err.message;
    } finally {
        btnText.textContent = "Investigate Failure";
        btnSpinner.classList.add("hidden");
        submitBtn.disabled = false;
    }
});

function handleStreamEvent(data) {
    if (data.thread_id) {
        currentThreadId = data.thread_id;
    }

    if (data.status) {
        statusBadge.textContent = data.status;
    }
    if (data.detail) {
        statusDetail.textContent = data.detail;
    }

    if (data.step) {
        if (data.step === "complete") {
            completeTimeline();
        } else {
            updateTimelineStep(data.step);
        }
    }

    // Render RCA live if available
    if (data.rca) {
        rcaHypothesis.textContent = data.rca.hypothesis || "No hypothesis found";

        rcaEvidence.innerHTML = "";
        (data.rca.evidence || []).forEach(ev => {
            const li = document.createElement("li");
            li.textContent = ev;
            rcaEvidence.appendChild(li);
        });

        rcaFiles.innerHTML = "";
        (data.rca.inspected_files || []).forEach(file => {
            const span = document.createElement("span");
            span.className = "tag";
            span.textContent = file;
            rcaFiles.appendChild(span);
        });

        rcaCard.classList.remove("hidden");
    }

    // Render RAG context live if available
    if (data.rag_context && data.rag_context.trim()) {
        ragContent.textContent = data.rag_context;
        ragContainer.classList.remove("hidden");
    }

    // Render Proposed Fix live if available
    if (data.proposed_fix) {
        fixExplanation.textContent = data.proposed_fix.explanation;

        changesContainer.innerHTML = "";
        (data.proposed_fix.changes || []).forEach(change => {
            const item = document.createElement("div");
            item.className = "change-item";
            item.innerHTML = `
                <div class="change-header">
                    <span class="action-badge action-${change.action}">${change.action.toUpperCase()}</span>
                    <span>${change.path}</span>
                </div>
                <pre class="code-block"><code>${change.content || "(empty file / deletion)"}</code></pre>
            `;
            changesContainer.appendChild(item);
        });

        fixCard.classList.remove("hidden");
    }
}

// Handle Human Approval
approveBtn.addEventListener("click", () => handleApproval(true));
rejectBtn.addEventListener("click", () => handleApproval(false));

async function handleApproval(approved) {
    if (!currentThreadId) return;

    approveBtn.disabled = true;
    rejectBtn.disabled = true;

    statusBadge.textContent = approved ? "Creating PR..." : "Rejecting...";
    statusDetail.textContent = approved ? "Committing patch and opening Pull Request on GitHub..." : "Fix rejected by user.";

    try {
        const response = await fetch("/api/approve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                thread_id: currentThreadId,
                approved: approved,
            }),
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Failed to process approval");
        }

        const data = await response.json();

        if (approved && data.pr_url) {
            resultBranch.textContent = data.branch_name;
            resultPrLink.href = data.pr_url;
            resultCard.classList.remove("hidden");
            statusBadge.textContent = "Completed";
            statusDetail.textContent = "Pull Request successfully created!";
        } else {
            statusBadge.textContent = "Cancelled";
            statusDetail.textContent = "Investigation closed without modifying GitHub.";
        }

    } catch (err) {
        statusBadge.textContent = "Error";
        statusDetail.textContent = err.message;
    } finally {
        approveBtn.disabled = false;
        rejectBtn.disabled = false;
    }
}
