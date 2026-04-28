# Project Chat Agent

[![Doctests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)
[![Integration Tests](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml/badge.svg)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/integration-tests.yml)
![flake8](https://img.shields.io/github/actions/workflow/status/aryan00-hub/llm-inclass/flake8.yml?label=flake8)
[![PyPI](https://img.shields.io/pypi/v/cmc-csci040-annaryan)](https://pypi.org/project/cmc-csci040-annaryan/)
[![Coverage](https://img.shields.io/badge/coverage-90%25%2B-brightgreen)](https://github.com/aryan00-hub/llm-inclass/actions/workflows/doctests.yml)

<!--
I'm not leaving super detailed comments here because your README looks basically the same as Preslie's
(and so I'm guessing you both worked together, which is fine)
but you should review my comments to her README and make the same changes
-->

Project Chat Agent is a Python-based conversational assistant for inspecting and reasoning over local project documents from the terminal. It supports both automatic LLM tool-calling and manual slash commands so you can get fast, deterministic file inspection when needed. The project is packaged for `pip` installation, includes doctests and CI checks, and is designed to safely answer questions about code and text files in the current working directory.

## Demo

![Project Chat Agent demo](docs/demo.gif)

## Installation

```bash
pip install cmc-csci040-annaryan
```

Published by GitHub user `aryan00-hub` on PyPI as `cmc-csci040-annaryan`.

## Usage

```bash
chat
```

After launch, type prompts and press Enter. Use `Ctrl+C` to exit the REPL.

You can ask normal questions or run slash commands like `/ls`, `/cat`, `/grep`, `/calculate`, and `/compact`.

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

## Features

- Automatic tool-calling with an LLM for file-aware answers.
- Manual slash commands: `/ls`, `/cat`, `/grep`, `/calculate`.
- Path safety guards against absolute paths and `..` traversal.
- Conversation compaction with `/compact` to reduce context size.
- One-shot CLI prompts: `chat "your question"`.
- Debug tool tracing with `chat --debug`.
- Provider selection with `chat --provider <groq|openai|anthropic|google>`.
- Slash-command tab completion for commands and file paths.
- Image context loading with `/load_image <image.png|image.jpg>`.
