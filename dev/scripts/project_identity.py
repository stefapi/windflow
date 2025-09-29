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
import re
from datetime import date

import jinja2
import toml
import os
import sys

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
if "tool" in readconfig:
    if "poetry" in readconfig["tool"]:
        if "name" in readconfig["tool"]["poetry"]:
            macros["name"] = readconfig["tool"]["poetry"]["name"]
            macros["doc_title"] = macros["name"] + " Documentation"
        if "version" in readconfig["tool"]["poetry"]:
            macros["version"] = readconfig["tool"]["poetry"]["version"]
            s = re.search(r"^([0-9]+)\.([0-9]+)", macros["version"])
            if s:
                macros["short_version"] = str(s.group(1).strip()) + "." + str(s.group(2).strip())
        if "description" in readconfig["tool"]["poetry"]:
            macros["short_desc"] = readconfig["tool"]["poetry"]["description"]
        if "documentation" in readconfig["tool"]["poetry"]:
            macros["documentation"] = readconfig["tool"]["poetry"]["documentation"]
        if "homepage" in readconfig["tool"]["poetry"]:
            macros["website"] = readconfig["tool"]["poetry"]["homepage"]
        if "repository" in readconfig["tool"]["poetry"]:
            macros["repository"] = readconfig["tool"]["poetry"]["repository"]
            macros["bug_report"] = macros["repository"] + "/issues"
        if "authors" in readconfig["tool"]["poetry"]:
            author_mail = readconfig["tool"]["poetry"]["authors"][0]
            s = re.search(r"^([^\<]*)\<([^\>]*)\>$", author_mail)
            if s:
                macros["author"] = s.group(1).strip()
                macros["mail"] = s.group(2).strip()
                macros["obfuscated_mail"] = macros["mail"].replace(".", " dot ").replace("@", " at ")
                macros["copyright"] = "Copyright (c) " + str(date.today().year) + " " + macros["author"]
        if "license" in readconfig["tool"]["poetry"]:
            macros["license"] = readconfig["tool"]["poetry"]["license"]

for src, dst_list in files.items():
    new_list = []
    for dst in dst_list:
        match = re.search(r'\{\{(\w+)\}\}', dst)
        if match is not None:
            val= macros.get(match.group(1))
            dst = re.sub(r'\{\{(\w+)\}\}', val, dst)
        new_list.append(dst)
    dst_list = new_list
    match = re.search(r'\{\{(\w+)\}\}', src)
    if match is not None:
        val = macros.get(match.group(1))
        src = re.sub(r'\{\{(\w+)\}\}', val, src)
    with open(src, "r") as file:
        template = jinja2.Template(file.read(), autoescape=True)
        string = template.render(macros)
        for dst in dst_list:
            with open(dst, "w") as ofile:
                ofile.write(string)
