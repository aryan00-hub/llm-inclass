# DocChat: Conversational Interface to Chat with Documents

[![Doctests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)
[![Integration Tests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml)
![flake8](https://img.shields.io/github/actions/workflow/status/aryan00-hub/llm-inclass/flake8.yml?label=flake8)
[![PyPI](https://img.shields.io/pypi/v/cmc-csci040-annaryan)](https://pypi.org/project/cmc-csci040-annaryan/)
[![Coverage](https://img.shields.io/badge/coverage-90%25%2B-brightgreen)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)

DocChat is a Python-based conversational assistant for inspecting and reasoning over local project documents from the terminal. It can summarize repository context and answer questions using safe tool calls over text/code files, with both automatic tool use and explicit slash commands (`/ls`, `/cat`, `/grep`, `/calculate`, `/compact`).

[Watch demo video](docs/demo.mov)

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

## Security Notes

All file-reading tools reject absolute paths and directory traversal (`..`) so the agent cannot read outside the current project directory.
