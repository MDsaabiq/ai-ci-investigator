from app.github.client import GitHubClient
from app.models.evidence import InitialEvidence, ChangedFile


class EvidenceCollector:
    def __init__(self, github_client: GitHubClient):
        self.github = github_client

    def collect(
        self,
        repository: str,
        run_id: int,
    ) -> InitialEvidence:

        run = self.github.get_workflow_run(repository, run_id)
        jobs = self.github.get_jobs(repository, run_id)
        logs = self.github.get_workflow_logs(repository, run_id)

        # Find failed job and step
        failed_job = None
        failed_step = None

        for job in jobs:
            if job.conclusion == "failure":
                failed_job = job.name

                for step in job.steps:
                    if step.conclusion == "failure":
                        failed_step = step.name
                        break

                break

        commit = self.github.get_commit(
            repository,
            run.head_sha,
        )

        changed_files = []

        for file in commit.files:
            changed_files.append(
                ChangedFile(
                    filename=file.filename,
                    status=file.status,
                    additions=file.additions,
                    deletions=file.deletions,
                    patch=file.patch,
                )
            )

        # Combine and extract only relevant failure logs to stay well within token limits
        relevant_sections = []
        for filename, content in logs.items():
            # Skip noise/setup files
            if filename.startswith("0_") or "system" in filename.lower() or "Post " in filename or "Set up" in filename:
                continue

            lines = content.strip().splitlines()
            is_failing = bool(failed_step and failed_step.lower() in filename.lower())
            has_error = any(kw in content.lower() for kw in ["error", "fail", "fatal", "traceback", "exception"])

            if is_failing or has_error:
                tail_lines = lines[-60:] if len(lines) > 60 else lines
                relevant_sections.append(f"--- {filename} ---\n" + "\n".join(tail_lines))

        if not relevant_sections:
            for filename, content in list(logs.items())[:3]:
                lines = content.strip().splitlines()
                relevant_sections.append(f"--- {filename} ---\n" + "\n".join(lines[-30:]))

        combined_logs = "\n\n".join(relevant_sections)
        if len(combined_logs) > 4000:
            combined_logs = combined_logs[-4000:]

        return InitialEvidence(
            repository=repository,
            run_id=run_id,
            failed_job=failed_job,
            failed_step=failed_step,
            logs=combined_logs,
            commit_sha=run.head_sha,
            commit_message=(
                commit.commit.message
                if commit.commit
                else None
            ),
            changed_files=changed_files,
        )