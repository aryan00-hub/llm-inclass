# DocChat CLI

[![Doctests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)
[![Integration Tests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml)
![flake8](https://img.shields.io/github/actions/workflow/status/aryan00-hub/llm-inclass/flake8.yml?label=flake8)
[![PyPI](https://img.shields.io/pypi/v/cmc-csci040-annaryan)](https://pypi.org/project/cmc-csci040-annaryan/)
[![Coverage](https://img.shields.io/badge/coverage-90%25%2B-brightgreen)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)

DocChat is a terminal AI agent that chats about your project files using safe local tools (`ls`, `cat`, `grep`, `calculate`). It supports both automatic tool calling and manual slash commands for fast, deterministic inspection.

![DocChat demo](docs/demo.gif)

## Usage

```bash
pip install cmc-csci040-annaryan
chat
```

## Example: Webpage Project

This is a good example because it shows using local tools to inspect project files before asking a summary question.

```bash
$ cd test_projects/webpage
$ chat
chat> /ls .
chat> /cat README.md
chat> What is this project about?
```

## Example: Markdown Compiler

This is a good example because it combines direct file inspection with a focused question about project purpose.

```bash
$ cd test_projects/markdown_compiler
$ chat
chat> /ls .
chat> /cat README.md
chat> What does this project do?
```

## Example: Ebay Scraper

This is a good example because it uses both README context and code search to answer a practical question.

```bash
$ cd test_projects/ebay_scraper
$ chat
chat> /ls .
chat> /grep "ebay" "*.py"
chat> Tell me what this scraper collects.
```

## Security Notes

All file-reading tools reject absolute paths and directory traversal (`..`) so the agent cannot read outside the current project directory.
