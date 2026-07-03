"""Represents metadata of downloaded resources."""

from src.metadata.base import SourceMetadata, SourceType
from src.metadata.github import GithubSourceMetadata
from src.metadata.gitlab import GitlabSourceMetadata

__all__ = ["GithubSourceMetadata", "GitlabSourceMetadata", "SourceMetadata", "SourceType"]
