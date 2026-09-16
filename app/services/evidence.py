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

        # Combine log files
        combined_logs = "\n\n".join(
            f"--- {filename} ---\n{content}"
            for filename, content in logs.items()
        )

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