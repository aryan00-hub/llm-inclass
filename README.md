# Project Chat Agent

[![Doctests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)
[![Integration Tests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml)
![flake8](https://img.shields.io/github/actions/workflow/status/aryan00-hub/llm-inclass/flake8.yml?label=flake8)
[![PyPI](https://img.shields.io/pypi/v/cmc-csci040-annaryan)](https://pypi.org/project/cmc-csci040-annaryan/)
[![Coverage](https://img.shields.io/badge/coverage-90%25%2B-brightgreen)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)

Project Chat Agent is a terminal-first coding assistant for repository work. It can inspect files, run tool calls, and apply safe write actions with git-backed history, so every change is auditable. The project is packaged for `pip`, validated with doctests/coverage/flake8 in CI, and restricted to safe relative paths inside the active repo.

## Demo

![Project Chat Agent demo](docs/demo.gif)

## Example Usage

This session shows normal REPL use plus manual slash commands for deterministic local inspection.

```bash
$ chat
chat> /ls .
README.md
chat.py
tools
chat> /cat README.md
# Project Chat Agent
...
chat> summarize this repo in two sentences
This repository contains a terminal chat agent for local project inspection and safe automation. It combines LLM tool-calling with path-restricted file operations and CI-tested behavior.
chat> ^C
```

## Agent Write Actions

This session demonstrates file creation, modification, deletion, and automatic git commits from the agent tools.

```bash
$ ls -a
.git  AGENTS.md  README.md  chat.py  tools
$ git log --oneline -n 2
abc1234 init project
$ chat
chat> /write_file '{"path":"hello.py","contents":"\"\"\"demo\\n\\n>>> 1+1\\n2\\n\"\"\"\\n","commit_message":"add hello module"}'
Committed def5678
Doctests for hello.py:
...
hello.py::hello.py PASSED
...
chat> /write_file '{"path":"hello.py","contents":"\"\"\"demo\\n\\n>>> 2+2\\n4\\n\"\"\"\\n","commit_message":"update hello doctest"}'
Committed 89ab012
Doctests for hello.py:
...
hello.py::hello.py PASSED
...
chat> /rm hello.py
Removed 1 file(s) and committed [docchat] rm hello.py
chat> ^C
$ git log --oneline -n 4
3456cde [docchat] rm hello.py
89ab012 [docchat] update hello doctest
def5678 [docchat] add hello module
abc1234 init project
```

## Startup Checks

This session shows startup safety checks required for agent mode (`.git` required, `AGENTS.md` auto-loaded when present).

```bash
$ mkdir -p /tmp/no_repo && cd /tmp/no_repo
$ python3 /path/to/chat.py
ERROR: no .git folder found. Please run docchat from inside a git repository.
```

## Example: Webpage Project

This is a good example because it shows using local tools to inspect project files before asking a summary question.

```bash
$ cd test_projects/webpage
$ chat
chat> /ls .
README.md
index.html
chat> /cat README.md
This project contains a personal webpage.
chat> What is this project about?
This project appears to build a personal webpage with static files.
```

## Example: Markdown Compiler

This is a good example because it combines direct file inspection with a focused question about project purpose.

```bash
$ cd test_projects/markdown_compiler
$ chat
chat> /ls .
README.md
main.py
chat> /cat README.md
This project compiles markdown into HTML.
chat> What does this project do?
It converts markdown content into HTML output.
```

## Example: Ebay Scraper

This is a good example because it uses both README context and code search to answer a practical question.

```bash
$ cd test_projects/ebay_scraper
$ chat
chat> /ls .
README.md
scraper.py
chat> /grep "ebay" "*.py"
scraper.py:# scrape ebay listing data
chat> Tell me what this scraper collects.
It collects product information from ebay listings.
```
