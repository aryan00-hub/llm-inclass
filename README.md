# Project Chat Agent

[![Doctests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)
[![Integration Tests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml)
[![flake8](https://img.shields.io/github/actions/workflow/status/aryan00-hub/llm-inclass/flake8.yml?label=flake8)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/flake8.yml)
[![PyPI](https://img.shields.io/pypi/v/cmc-csci040-annaryan)](https://pypi.org/project/cmc-csci040-annaryan/)
[![Coverage](https://img.shields.io/badge/coverage-90%25%2B-brightgreen)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)

Project Chat Agent is a terminal-first assistant for inspecting and editing repository files with safe local tools. It supports both automatic tool calling and manual slash commands, and it records write/remove actions as git commits for auditable history. Project 4 adds repo startup checks, AGENTS.md bootstrapping, doctest execution, safe write/remove tools, diff-based updates, and a Ralph retry loop for failing doctests.

## Demo

![Project Chat Agent demo](docs/demo.gif)

## Example: Agent File Writes + Git Commits

This is a good example because it proves that the agent can create, update, and remove files while making git commits automatically.

```bash
$ ls -a
.git  AGENTS.md  README.md  chat.py  tools
$ git log --oneline -n 1
680fe78 [docchat] Initial commit
$ chat
chat> /write_file tmp_one.txt hello "add tmp one"
Committed 9dc91c2
chat> /rm tmp_one.txt
Removed 1 file(s) and committed [docchat] rm tmp_one.txt
chat> ^C
$ git log --oneline -n 3
716cec9 [docchat] rm tmp_one.txt
9dc91c2 [docchat] add tmp one
680fe78 [docchat] Initial commit
```

## Example: Startup Safety Checks

This is a good example because it demonstrates the required Project 4 startup guard (`.git` must exist).

```bash
$ mkdir -p /tmp/p4check && cd /tmp/p4check
$ python3 /path/to/chat.py
ERROR: no .git folder found. Please run docchat from inside a git repository.
```

## Example: Doctests Tool

This is a good example because it shows explicit doctest execution output from the tool.

```bash
$ chat "/doctests tools/ls_tool.py"
...
tools/ls_tool.py::tools.ls_tool.run_ls PASSED
...
```

## Example: Diff-Based File Update

This is a good example because it uses a patch-style update (`diff`) instead of rewriting a full file.

```bash
$ chat
chat> update tools/compact_tool.py to improve the compact description using write_file with a diff patch
Committed abc1234
Doctests for tools/compact_tool.py:
...
Test passed.
```

## Example: Ralph Retry Loop

This is a good example because it demonstrates that when doctests fail, the agent keeps using tools until doctests pass before returning a final answer.

```bash
$ chat
chat> Create a file bad_loop.py with a failing doctest, then keep fixing and re-running doctests until they pass. Use tools only.
The doctests for the file `bad_loop.py` now pass.
```

## Example: Webpage Project

This is a good example because it shows inspecting files first, then answering using grounded repo context.

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

This is a good example because it combines file inspection and summary of implementation intent.

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

This is a good example because it uses both directory listing and pattern search to answer a concrete question.

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
