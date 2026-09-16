import io
import zipfile
import requests
from github import Github
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun

class GitHubClient:
    def __init__(self, token: str):
        self.github = Github(token)
        self.token = token

    def get_repository(self, repository: str) -> Repository:
        return self.github.get_repo(repository)

    def get_workflow_run(
        self,
        repository: str,
        run_id: int,
    ) -> WorkflowRun:
        repo = self.get_repository(repository)
        return repo.get_workflow_run(run_id)

    def get_jobs(
        self,
        repository: str,
        run_id: int,
    ):
        run = self.get_workflow_run(repository, run_id)
        return list(run.jobs())

    def get_commit(
        self,
        repository: str,
        commit_sha: str,
    ):
        repo = self.get_repository(repository)
        return repo.get_commit(commit_sha)

    def get_file(
        self,
        repository: str,
        path: str,
        ref: str | None = None,
    ):
        repo = self.get_repository(repository)

        if ref:
            return repo.get_contents(path, ref=ref)

        return repo.get_contents(path)

    def get_diff(self, repository: str, commit_sha: str):
        repo = self.get_repository(repository)
        commit = repo.get_commit(commit_sha)

        diffs = []

        for file in commit.files:
            diffs.append({
                "filename": file.filename,
                "status": file.status,
                "patch": file.patch,
                "additions": file.additions,
                "deletions": file.deletions,
            })

        return diffs

    def get_workflow_logs(
        self,
        repository: str,
        run_id: int,
    ) -> dict[str, str]:
        url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/logs"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        logs = {}

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for filename in archive.namelist():
                with archive.open(filename) as file:
                    logs[filename] = file.read().decode(
                        "utf-8",
                        errors="replace",
                    )

        return logs
    def search_repository(
        self,
        repository: str,
        query: str,
    ) -> list[dict]:
        results = self.github.search_code(
            f"{query} repo:{repository}"
        )

        return [
            {
                "path": result.path,
                "name": result.name,
                "url": result.html_url,
            }
            for result in results
        ]
