"""Document chat agent with local tools and a terminal REPL.

This file defines the Chat class, tool execution flow, and interactive loop used by the `chat` command.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
from typing import Any

from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

from tools.calculate import TOOL_SPEC as CALCULATE_SPEC
from tools.calculate import run_calculate
from tools.compact_tool import TOOL_SPEC as COMPACT_SPEC
from tools.cat_tool import TOOL_SPEC as CAT_SPEC
from tools.cat_tool import run_cat
from tools.grep_tool import TOOL_SPEC as GREP_SPEC
from tools.grep_tool import run_grep
from tools.ls_tool import TOOL_SPEC as LS_SPEC
from tools.ls_tool import run_ls

TOOL_SPECS = [CALCULATE_SPEC, LS_SPEC, CAT_SPEC, GREP_SPEC, COMPACT_SPEC]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PROVIDER_MODELS = {
    "groq": "llama-3.1-8b-instant",
    "openai": "openai/gpt-5",
    "anthropic": "anthropic/claude-opus-4.1",
    "google": "google/gemini-2.5-pro",
}


def _is_tool_validation_error(exc: Exception) -> bool:
    """Return True when provider rejected a hallucinated/invalid tool call.

    >>> _is_tool_validation_error(ValueError("x"))
    False
    >>> _is_tool_validation_error(RuntimeError("tool call validation failed"))
    True
    """
    return "tool call validation failed" in str(exc).lower()


class Chat:
    """A small doc-chat agent that can read local files through safe tools.

    The class keeps conversation state in `messages`, supports automatic LLM tool calls,
    and also supports manual slash-command tool calls in the REPL.

    >>> from types import SimpleNamespace
    >>> class FakeCompletions:
    ...     def __init__(self):
    ...         self.calls = 0
    ...     def create(self, **kwargs):
    ...         self.calls += 1
    ...         if self.calls == 1:
    ...             tool_call = SimpleNamespace(
    ...                 id="t1",
    ...                 function=SimpleNamespace(name="calculate", arguments='{"expression": "2+3"}')
    ...             )
    ...             msg = SimpleNamespace(content=None, tool_calls=[tool_call])
    ...             return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    ...         msg = SimpleNamespace(content="Result is 5", tool_calls=[])
    ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    >>> fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    >>> chat = Chat(client=fake_client)
    >>> chat.send_message("what is 2+3?")
    'Result is 5'
    >>> print(chat.handle_slash_command('/calculate 9*9'))
    81
    """

    def __init__(
        self,
        model: str | None = None,
        client: Any | None = None,
        debug: bool = False,
        provider: str = "groq",
    ):
        """Initialize chat state and optionally inject a client for tests.

        >>> c = Chat(client=object())
        >>> isinstance(c.messages, list)
        True
        >>> c.provider
        'groq'
        """
        self.provider = provider
        self.model = model or PROVIDER_MODELS[provider]
        self._client = client
        self.debug = debug
        self.messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a coding assistant that can inspect project files with tools. "
                    "Never claim to read files unless tool output shows it."
                ),
            }
        ]

    @property
    def client(self) -> Any:
        """Return API client, lazily creating one from GROQ_API_KEY if needed.

        >>> from types import SimpleNamespace
        >>> c = Chat(client=SimpleNamespace())
        >>> c.client is c._client
        True
        >>> import os
        >>> old_getenv = os.getenv
        >>> os.getenv = lambda key, default=None: None
        >>> c2 = Chat(client=None, provider="google")
        >>> try:
        ...     _ = c2.client
        ... except RuntimeError as e:
        ...     print("Missing OPENROUTER_API_KEY" in str(e))
        True
        >>> os.getenv = old_getenv
        """
        if self._client is None:
            load_dotenv()
            if self.provider == "groq":
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise RuntimeError("Missing GROQ_API_KEY in environment or .env")
                self._client = Groq(api_key=api_key)
            else:
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    raise RuntimeError("Missing OPENROUTER_API_KEY for non-groq providers")
                self._client = OpenAI(
                    base_url=OPENROUTER_BASE_URL,
                    api_key=api_key,
                )
        return self._client

    def run_tool(self, name: str, args: dict[str, Any]) -> str:
        """Dispatch a named tool with decoded arguments.

        >>> c = Chat(client=object())
        >>> c.run_tool("calculate", {"expression": "10-3"})
        '7'
        >>> c.run_tool("ls", {"path": ".."})
        'ERROR: unsafe path'
        >>> c.run_tool("cat", {"path": "missing.txt"})
        'ERROR: file not found'
        >>> isinstance(c.run_tool("grep", {"pattern": "x", "path": "*.py"}), str)
        True
        >>> from types import SimpleNamespace
        >>> class SummaryOnly:
        ...     def create(self, **kwargs):
        ...         m = SimpleNamespace(content='summary line', tool_calls=[])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=m)])
        >>> c2 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=SummaryOnly())))
        >>> _ = c2.send_message('hello world')
        >>> c2.run_tool("compact", {})
        'summary line'
        >>> len(c2.messages)
        1
        >>> c.run_tool("nope", {})
        'ERROR: unknown tool: nope'
        """
        if name == "calculate":
            return run_calculate(str(args.get("expression", "")))
        if name == "ls":
            return run_ls(str(args.get("path", ".")))
        if name == "cat":
            return run_cat(str(args.get("path", "")))
        if name == "grep":
            return run_grep(str(args.get("pattern", "")), str(args.get("path", "")))
        if name == "compact":
            return self.compact_messages()
        return f"ERROR: unknown tool: {name}"

    def _debug_tool(self, name: str, args: dict[str, Any]) -> None:
        """Print a debug line showing tool invocation when debug mode is enabled.

        >>> c = Chat(client=object(), debug=False)
        >>> c._debug_tool("ls", {"path": "."})
        >>> c2 = Chat(client=object(), debug=True)
        >>> c2._debug_tool("calculate", {"expression": "1+2"})
        [tool] /calculate 1+2
        >>> c2._debug_tool("cat", {"path": "README.md"})
        [tool] /cat README.md
        """
        if not self.debug:
            return

        if name == "calculate":
            print(f"[tool] /calculate {args.get('expression', '')}".rstrip())
        elif name == "ls":
            print(f"[tool] /ls {args.get('path', '.')}".rstrip())
        elif name == "cat":
            print(f"[tool] /cat {args.get('path', '')}".rstrip())
        elif name == "grep":
            print(f"[tool] /grep {args.get('pattern', '')} {args.get('path', '')}".rstrip())
        elif name == "compact":
            print("[tool] /compact")
        else:
            print(f"[tool] /{name} {args}")

    def compact_messages(self) -> str:
        """Summarize conversation into 1-5 lines via a subagent and replace memory.

        >>> from types import SimpleNamespace
        >>> class SummaryOnly:
        ...     def create(self, **kwargs):
        ...         m = SimpleNamespace(content='short summary', tool_calls=[])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=m)])
        >>> c = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=SummaryOnly())))
        >>> _ = c.send_message('hello')
        >>> c.compact_messages()
        'short summary'
        >>> len(c.messages)
        1
        >>> c.messages[0]['content'].startswith('Conversation summary')
        True
        """
        if len(self.messages) <= 1:
            summary = "No prior context to summarize."
            self.messages = [
                {
                    "role": "system",
                    "content": f"Conversation summary (compacted):\n{summary}",
                }
            ]
            return summary

        # Subagent shares provider/model/client but uses an isolated prompt/messages.
        subagent = Chat(
            model=self.model,
            provider=self.provider,
            debug=self.debug,
            client=self.client,
        )
        transcript = json.dumps(self.messages, ensure_ascii=False)
        response = subagent.client.chat.completions.create(
            model=subagent.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the chat history in 1-5 short lines. "
                        "Keep concrete facts and prior tool findings."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Summarize this chat history:\\n{transcript}",
                },
            ],
            temperature=0,
            max_tokens=180,
        )
        summary = (response.choices[0].message.content or "").strip()
        if not summary:
            summary = "No prior context to summarize."
        self.messages = [
            {
                "role": "system",
                "content": f"Conversation summary (compacted):\\n{summary}",
            }
        ]
        return summary

    def send_message(self, user_input: str, max_rounds: int = 6) -> str:
        """Send user text to the model and resolve any automatic tool-calling chain.

        >>> from types import SimpleNamespace
        >>> class OneShot:
        ...     def create(self, **kwargs):
        ...         msg = SimpleNamespace(content="hi", tool_calls=[])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=OneShot())))
        >>> c.send_message("hello")
        'hi'
        >>> class BadJson:
        ...     def __init__(self):
        ...         self.calls = 0
        ...     def create(self, **kwargs):
        ...         self.calls += 1
        ...         if self.calls == 1:
        ...             tc = SimpleNamespace(id='x1', function=SimpleNamespace(name='calculate', arguments='{bad'))
        ...             msg = SimpleNamespace(content=None, tool_calls=[tc])
        ...             return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        ...         msg = SimpleNamespace(content='ok', tool_calls=[])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c2 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=BadJson())))
        >>> c2.send_message("test")
        'ok'
        >>> class Endless:
        ...     def create(self, **kwargs):
        ...         func = SimpleNamespace(name='calculate', arguments='{\"expression\":\"1+1\"}')
        ...         tc = SimpleNamespace(id='z', function=func)
        ...         msg = SimpleNamespace(content=None, tool_calls=[tc])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c3 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=Endless())))
        >>> c3.send_message("loop", max_rounds=1)
        '2'
        >>> class RepeatThenStop:
        ...     def __init__(self):
        ...         self.calls = 0
        ...     def create(self, **kwargs):
        ...         self.calls += 1
        ...         func = SimpleNamespace(name='ls', arguments='{\"path\":\".github\"}')
        ...         tc = SimpleNamespace(id='r1', function=func)
        ...         msg = SimpleNamespace(content=None, tool_calls=[tc])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c4 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=RepeatThenStop())))
        >>> c4.send_message("what folder is in .github?", max_rounds=3).startswith("workflows")
        True
        """
        self.messages.append({"role": "user", "content": user_input})
        last_signature = None
        repeat_count = 0
        last_tool_result = ""

        for _ in range(max_rounds):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=TOOL_SPECS,
                    tool_choice="auto",
                    temperature=0,
                    max_tokens=500,
                )
            except Exception as exc:
                if not _is_tool_validation_error(exc):
                    raise
                # Some providers occasionally hallucinate unsupported remote tools
                # even when local tools are provided. Retry once with tools disabled.
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    temperature=0,
                    max_tokens=500,
                )
            message = response.choices[0].message

            tool_calls = getattr(message, "tool_calls", None) or []
            if tool_calls:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": getattr(message, "content", None),
                        "tool_calls": tool_calls,
                    }
                )

                for tool_call in tool_calls:
                    name = tool_call.function.name
                    raw_args = tool_call.function.arguments or "{}"
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                    signature = (name, json.dumps(args, sort_keys=True))
                    if signature == last_signature:
                        repeat_count += 1
                    else:
                        repeat_count = 0
                    last_signature = signature
                    if repeat_count >= 2:
                        return (
                            last_tool_result
                            if last_tool_result
                            else "ERROR: repeated tool-call loop detected"
                        )
                    self._debug_tool(name, args)
                    result = self.run_tool(name, args)
                    last_tool_result = result
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": result,
                        }
                    )
                continue

            content = getattr(message, "content", "") or ""
            self.messages.append({"role": "assistant", "content": content})
            return content

        if last_tool_result:
            return last_tool_result
        return "ERROR: tool loop exceeded"

    def handle_slash_command(self, user_input: str) -> str:
        """Execute manual tool command and store result in context for later questions.

        >>> c = Chat(client=object())
        >>> c.handle_slash_command('/ls ..')
        'ERROR: unsafe path'
        >>> c.handle_slash_command('/grep hello *.md') in ('', 'README.md:hello')
        True
        >>> c.handle_slash_command('/')
        'ERROR: empty command'
        >>> c.handle_slash_command('/cat')
        'USAGE: /cat <path>'
        >>> c.handle_slash_command('/grep a')
        'USAGE: /grep <regex> <path_or_glob>'
        >>> c.handle_slash_command('/calculate')
        'USAGE: /calculate <expression>'
        >>> c2 = Chat(client=object())
        >>> c2.handle_slash_command('/compact')
        'No prior context to summarize.'
        >>> c.handle_slash_command('/bogus')
        'ERROR: unknown command /bogus'
        """
        command_line = user_input[1:].strip()
        if not command_line:
            return "ERROR: empty command"

        parts = shlex.split(command_line)
        command = parts[0]
        params = parts[1:]

        if command == "ls":
            path = params[0] if params else "."
            self._debug_tool("ls", {"path": path})
            result = run_ls(path)
        elif command == "cat":
            if len(params) != 1:
                return "USAGE: /cat <path>"
            self._debug_tool("cat", {"path": params[0]})
            result = run_cat(params[0])
        elif command == "grep":
            if len(params) != 2:
                return "USAGE: /grep <regex> <path_or_glob>"
            self._debug_tool("grep", {"pattern": params[0], "path": params[1]})
            result = run_grep(params[0], params[1])
        elif command == "calculate":
            if not params:
                return "USAGE: /calculate <expression>"
            expression = " ".join(params)
            self._debug_tool("calculate", {"expression": expression})
            result = run_calculate(expression)
        elif command == "compact":
            if params:
                return "USAGE: /compact"
            self._debug_tool("compact", {})
            result = self.compact_messages()
        else:
            return f"ERROR: unknown command /{command}"

        self.messages.append({"role": "user", "content": f"/{command_line}"})
        self.messages.append({"role": "assistant", "content": result})
        return result


def repl(
    client: Any | None = None,
    provider: str = "groq",
    debug: bool = False,
) -> None:
    """Run terminal loop and route slash commands directly to tools.

    >>> def monkey_input(prompt, items=['/calculate 2+2']):
    ...     try:
    ...         x = items.pop(0)
    ...         print(f"{prompt}{x}")
    ...         return x
    ...     except IndexError:
    ...         raise KeyboardInterrupt
    >>> import builtins
    >>> old_input = builtins.input
    >>> builtins.input = monkey_input
    >>> repl(client=object())
    chat> /calculate 2+2
    4
    <BLANKLINE>
    >>> builtins.input = old_input
    >>> def monkey_input2(prompt, items=['hello']):
    ...     try:
    ...         x = items.pop(0)
    ...         print(f"{prompt}{x}")
    ...         return x
    ...     except IndexError:
    ...         raise KeyboardInterrupt
    >>> old_send = Chat.send_message
    >>> Chat.send_message = lambda self, msg: "ECHO:" + msg
    >>> builtins.input = monkey_input2
    >>> repl(client=object())
    chat> hello
    ECHO:hello
    <BLANKLINE>
    >>> builtins.input = old_input
    >>> Chat.send_message = old_send
    """
    import readline  # noqa: F401

    chat = Chat(client=client, provider=provider, debug=debug)
    try:
        while True:
            user_input = input("chat> ")
            if user_input.startswith("/"):
                print(chat.handle_slash_command(user_input))
            else:
                print(chat.send_message(user_input))
    except (KeyboardInterrupt, EOFError):
        print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the chat CLI.

    >>> ns = parse_args(["--debug", "--provider", "google", "hello"])
    >>> (ns.debug, ns.provider, ns.message)
    (True, 'google', 'hello')
    """
    parser = argparse.ArgumentParser(description="Chat with local documents using tool-calling.")
    parser.add_argument("message", nargs="?", help="Optional one-shot message to send.")
    parser.add_argument("--debug", action="store_true", help="Print tool calls as they happen.")
    parser.add_argument(
        "--provider",
        choices=sorted(PROVIDER_MODELS.keys()),
        default="groq",
        help="LLM provider backend (default: groq).",
    )
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None, client: Any | None = None) -> int:
    """Run CLI entrypoint for either one-shot mode or interactive REPL mode.

    >>> run_cli(["/calculate 4*5"], client=object())
    20
    0
    >>> run_cli(["--debug", "/calculate 2+3"], client=object())
    [tool] /calculate 2+3
    5
    0
    """
    args = parse_args(argv)
    chat = Chat(client=client, provider=args.provider, debug=args.debug)

    if args.message is not None:
        if args.message.startswith("/"):
            print(chat.handle_slash_command(args.message))
        else:
            print(chat.send_message(args.message))
        return 0

    repl(client=client, provider=args.provider, debug=args.debug)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
