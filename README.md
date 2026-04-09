# DocChat CLI

[![Doctests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)
[![Integration Tests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml)
[![flake8](https://github.com/aryan00-hub/llm-inclass/actions/workflows/flake8.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/flake8.yml)
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

This is a good example because it demonstrates using `grep` and `cat` to verify implementation details against a real project.

```bash
$ cd test_projects/webpage
$ chat
chat> does this project include any javascript files?
I used /ls and /grep and found no JavaScript files in this project.
```

## Example: Markdown Compiler

This is a good example because it asks a concrete architecture question that can be answered from source files.

```bash
$ cd test_projects/markdown_compiler
$ chat
chat> does this project use regular expressions?
I searched Python files and found usage of the `re` library in the parser module.
```

## Example: Ebay Scraper

This is a good example because it combines README summarization with source-level evidence from tool outputs.

```bash
$ cd test_projects/ebay_scraper
$ chat
chat> tell me what this project is for
From the README and scraper files, this project extracts product information from ebay listings.
```

## Security Notes

All file-reading tools reject absolute paths and directory traversal (`..`) so the agent cannot read outside the current project directory.
