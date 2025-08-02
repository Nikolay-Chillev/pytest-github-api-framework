import re
import requests
from typing import Dict, Optional, Any, Union
from config import GITHUB_TOKEN, BASE_URL
from requests.exceptions import RequestException

class RepoClientError(Exception):
    """Base exception for RepoClient errors."""
    pass

class ValidationError(RepoClientError):
    """Raised when input validation fails."""
    pass

class GitHubAPIError(RepoClientError):
    """Raised when GitHub API returns an error."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message)

class RepoClient:
    """Client for interacting with GitHub's Repository API.
    
    This client provides methods to create, read, update, and delete GitHub repositories
    with proper error handling and input validation.
    """
    
    # GitHub repository name rules
    REPO_NAME_PATTERN = r'^[a-zA-Z0-9_.-]+$'
    MAX_REPO_NAME_LENGTH = 100
    
    def __init__(self, token: Optional[str] = None, base_url: str = None):
        """Initialize the GitHub Repository client.
        
        Args:
            token: GitHub personal access token. If not provided, uses GITHUB_TOKEN from environment.
            base_url: Base URL for GitHub API. Defaults to config.BASE_URL.
            
        Raises:
            ValidationError: If token is not provided and GITHUB_TOKEN is not set.
            GitHubAPIError: If there's an error verifying the token with GitHub API.
        """
        self.token = token or GITHUB_TOKEN
        self.base_url = base_url or BASE_URL
        
        if not self.token:
            raise ValidationError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token parameter.")
            
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            # Verify the token and get the authenticated user
            user_response = requests.get(
                f"{self.base_url}/user",
                headers=self.headers,
                timeout=10
            )
            user_response.raise_for_status()
            self.username = user_response.json()['login']
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            if status_code == 401:
                raise GitHubAPIError("Invalid GitHub token. Please check your credentials.", status_code=401) from e
            raise GitHubAPIError(f"Failed to authenticate with GitHub: {str(e)}", status_code=status_code) from e

    def _validate_repo_name(self, repo_name: str) -> None:
        """Validates repository name against GitHub's naming rules.
        
        Args:
            repo_name: Name of the repository to validate.
            
        Raises:
            ValidationError: If the repository name is invalid.
        """
        if not repo_name:
            raise ValidationError("Repository name cannot be empty.")
            
        if len(repo_name) > self.MAX_REPO_NAME_LENGTH:
            raise ValidationError(
                f"Repository name cannot exceed {self.MAX_REPO_NAME_LENGTH} characters. "
                f"Got {len(repo_name)} characters."
            )
            
        if not re.match(self.REPO_NAME_PATTERN, repo_name):
            raise ValidationError(
                "Repository name can only contain alphanumeric characters, '-', '_', and '.'"
            )
            
        if repo_name[0] == '-' or repo_name[-1] == '.':
            raise ValidationError("Repository name cannot start with '-' or end with '.'")
    
    def create_repo(self, repo_name: str, description: str = "", private: bool = False) -> requests.Response:
        """Creates a new repository for the authenticated user.
        
        Args:
            repo_name: Name of the repository to create.
            description: Description of the repository.
            private: Whether the repository should be private.
            
        Returns:
            requests.Response: The response from GitHub API.
            
        Raises:
            ValidationError: If repository name is invalid.
            GitHubAPIError: If the API request fails.
        """
        self._validate_repo_name(repo_name)
        
        if not isinstance(description, str):
            raise ValidationError("Description must be a string.")
            
        url = f"{self.base_url}/user/repos"
        payload = {
            "name": repo_name,
            "description": description,
            "private": private,
            "auto_init": False  # Don't initialize with README
        }
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            if status_code == 422:
                error_msg = e.response.json().get('message', 'Validation failed')
                raise GitHubAPIError(f"Failed to create repository: {error_msg}", status_code=422) from e
            raise GitHubAPIError(
                f"Failed to create repository: {str(e)}",
                status_code=status_code
            ) from e

    def get_repo(self, repo_name: str) -> requests.Response:
        """Gets details of a specific repository.
        
        Args:
            repo_name: Name of the repository to retrieve.
            
        Returns:
            requests.Response: The response from GitHub API.
            
        Raises:
            ValidationError: If repository name is invalid.
            GitHubAPIError: If the API request fails.
        """
        self._validate_repo_name(repo_name)
        
        url = f"{self.base_url}/repos/{self.username}/{repo_name}"
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            raise GitHubAPIError(
                f"Failed to get repository '{repo_name}': {str(e)}",
                status_code=status_code
            ) from e

    def update_repo(self, repo_name: str, new_description: str) -> requests.Response:
        """Updates a repository's description.
        
        Args:
            repo_name: Name of the repository to update.
            new_description: New description for the repository.
            
        Returns:
            requests.Response: The response from GitHub API.
            
        Raises:
            ValidationError: If repository name is invalid or description is not a string.
            GitHubAPIError: If the API request fails.
        """
        self._validate_repo_name(repo_name)
        
        if not isinstance(new_description, str):
            raise ValidationError("Description must be a string.")
            
        url = f"{self.base_url}/repos/{self.username}/{repo_name}"
        payload = {
            "description": new_description
        }
        
        try:
            response = requests.patch(
                url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            raise GitHubAPIError(
                f"Failed to update repository '{repo_name}': {str(e)}",
                status_code=status_code
            ) from e

    def delete_repo(self, repo_name: str) -> requests.Response:
        """Deletes a repository.
        
        Args:
            repo_name: Name of the repository to delete.
            
        Returns:
            requests.Response: The response from GitHub API (204 No Content on success).
            
        Raises:
            ValidationError: If repository name is invalid.
            GitHubAPIError: If the API request fails.
        """
        self._validate_repo_name(repo_name)
        
        url = f"{self.base_url}/repos/{self.username}/{repo_name}"
        
        try:
            response = requests.delete(
                url,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            return response
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
            raise GitHubAPIError(
                f"Failed to delete repository '{repo_name}': {str(e)}",
                status_code=status_code
            ) from e