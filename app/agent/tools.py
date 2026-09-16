from langchain_core.tools import tool

from app.github.client import GitHubClient


def create_github_tools(github_client: GitHubClient):

    @tool
    def get_file(
        repository: str,
        path: str,
        ref: str | None = None,
    ) -> str:
        """Get the contents of a specific file from a GitHub repository."""
        return github_client.get_file(repository, path, ref)

    @tool
    def search_repository(
        repository: str,
        query: str,
    ) -> list[dict]:
        """Search a GitHub repository for relevant files or code."""
        return github_client.search_repository(repository, query)

    return [
        get_file,
        search_repository,
    ]