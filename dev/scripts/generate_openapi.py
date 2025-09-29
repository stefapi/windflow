#!/usr/bin/env python3

import json
import os
import sys
import toml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add the project root to Python path to import from app
CWD = Path(__file__).parent
PROJECT_ROOT = CWD / ".." / ".."
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

# Output directory
DOC_DIR = PROJECT_ROOT / "doc"
OPENAPI_FILE = DOC_DIR / "openapi.json"

def load_project_metadata() -> Dict[str, Any]:
    """
    Load project metadata from pyproject.toml file.
    """
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    try:
        config = toml.load(pyproject_path)
        metadata = {}

        # Extract from tool.poetry section
        if "tool" in config and "poetry" in config["tool"]:
            poetry = config["tool"]["poetry"]
            metadata.update({
                "name": poetry.get("name", "API"),
                "version": poetry.get("version", "1.0.0"),
                "description": poetry.get("description", ""),
                "authors": poetry.get("authors", []),
                "license": poetry.get("license", ""),
                "homepage": poetry.get("homepage", ""),
                "repository": poetry.get("repository", ""),
                "documentation": poetry.get("documentation", "")
            })

        # Extract from custom.params section
        if "custom" in config and "params" in config["custom"]:
            custom = config["custom"]["params"]
            if "long-description" in custom:
                metadata["long_description"] = custom["long-description"]

        return metadata
    except Exception as e:
        print(f"Warning: Could not load project metadata from pyproject.toml: {e}")
        return {}

def get_server_urls() -> List[Dict[str, str]]:
    """
    Get server URLs from environment variables or defaults.
    """
    servers = []

    # Development server
    dev_port = os.getenv("PORT", "8010")
    dev_host = os.getenv("DEV_HOST", "localhost")
    servers.append({
        "url": f"http://{dev_host}:{dev_port}",
        "description": "Development server (local)"
    })

    # Production server (if configured)
    prod_url = os.getenv("PROD_API_URL")
    if prod_url:
        servers.append({
            "url": prod_url,
            "description": "Production server"
        })

    # Staging server (if configured)
    staging_url = os.getenv("STAGING_API_URL")
    if staging_url:
        servers.append({
            "url": staging_url,
            "description": "Staging server"
        })

    return servers

def extract_tags_from_routes(openapi_spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extract unique tags from the API routes and generate descriptions dynamically
    based on the actual API endpoints and their operations.
    """
    tag_operations = {}

    # Extract tags and their associated operations from paths
    if "paths" in openapi_spec:
        for path, path_data in openapi_spec["paths"].items():
            for method, operation in path_data.items():
                if isinstance(operation, dict) and "tags" in operation:
                    for tag in operation["tags"]:
                        if tag not in tag_operations:
                            tag_operations[tag] = {
                                "operations": [],
                                "summaries": [],
                                "descriptions": [],
                                "paths": []
                            }

                        tag_operations[tag]["operations"].append(method.upper())
                        tag_operations[tag]["paths"].append(path)

                        if "summary" in operation:
                            tag_operations[tag]["summaries"].append(operation["summary"])
                        if "description" in operation:
                            tag_operations[tag]["descriptions"].append(operation["description"])

    # Generate tag descriptions based on actual operations
    tags = []
    for tag in sorted(tag_operations.keys()):
        description = generate_dynamic_tag_description(tag, tag_operations[tag])
        tags.append({
            "name": tag,
            "description": description
        })

    return tags

def generate_dynamic_tag_description(tag: str, operations_data: Dict[str, List]) -> str:
    """
    Generate a description for a tag based on its actual operations and endpoints.
    """
    operations = operations_data.get("operations", [])
    summaries = operations_data.get("summaries", [])
    descriptions = operations_data.get("descriptions", [])
    paths = operations_data.get("paths", [])

    # Count operation types
    operation_counts = {}
    for op in operations:
        operation_counts[op] = operation_counts.get(op, 0) + 1

    # Analyze common patterns in summaries and descriptions
    all_text = " ".join(summaries + descriptions).lower()

    # Generate description based on analysis
    description_parts = []

    # Add operation type information
    if operation_counts:
        op_types = []
        if operation_counts.get("GET", 0) > 0:
            op_types.append("retrieval")
        if operation_counts.get("POST", 0) > 0:
            op_types.append("creation")
        if operation_counts.get("PUT", 0) > 0 or operation_counts.get("PATCH", 0) > 0:
            op_types.append("modification")
        if operation_counts.get("DELETE", 0) > 0:
            op_types.append("deletion")

        if op_types:
            description_parts.append(f"Operations for {', '.join(op_types)}")

    # Analyze content to determine domain
    domain_keywords = {
        "user": ["user", "utilisateur", "account", "profile", "login", "authentication"],
        "organization": ["organization", "organisation", "company", "tenant"],
        "environment": ["environment", "environnement", "deployment", "infrastructure"],
        "element": ["element", "élément", "component", "resource", "infrastructure"],
        "group": ["group", "groupe", "team", "permission", "role"],
        "policy": ["policy", "politique", "rule", "access", "permission"],
        "audit": ["audit", "log", "monitoring", "tracking", "history"],
        "health": ["health", "status", "check", "monitoring", "diagnostic"],
        "tag": ["tag", "label", "category", "classification"],
        "function": ["function", "fonction", "capability", "feature"],
        "coffee": ["coffee", "teapot", "test", "utility"]
    }

    # Find the most relevant domain
    domain_scores = {}
    for domain, keywords in domain_keywords.items():
        score = 0
        for keyword in keywords:
            score += all_text.count(keyword)
            score += tag.lower().count(keyword) * 3  # Tag name is more important
        domain_scores[domain] = score

    best_domain = max(domain_scores.items(), key=lambda x: x[1])

    # Generate contextual description
    if best_domain[1] > 0:  # If we found relevant keywords
        domain = best_domain[0]

        if domain == "user":
            base_desc = "user management and authentication"
        elif domain == "organization":
            base_desc = "organization management and membership"
        elif domain == "environment":
            base_desc = "environment configuration and deployment"
        elif domain == "element":
            base_desc = "infrastructure elements and resources"
        elif domain == "group":
            base_desc = "user groups and permissions"
        elif domain == "policy":
            base_desc = "access control policies and rules"
        elif domain == "audit":
            base_desc = "audit logging and system monitoring"
        elif domain == "health":
            base_desc = "system health and status monitoring"
        elif domain == "tag":
            base_desc = "resource tagging and categorization"
        elif domain == "function":
            base_desc = "system functions and capabilities"
        elif domain == "coffee":
            base_desc = "utility endpoints and testing"
        else:
            base_desc = f"{tag.lower()} operations"
    else:
        # Fallback to tag name analysis
        base_desc = f"{tag.replace('_', ' ').replace('-', ' ').title()} operations"

    # Add operation count information
    total_ops = len(operations)
    if total_ops > 0:
        description_parts.append(f"Provides {base_desc} with {total_ops} endpoint{'s' if total_ops != 1 else ''}")
    else:
        description_parts.append(f"Provides {base_desc}")

    # Add specific operation details if available
    if operation_counts:
        op_details = []
        for op_type, count in sorted(operation_counts.items()):
            if count > 0:
                op_details.append(f"{count} {op_type}")
        if op_details:
            description_parts.append(f"({', '.join(op_details)} operations)")

    return ". ".join(description_parts) + "."

def extract_security_schemes(openapi_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract security schemes from the existing OpenAPI spec or generate defaults.
    """
    # Check if security schemes already exist
    if ("components" in openapi_spec and
        "securitySchemes" in openapi_spec["components"] and
        openapi_spec["components"]["securitySchemes"]):
        return openapi_spec["components"]["securitySchemes"]

    # Generate default security schemes based on detected patterns
    security_schemes = {}

    # Check if we have OAuth2 endpoints
    has_login = False
    if "paths" in openapi_spec:
        for path, methods in openapi_spec["paths"].items():
            if "login" in path.lower():
                has_login = True
                break

    if has_login:
        security_schemes["OAuth2PasswordBearerOrKey"] = {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "/login",
                    "scopes": {}
                }
            }
        }

    return security_schemes

def analyze_api_patterns(openapi_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze API patterns to extract comprehensive statistics and insights.
    """
    analysis = {
        "endpoint_count": 0,
        "operation_count": 0,
        "methods_used": set(),
        "response_codes": set(),
        "parameter_types": set(),
        "content_types": set(),
        "authentication_required": 0,
        "path_parameters": 0,
        "query_parameters": 0,
        "request_bodies": 0,
        "tags_count": 0,
        "schemas_count": 0,
        "security_schemes_count": 0
    }

    if "paths" in openapi_spec:
        analysis["endpoint_count"] = len(openapi_spec["paths"])

        for path, methods in openapi_spec["paths"].items():
            for method, operation in methods.items():
                if isinstance(operation, dict):
                    analysis["operation_count"] += 1
                    analysis["methods_used"].add(method.upper())

                    # Check for authentication requirements
                    if "security" in operation or "security" in openapi_spec:
                        analysis["authentication_required"] += 1

                    # Analyze parameters
                    if "parameters" in operation:
                        for param in operation["parameters"]:
                            if param.get("in") == "path":
                                analysis["path_parameters"] += 1
                            elif param.get("in") == "query":
                                analysis["query_parameters"] += 1

                            if "schema" in param and "type" in param["schema"]:
                                analysis["parameter_types"].add(param["schema"]["type"])

                    # Analyze request bodies
                    if "requestBody" in operation:
                        analysis["request_bodies"] += 1
                        if "content" in operation["requestBody"]:
                            analysis["content_types"].update(operation["requestBody"]["content"].keys())

                    # Analyze responses
                    if "responses" in operation:
                        analysis["response_codes"].update(operation["responses"].keys())
                        for response in operation["responses"].values():
                            if "content" in response:
                                analysis["content_types"].update(response["content"].keys())

    # Count components
    if "components" in openapi_spec:
        if "schemas" in openapi_spec["components"]:
            analysis["schemas_count"] = len(openapi_spec["components"]["schemas"])
        if "securitySchemes" in openapi_spec["components"]:
            analysis["security_schemes_count"] = len(openapi_spec["components"]["securitySchemes"])

    if "tags" in openapi_spec:
        analysis["tags_count"] = len(openapi_spec["tags"])

    return analysis

def enhance_api_description(openapi_spec: Dict[str, Any], project_metadata: Dict[str, Any]) -> str:
    """
    Generate an enhanced API description based on analysis of the actual API.
    """
    analysis = analyze_api_patterns(openapi_spec)

    # Base description from project metadata
    description = project_metadata.get("description", "")
    long_description = project_metadata.get("long_description", "")

    if long_description:
        description = f"{description}\n\n{long_description}" if description else long_description

    # Add API overview section
    description += f"\n\n## API Overview\n"
    description += f"This API provides {analysis['operation_count']} operations across {analysis['endpoint_count']} endpoints"

    if analysis['tags_count'] > 0:
        description += f", organized into {analysis['tags_count']} functional areas"

    description += "."

    # Add supported methods
    if analysis['methods_used']:
        methods = sorted(analysis['methods_used'])
        description += f" Supports {', '.join(methods)} HTTP methods."

    # Add authentication info
    auth_percentage = (analysis['authentication_required'] / analysis['operation_count'] * 100) if analysis['operation_count'] > 0 else 0
    if auth_percentage > 0:
        description += f"\n\n## Authentication\n"
        if auth_percentage == 100:
            description += "All endpoints require authentication."
        elif auth_percentage > 50:
            description += f"Most endpoints ({auth_percentage:.0f}%) require authentication."
        else:
            description += f"Some endpoints ({auth_percentage:.0f}%) require authentication."

    # Add data formats
    if analysis['content_types']:
        content_types = sorted(analysis['content_types'])
        description += f"\n\n## Data Formats\n"
        description += f"Supports the following content types: {', '.join(content_types)}."

    # Add response codes info
    if analysis['response_codes']:
        success_codes = [code for code in analysis['response_codes'] if code.startswith('2')]
        error_codes = [code for code in analysis['response_codes'] if not code.startswith('2')]

        description += f"\n\n## Response Codes\n"
        if success_codes:
            description += f"Success responses: {', '.join(sorted(success_codes))}. "
        if error_codes:
            description += f"Error responses: {', '.join(sorted(error_codes))}."

    # Add schemas info
    if analysis['schemas_count'] > 0:
        description += f"\n\n## Data Models\n"
        description += f"Includes {analysis['schemas_count']} data model definitions for request and response validation."

    description += f"\n\n## Error Handling\n"
    description += "The API returns standardized error responses with appropriate HTTP status codes and detailed error messages."

    return description.strip()

def enhance_openapi_spec(openapi_spec: dict) -> dict:
    """
    Enhance the OpenAPI specification with additional details and metadata.
    All information is extracted dynamically from project configuration and introspection.
    """
    # Load project metadata from pyproject.toml
    project_metadata = load_project_metadata()

    # Add generation timestamp and generator info
    openapi_spec["info"]["x-generated-at"] = datetime.now().isoformat()
    generator_name = os.getenv("OPENAPI_GENERATOR_NAME", f"{project_metadata.get('name', 'API')} OpenAPI Generator")
    openapi_spec["info"]["x-generator"] = generator_name

    # Enhance info section with project metadata
    if "info" not in openapi_spec:
        openapi_spec["info"] = {}

    info = openapi_spec["info"]

    # Build title from project metadata
    title = project_metadata.get("name", "API")
    if title.lower() != "api":
        title = f"{title.title()} API"

    # Build enhanced description using dynamic analysis
    description = enhance_api_description(openapi_spec, project_metadata)

    # Add generic API documentation sections if no specific description
    if not description:
        description = f"API for {title}"

    # Update info with extracted metadata
    info_updates = {
        "title": title,
        "description": description.strip(),
        "version": project_metadata.get("version", "1.0.0")
    }

    # Add contact information if available
    authors = project_metadata.get("authors", [])
    if authors and isinstance(authors, list) and len(authors) > 0:
        author_info = authors[0]
        if isinstance(author_info, str) and "<" in author_info and ">" in author_info:
            # Parse "Name <email>" format
            import re
            match = re.match(r"^([^<]+)<([^>]+)>$", author_info.strip())
            if match:
                name = match.group(1).strip()
                email = match.group(2).strip()
                contact = {"name": name, "email": email}

                # Add repository URL if available
                repository = project_metadata.get("repository", "")
                if repository:
                    contact["url"] = repository

                info_updates["contact"] = contact

    # Add license information if available
    license_name = project_metadata.get("license", "")
    if license_name:
        license_info = {"name": license_name}

        # Add common license URLs
        license_urls = {
            "MIT": "https://opensource.org/licenses/MIT",
            "Apache": "https://www.apache.org/licenses/LICENSE-2.0",
            "Apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
            "GPL": "https://www.gnu.org/licenses/gpl-3.0.html",
            "GPL-3.0": "https://www.gnu.org/licenses/gpl-3.0.html",
            "BSD": "https://opensource.org/licenses/BSD-3-Clause"
        }

        if license_name in license_urls:
            license_info["url"] = license_urls[license_name]

        info_updates["license"] = license_info

    # Add terms of service if homepage is available
    homepage = project_metadata.get("homepage", "")
    if homepage:
        info_updates["termsOfService"] = f"{homepage}/terms"

    info.update(info_updates)

    # Add servers from environment variables and configuration
    openapi_spec["servers"] = get_server_urls()

    # Extract and add security schemes
    if "components" not in openapi_spec:
        openapi_spec["components"] = {}

    if "securitySchemes" not in openapi_spec["components"]:
        openapi_spec["components"]["securitySchemes"] = {}

    # Extract security schemes from existing spec or generate defaults
    security_schemes = extract_security_schemes(openapi_spec)
    if security_schemes:
        openapi_spec["components"]["securitySchemes"].update(security_schemes)

        # Add global security requirement based on detected schemes
        security_requirements = []
        for scheme_name in security_schemes.keys():
            security_requirements.append({scheme_name: []})

        if security_requirements:
            openapi_spec["security"] = security_requirements

    # Extract tags from actual routes
    openapi_spec["tags"] = extract_tags_from_routes(openapi_spec)

    # Enhance paths with additional metadata
    if "paths" in openapi_spec:
        for path, methods in openapi_spec["paths"].items():
            for method, operation in methods.items():
                # Add operation ID if missing
                if "operationId" not in operation:
                    # Generate operation ID from path and method
                    path_parts = [part for part in path.split("/") if part and not part.startswith("{")]
                    operation_id = method + "".join(word.capitalize() for word in path_parts)
                    operation["operationId"] = operation_id

                # Add examples to responses
                if "responses" in operation:
                    for status_code, response in operation["responses"].items():
                        if "content" in response:
                            for content_type, content_info in response["content"].items():
                                if content_type == "application/json" and "examples" not in content_info:
                                    # Add example based on status code
                                    if status_code == "200":
                                        content_info["examples"] = {
                                            "success": {
                                                "summary": "Successful response",
                                                "value": {
                                                    "status": "success",
                                                    "message": "Operation completed successfully",
                                                    "data": {}
                                                }
                                            }
                                        }
                                    elif status_code.startswith("4"):
                                        content_info["examples"] = {
                                            "error": {
                                                "summary": "Client error",
                                                "value": {
                                                    "status": "error",
                                                    "message": "Invalid request",
                                                    "detail": "Detailed error description"
                                                }
                                            }
                                        }

    # Add external documentation if available
    documentation_url = project_metadata.get("documentation", "")
    if not documentation_url:
        # Try to construct from homepage
        homepage = project_metadata.get("homepage", "")
        if homepage:
            documentation_url = f"{homepage}/docs"

    if documentation_url:
        project_name = project_metadata.get("name", "API")
        openapi_spec["externalDocs"] = {
            "description": f"{project_name.title()} Documentation",
            "url": documentation_url
        }

    return openapi_spec

def generate_openapi_json():
    """
    Generate the comprehensive OpenAPI specification and save it to .junie/openapi.json
    """
    print("Generating comprehensive OpenAPI specification...")

    # Get the OpenAPI specification from FastAPI
    openapi_spec = app.openapi()

    # Enhance the specification with additional details
    enhanced_spec = enhance_openapi_spec(openapi_spec)

    # Ensure the .junie directory exists
    JUNIE_DIR.mkdir(exist_ok=True)

    # Save the enhanced OpenAPI specification
    with open(OPENAPI_FILE, "w", encoding="utf-8") as f:
        json.dump(enhanced_spec, f, indent=2, ensure_ascii=False, sort_keys=True)

    print(f"✅ OpenAPI specification generated successfully!")
    print(f"📁 File location: {OPENAPI_FILE}")
    print(f"📊 File size: {OPENAPI_FILE.stat().st_size} bytes")

    # Print summary statistics
    paths_count = len(enhanced_spec.get("paths", {}))
    total_operations = sum(len(methods) for methods in enhanced_spec.get("paths", {}).values())
    schemas_count = len(enhanced_spec.get("components", {}).get("schemas", {}))

    print(f"📈 Statistics:")
    print(f"   - API paths: {paths_count}")
    print(f"   - Total operations: {total_operations}")
    print(f"   - Schema definitions: {schemas_count}")
    print(f"   - Tags: {len(enhanced_spec.get('tags', []))}")
    print(f"   - Security schemes: {len(enhanced_spec.get('components', {}).get('securitySchemes', {}))}")

if __name__ == "__main__":
    generate_openapi_json()
