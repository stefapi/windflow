#!/usr/bin/env python3
import re
import sys
import unicodedata
from enum import Enum
from itertools import groupby
from pathlib import Path

import slugify
from fastapi import FastAPI
from humps import camelize
from jinja2 import Template
from pydantic import BaseModel, computed_field

# Add the project root to Python path to import from app
CWD = Path(__file__).parent
PROJECT_ROOT = CWD / ".." / ".."
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app

# Output to frontend/src/api instead of dev/scripts/output/javascriptAPI
TS_DIR = PROJECT_ROOT / "frontend" / "src" / "api"
TS_OUT_FILE = TS_DIR / "apiRoutes.ts"
TEMPLATES_DIR = CWD / ".." / "templates"

TS_REQUESTS = TEMPLATES_DIR / "ts_requests.jinja"
TS_ROUTES = TEMPLATES_DIR / "ts_routes.jinja"
TS_INDEX = TEMPLATES_DIR / "ts_index.jinja"
TS_TYPES = TEMPLATES_DIR / "ts_types.jinja"

TS_DIR.mkdir(exist_ok=True, parents=True)


def sanitize_function_name(text: str) -> str:
    """
    Sanitize text to create valid TypeScript function names.
    Removes apostrophes and converts accented characters to their non-accented equivalents.
    """
    if not text:
        return text

    # Remove various types of apostrophes and quotes using Unicode code points
    apostrophe_codes = [0x0027, 0x2018, 0x2019, 0x0060, 0x00B4, 0x02BC, 0x02BB, 0x02BD, 0x02BE, 0x02BF]
    for code in apostrophe_codes:
        char = chr(code)
        if char in text:
            text = text.replace(char, "")

    # Convert accented characters to their non-accented equivalents
    # NFD normalization decomposes characters into base + combining characters
    # Then we filter out the combining characters (category 'Mn')
    text = ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')
    return text


def openapi_type_to_typescript(prop_schema: dict) -> str:
    """
    Convert OpenAPI property schema to TypeScript type.
    """
    if not prop_schema:
        return "never"

    # Handle $ref (references to other schemas)
    if "$ref" in prop_schema:
        ref_name = prop_schema["$ref"].split("/")[-1]
        return ref_name

    # Handle anyOf (union types, often used for nullable fields)
    if "anyOf" in prop_schema:
        types = []
        for any_schema in prop_schema["anyOf"]:
            if any_schema.get("type") == "null":
                continue  # We'll handle null separately
            types.append(openapi_type_to_typescript(any_schema))

        # Check if null is allowed
        has_null = any(schema.get("type") == "null" for schema in prop_schema["anyOf"])
        base_type = " | ".join(types) if types else "never"

        return f"{base_type} | null" if has_null else base_type

    # Handle arrays
    if prop_schema.get("type") == "array":
        if "items" in prop_schema:
            item_type = openapi_type_to_typescript(prop_schema["items"])
            return f"{item_type}[]"
        return "never[]"

    # Handle basic types
    openapi_type = prop_schema.get("type", "never")

    type_mapping = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "object": "Record<string, unknown>",  # More specific than any for objects
        "array": "never[]"
    }

    return type_mapping.get(openapi_type, "never")


def extract_schemas(openapi_spec: dict) -> dict:
    """
    Extract and process all schemas from OpenAPI specification.
    """
    schemas = {}

    if "components" not in openapi_spec or "schemas" not in openapi_spec["components"]:
        return schemas

    raw_schemas = openapi_spec["components"]["schemas"]

    for schema_name, schema_def in raw_schemas.items():
        if schema_def.get("type") != "object" or "properties" not in schema_def:
            continue

        processed_schema = {
            "title": schema_def.get("title", schema_name),
            "description": schema_def.get("description", ""),
            "required": schema_def.get("required", []),
            "properties": {}
        }

        # Process each property
        for prop_name, prop_def in schema_def["properties"].items():
            processed_schema["properties"][prop_name] = {
                "ts_type": openapi_type_to_typescript(prop_def),
                "description": prop_def.get("description", ""),
                "title": prop_def.get("title", prop_name)
            }

        schemas[schema_name] = processed_schema

    return schemas


class RouteObject:
    def __init__(self, route_string) -> None:
        self.prefix = "/" + route_string.split("/")[1]
        self.route = route_string.replace(self.prefix, "")
        self.js_route = self.route.replace("{", "${")
        self.parts = route_string.split("/")[1:]
        self.var = re.findall(r"\{(.*?)\}", route_string)
        self.is_function = "{" in self.route
        # Include all parts to avoid collisions, not just parts[1:]
        self.router_slug = slugify.slugify("_".join(self.parts), separator="_")
        self.router_camel = camelize(self.router_slug)

    def __repr__(self) -> str:
        return f"""Route: {self.route}
Parts: {self.parts}
Function: {self.is_function}
Var: {self.var}
Slug: {self.router_slug}
"""


class RequestType(str, Enum):
    get = "get"
    put = "put"
    post = "post"
    patch = "patch"
    delete = "delete"


class HTTPRequest(BaseModel):
    request_type: RequestType
    description: str = ""
    summary: str = ""
    tags: list[str] = []
    requestBody: dict = {}
    vars: list[str] = []
    path: str = ""  # Add path information
    @computed_field
    @property
    def content(self)-> str:
        if 'content' in self.requestBody:
            # Check for JSON content type
            if 'application/json' in self.requestBody['content']:
                a= self.requestBody['content']['application/json']['schema']['$ref'].split("/")[-1]
                return a
            # Check for form data content type
            elif 'application/x-www-form-urlencoded' in self.requestBody['content']:
                a= self.requestBody['content']['application/x-www-form-urlencoded']['schema']['$ref'].split("/")[-1]
                return a
        return ""

    @property
    def summary_camel(self):
        # Create a more unique function name by incorporating path information
        base_name = self.summary

        # If summary is empty or too generic, use path-based naming
        if not base_name or len(base_name.strip()) < 3:
            # Generate name from path and method
            path_parts = [part for part in self.path.split("/") if part and not part.startswith("{")]
            base_name = f"{self.request_type.value} {' '.join(path_parts)}"

        # For potential collisions, add path context
        # Check if this might be a collision-prone name
        collision_prone_keywords = ["lister", "récupère", "get", "list", "fetch"]
        if any(keyword in base_name.lower() for keyword in collision_prone_keywords):
            # Add the first meaningful path segment to make it unique
            path_parts = [part for part in self.path.split("/") if part and not part.startswith("{")]
            if path_parts:
                # Use the first path segment as context (e.g., "groups", "organizations")
                context = path_parts[0]
                if context not in base_name.lower():
                    base_name = f"{base_name} {context}"

        camelized = camelize(base_name)
        result = sanitize_function_name(camelized)
        return result

    @property
    def js_docs(self):
        return self.description.replace("\n", "  \n  * ")

    @computed_field
    @property
    def is_form_data_endpoint(self) -> bool:
        """
        Detect if this endpoint requires form data (like login endpoints).
        Returns True for endpoints that use OAuth2PasswordRequestForm or similar form-based authentication.
        """
        # Check if this is a login endpoint
        if self.path == "/login" and self.request_type == RequestType.post:
            return True

        # Check if the requestBody indicates form data
        if 'content' in self.requestBody:
            content_types = self.requestBody['content'].keys()
            if 'application/x-www-form-urlencoded' in content_types:
                return True

        return False


class PathObject(BaseModel):
    route_object: RouteObject
    http_verbs: list[HTTPRequest]

    class Config:
        arbitrary_types_allowed = True


def get_path_objects(app: FastAPI):
    paths = []
    schemas = {}

    openapi_spec = app.openapi()

    for key, value in openapi_spec.items():
        if key == "paths":
            for path_key, path_value in value.items():
                paths.append(
                    PathObject(
                        route_object=RouteObject(path_key),
                        http_verbs=[HTTPRequest(request_type=k, path=path_key, **v) for k, v in path_value.items()],
                    )
                )
        elif key == "components":
            for key, value in value.items():
                if key == "schemas":
                    for key, value in value.items():
                        # Only process schemas that have properties (object schemas)
                        if 'properties' in value:
                            schemas[key] = [k for k, v in value['properties'].items()]

    for path in paths:
        for verb in path.http_verbs:
            if verb.content in schemas:
                verb.vars = list(schemas[verb.content])

    # Extract TypeScript schemas
    ts_schemas = extract_schemas(openapi_spec)

    return paths, ts_schemas


def read_template(file: Path):
    with open(file, "r") as f:
        return f.read()


def generate_template(app):
    paths, ts_schemas = get_path_objects(app)

    static_paths = [x.route_object for x in paths if not x.route_object.is_function]
    get_paths = [x.route_object for x in paths if x.route_object.is_function]

    static_paths.sort(key=lambda x: x.router_slug)
    get_paths.sort(key=lambda x: x.router_slug)

    # Generate API routes
    template = Template(read_template(TS_ROUTES))
    content = template.render(
        paths={"prefix": paths[0].route_object.prefix, "static_paths": static_paths, "get_paths": get_paths, "all_paths": paths}
    )
    with open(TS_OUT_FILE, "w") as f:
        f.write(content)

    # Generate TypeScript types
    if ts_schemas:
        template = Template(read_template(TS_TYPES))
        content = template.render(schemas=ts_schemas)
        with open(TS_DIR.joinpath("types.ts"), "w") as f:
            f.write(content)

    all_tags = []
    for k, g in groupby(paths, lambda x: "_".join(x.http_verbs[0].tags)):
        # Handle endpoints without tags by assigning them to a default category
        if not k or not camelize(k):
            k = "root"  # Default category for endpoints without tags

        # Skip if the camelized name is still empty (shouldn't happen now)
        camelized_name = camelize(k)
        if not camelized_name:
            continue

        template = Template(read_template(TS_REQUESTS))
        content = template.render(paths={"all_paths": list(g), "export_name": camelized_name})

        all_tags.append(camelized_name)

        with open(TS_DIR.joinpath(camelized_name + ".ts"), "w") as f:
            f.write(content)

    template = Template(read_template(TS_INDEX))
    content = template.render(files={"files": all_tags})

    with open(TS_DIR.joinpath("index.ts"), "w") as f:
        f.write(content)


if __name__ == "__main__":
    generate_template(app)
