"""
Comprehensive test suite for GitHub Repository Client.

This file contains all unit, integration, and workflow tests for the RepoClient class.
"""
import os
import pytest
import random
import string
from unittest.mock import patch, Mock

from api_clients.repo_client import RepoClient, ValidationError, GitHubAPIError

# Test configuration
TEST_REPO_PREFIX = "test-repo-"

def generate_test_repo_name(prefix=TEST_REPO_PREFIX):
    """Generate a unique test repository name."""
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}{random_suffix}"

class TestRepoClientUnit:
    """Unit tests for RepoClient using mocks."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.patcher = patch('api_clients.repo_client.requests')
        self.mock_requests = self.patcher.start()
        self.client = RepoClient(token="test-token")
        
        # Mock successful user authentication
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'login': 'testuser'}
        self.mock_requests.get.return_value = mock_response
    
    def teardown_method(self):
        """Tear down test fixtures after each test method."""
        self.patcher.stop()
    
    def test_init_without_token(self):
        """Test initialization without a token raises ValidationError."""
        with patch('api_clients.repo_client.GITHUB_TOKEN', None):
            with pytest.raises(ValidationError):
                RepoClient()
    
    @patch('api_clients.repo_client.re')
    def test_validate_repo_name(self, mock_re):
        """Test repository name validation."""
        # Test empty name
        with pytest.raises(ValidationError, match="Repository name cannot be empty"):
            self.client._validate_repo_name("")

        # Test name too long
        long_name = "a" * 101
        with pytest.raises(ValidationError, match=f"Repository name cannot exceed {self.client.MAX_REPO_NAME_LENGTH} characters"):
            self.client._validate_repo_name(long_name)

        # Test invalid characters
        invalid_names = ["invalid/name", ".start-with-dot", "end-with-dot.", "has space"]
        for name in invalid_names:
            mock_re.match.return_value = None  # Simulate pattern not matching
            with pytest.raises(ValidationError, match="Repository name can only contain alphanumeric characters"):
                self.client._validate_repo_name(name)
            mock_re.match.assert_called_once_with(self.client.REPO_NAME_PATTERN, name)
            mock_re.match.reset_mock()

        # Test valid names
        valid_names = ["test", "test123", "test-repo", "test.repo", "test_repo"]
        for name in valid_names:
            mock_re.match.return_value = True  # Simulate pattern matching
            try:
                self.client._validate_repo_name(name)
                mock_re.match.assert_called_once_with(self.client.REPO_NAME_PATTERN, name)
            except ValidationError:
                pytest.fail(f"Valid name '{name}' failed validation")
            mock_re.match.reset_mock()
    
    @patch.object(RepoClient, '_validate_repo_name')
    def test_create_repo_validation(self, mock_validate):
        """Test create_repo input validation."""
        self.client.create_repo("test-repo")
        mock_validate.assert_called_once_with("test-repo")

class TestRepoClientIntegration:
    """Integration tests for RepoClient with real GitHub API calls."""
    
    @classmethod
    def setup_class(cls):
        """Set up test fixtures before any tests are run."""
        cls.client = RepoClient()
        cls.test_repo = generate_test_repo_name()
        
        # Create a test repository for testing
        cls.client.create_repo(
            cls.test_repo,
            "Test repository for integration tests",
            private=False
        )
    
    @classmethod
    def teardown_class(cls):
        """Clean up after all tests are done."""
        try:
            cls.client.delete_repo(cls.test_repo)
        except GitHubAPIError:
            pass  # Ignore if already deleted
    
    def test_create_and_get_repo(self):
        """Test creating and retrieving a repository."""
        response = self.client.get_repo(self.test_repo)
        assert response.status_code == 200
        repo_data = response.json()
        assert repo_data['name'] == self.test_repo
        assert not repo_data['private']
    
    def test_update_repo(self):
        """Test updating a repository's description."""
        new_description = "Updated description for testing"
        response = self.client.update_repo(self.test_repo, new_description)
        assert response.status_code == 200
        
        # Verify the update
        response = self.client.get_repo(self.test_repo)
        assert response.json()['description'] == new_description
    
    def test_private_repo_workflow(self):
        """Test creating and managing a private repository."""
        repo_name = generate_test_repo_name("test-private-repo-")
        try:
            # Create private repo
            response = self.client.create_repo(repo_name, "Private test repo", private=True)
            assert response.status_code == 201
            
            # Verify it's private
            response = self.client.get_repo(repo_name)
            assert response.json()['private'] is True
            
            # Update description
            new_desc = "Updated private repo"
            response = self.client.update_repo(repo_name, new_desc)
            assert response.json()['description'] == new_desc
            
        finally:
            # Cleanup
            try:
                self.client.delete_repo(repo_name)
            except GitHubAPIError:
                pass

class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.client = RepoClient()
        self.non_existent_repo = "this-repo-does-not-exist-12345"
    
    def test_nonexistent_repo_operations(self):
        """Test operations on non-existent repository."""
        # Test get
        with pytest.raises(GitHubAPIError) as exc_info:
            self.client.get_repo(self.non_existent_repo)
        assert exc_info.value.status_code == 404
        
        # Test update
        with pytest.raises(GitHubAPIError) as exc_info:
            self.client.update_repo(self.non_existent_repo, "New description")
        assert exc_info.value.status_code == 404
        
        # Test delete
        with pytest.raises(GitHubAPIError) as exc_info:
            self.client.delete_repo(self.non_existent_repo)
        assert exc_info.value.status_code == 404
    
    def test_duplicate_repo_creation(self):
        """Test creating a duplicate repository."""
        # Create a temporary repo
        temp_repo = generate_test_repo_name("temp-repo-")
        try:
            self.client.create_repo(temp_repo)
            
            # Try to create again
            with pytest.raises(GitHubAPIError) as exc_info:
                self.client.create_repo(temp_repo)
            assert exc_info.value.status_code in [400, 422]
                
        finally:
            # Cleanup
            try:
                self.client.delete_repo(temp_repo)
            except GitHubAPIError:
                pass

def test_invalid_token():
    """Test initialization with an invalid token."""
    with pytest.raises(GitHubAPIError) as exc_info:
        RepoClient(token="invalid-token-123")
    assert exc_info.value.status_code in [401, 403]

def test_missing_token():
    """Test initialization without a token."""
    with patch('api_clients.repo_client.GITHUB_TOKEN', None):
        with pytest.raises(ValidationError):
            RepoClient()
