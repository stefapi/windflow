#!/usr/bin/env python3
#  Copyright (c) 2024  stefapi
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import os
import re
import sys
from datetime import date

import jinja2
import toml

macros = {
    "name": "Myapp",
    "package": "Myapp",
    "srcdir": "myapp",
    "version": "0.0.1",
    "short_version": "0.0",
    "man_section": "1",
    "short_desc": "Short application description",
    "long_desc": "Long application description",
    "website": "http://example.com",
    "repository": "http://git.example.com",
    "author": "Author",
    "mail": "author@example.com",
    "obfuscated_mail": "author at example dot com",
    "doc_title": "Myapp Documentation",
    "bug_report": "http://git.example.com/issues",
    "documentation": "http://doc.example.com",
    "license": "None",
}

files = {
    "dev/templates/version.py.jinja": ["{{srcdir}}/version.py"],
    "dev/templates/conf.py.jinja": ["docs/conf.py"],
    "dev/templates/CONTRIBUTING.md.jinja": ["CONTRIBUTING.md"],
    "dev/templates/manpage.man.adoc.jinja": ["docs/manpage.man.adoc"],
}

conf_file = "pyproject.toml"
if os.path.isfile(conf_file):
    readconfig = toml.load(conf_file)
else:
    sys.exit(conf_file + " is not in current directory")


if "custom" in readconfig:
    if "params" in readconfig["custom"]:
        if "man-section" in readconfig["custom"]["params"]:
            macros["man_section"] = readconfig["custom"]["params"]["man-section"]
        if "long-description" in readconfig["custom"]["params"]:
            macros["long_desc"] = readconfig["custom"]["params"]["long-description"]
        if "package" in readconfig["custom"]["params"]:
            macros["package"] = readconfig["custom"]["params"]["package"]
        if "srcdir" in readconfig["custom"]["params"]:
            macros["srcdir"] = readconfig["custom"]["params"]["srcdir"]
if "project" in readconfig:  # PEP 621
    project = readconfig["project"]
    if "name" in project:
        macros["name"] = project["name"]
        macros["doc_title"] = macros["name"] + " Documentation"
    if "version" in project:
        macros["version"] = project["version"]
        s = re.search(r"^([0-9]+)\.([0-9]+)", macros["version"])
        if s:
            macros["short_version"] = (
                str(s.group(1).strip()) + "." + str(s.group(2).strip())
            )
    if "description" in project:
        macros["short_desc"] = project["description"]
    urls = project.get("urls", {}) or {}
    if "Documentation" in urls:
        macros["documentation"] = urls["Documentation"]
    if "Homepage" in urls:
        macros["website"] = urls["Homepage"]
    if "Repository" in urls:
        macros["repository"] = urls["Repository"]
        macros["bug_report"] = macros["repository"] + "/issues"
    if "authors" in project and project["authors"]:
        author = project["authors"][0]
        author_name = (
            author.get("name", "") if isinstance(author, dict) else str(author)
        )
        author_email = author.get("email", "") if isinstance(author, dict) else ""
        macros["author"] = author_name.strip()
        if author_email:
            macros["mail"] = author_email.strip()
            macros["obfuscated_mail"] = (
                macros["mail"].replace(".", " dot ").replace("@", " at ")
            )
        macros["copyright"] = (
            "Copyright (c) " + str(date.today().year) + " " + macros["author"]
        )
    if "license" in project:
        license_field = project["license"]
        if isinstance(license_field, dict):
            macros["license"] = license_field.get("text", "")
        else:
            macros["license"] = str(license_field)

for src, dst_list in files.items():
    new_list = []
    for dst in dst_list:
        match = re.search(r"\{\{(\w+)\}\}", dst)
        if match is not None:
            val = macros.get(match.group(1))
            dst = re.sub(r"\{\{(\w+)\}\}", val, dst)
        new_list.append(dst)
    dst_list = new_list
    match = re.search(r"\{\{(\w+)\}\}", src)
    if match is not None:
        val = macros.get(match.group(1))
        src = re.sub(r"\{\{(\w+)\}\}", val, src)
    with open(src, "r") as file:
        template = jinja2.Template(file.read(), autoescape=True)
        string = template.render(macros)
        for dst in dst_list:
            with open(dst, "w") as ofile:
                ofile.write(string)
