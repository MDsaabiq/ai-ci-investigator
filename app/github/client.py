import io
import zipfile
from typing import Any
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

    def create_branch(
        self,
        repository: str,
        branch_name: str,
        base_sha: str,
    ) -> str:
        repo = self.get_repository(repository)
        ref_path = f"refs/heads/{branch_name}"

        try:
            repo.get_git_ref(f"heads/{branch_name}")
            # Branch already exists, update ref to base_sha
            ref = repo.get_git_ref(f"heads/{branch_name}")
            ref.edit(sha=base_sha, force=True)
        except Exception:
            # Create new branch ref
            repo.create_git_ref(ref=ref_path, sha=base_sha)

        return branch_name

    def apply_file_changes(
        self,
        repository: str,
        branch_name: str,
        changes: list[Any],
        commit_message: str = "AI automated CI fix",
    ) -> list[str]:
        repo = self.get_repository(repository)
        applied = []

        for change in changes:
            # Support both Pydantic FileChange and dict
            path = change.path if hasattr(change, "path") else change.get("path")
            action = change.action if hasattr(change, "action") else change.get("action", "create")
            content = change.content if hasattr(change, "content") else change.get("content", "")

            if not path:
                continue

            clean_path = path.strip().lstrip("/")

            try:
                if action == "create":
                    try:
                        # Check if it already exists on branch
                        existing = repo.get_contents(clean_path, ref=branch_name)
                        repo.update_file(
                            clean_path,
                            f"{commit_message}: update {clean_path}",
                            content,
                            sha=existing.sha,
                            branch=branch_name,
                        )
                    except Exception:
                        repo.create_file(
                            clean_path,
                            f"{commit_message}: create {clean_path}",
                            content,
                            branch=branch_name,
                        )
                elif action == "modify":
                    existing = repo.get_contents(clean_path, ref=branch_name)
                    repo.update_file(
                        clean_path,
                        f"{commit_message}: modify {clean_path}",
                        content,
                        sha=existing.sha,
                        branch=branch_name,
                    )
                elif action == "delete":
                    existing = repo.get_contents(clean_path, ref=branch_name)
                    repo.delete_file(
                        clean_path,
                        f"{commit_message}: delete {clean_path}",
                        sha=existing.sha,
                        branch=branch_name,
                    )
                applied.append(clean_path)
            except Exception as e:
                print(f"Error applying change to {clean_path}: {e}")

        return applied

    def create_pull_request(
        self,
        repository: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> dict[str, Any]:
        repo = self.get_repository(repository)

        # Check if an open PR already exists for this branch
        open_prs = list(repo.get_pulls(state="open", head=f"{repo.owner.login}:{head_branch}"))
        if open_prs:
            pr = open_prs[0]
            pr.edit(title=title, body=body)
            return {
                "pr_url": pr.html_url,
                "pr_number": pr.number,
                "title": pr.title,
                "created": False,
            }

        pr = repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch,
        )

        return {
            "pr_url": pr.html_url,
            "pr_number": pr.number,
            "title": pr.title,
            "created": True,
        }

