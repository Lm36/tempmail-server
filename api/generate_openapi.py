#!/usr/bin/env python3
"""
Generate OpenAPI specification from FastAPI app
"""
import json
import os
import sys

# Set test mode to skip database connection during import
os.environ["TESTING"] = "1"

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.main import app


def generate_openapi_spec(output_path: str = "openapi.json"):
    """Generate and save OpenAPI spec"""
    openapi_schema = app.openapi()

    with open(output_path, "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI spec generated: {output_path}")
    print(f"Title: {openapi_schema['info']['title']}")
    print(f"Version: {openapi_schema['info']['version']}")
    print(f"Endpoints: {len(openapi_schema['paths'])}")


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    generate_openapi_spec(output)
