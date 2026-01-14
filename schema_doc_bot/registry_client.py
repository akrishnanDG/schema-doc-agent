"""Client for interacting with Confluent Schema Registry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


@dataclass
class SchemaInfo:
    """Container for schema metadata."""

    subject: str
    version: int
    schema_id: int
    schema_type: str
    schema: dict[str, Any]


class SchemaRegistryClient:
    """Client for Confluent Schema Registry API."""

    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ):
        self.url = url.rstrip("/")
        self.auth = HTTPBasicAuth(username, password) if username and password else None
        self.session = requests.Session()
        if self.auth:
            self.session.auth = self.auth
        self.session.headers.update({"Accept": "application/vnd.schemaregistry.v1+json"})

    def get_subjects(self) -> list[str]:
        """Get all subjects (schema names) from the registry."""
        response = self.session.get(f"{self.url}/subjects")
        response.raise_for_status()
        return response.json()

    def get_latest_schema(self, subject: str) -> SchemaInfo:
        """Get the latest version of a schema for a subject."""
        response = self.session.get(f"{self.url}/subjects/{subject}/versions/latest")
        response.raise_for_status()
        data = response.json()

        schema_str = data.get("schema", "{}")
        schema_dict = json.loads(schema_str) if isinstance(schema_str, str) else schema_str

        return SchemaInfo(
            subject=data["subject"],
            version=data["version"],
            schema_id=data["id"],
            schema_type=data.get("schemaType", "AVRO"),
            schema=schema_dict,
        )

    def get_all_schemas(
        self,
        schema_type: str | None = None,
        include_subjects: list[str] | None = None,
        exclude_subjects: list[str] | None = None,
    ) -> list[SchemaInfo]:
        """
        Fetch all schemas from the registry.
        
        Args:
            schema_type: Schema type to filter (None = all types, "AVRO", "JSON", "PROTOBUF")
            include_subjects: Glob patterns for subjects to include (None = all)
            exclude_subjects: Glob patterns for subjects to exclude
            
        Returns:
            List of SchemaInfo objects
        """
        from .config import filter_subjects
        
        subjects = self.get_subjects()
        
        # Apply filters
        if include_subjects or exclude_subjects:
            subjects = filter_subjects(
                subjects,
                include_subjects or [],
                exclude_subjects or [],
            )
        
        schemas = []
        for subject in subjects:
            try:
                schema_info = self.get_latest_schema(subject)
                # Filter by type if specified
                if schema_type is None or schema_info.schema_type.upper() == schema_type.upper():
                    schemas.append(schema_info)
            except requests.HTTPError as e:
                print(f"Warning: Could not fetch schema for {subject}: {e}")

        return schemas

    def check_connectivity(self) -> bool:
        """Verify connection to the schema registry."""
        try:
            response = self.session.get(f"{self.url}/subjects")
            return response.status_code == 200
        except requests.RequestException:
            return False

