"""Document chat agent with local tools and a terminal REPL.

This file defines the Chat class, tool execution flow, and interactive loop used by the `chat` command.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import shlex
import subprocess
import tempfile
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
from tools.is_path_safe import is_path_safe
from tools.ls_tool import TOOL_SPEC as LS_SPEC
from tools.ls_tool import run_ls
from tools.load_image_tool import TOOL_SPEC as LOAD_IMAGE_SPEC
from tools.load_image_tool import load_image_as_data_url

TOOL_SPECS = [
    CALCULATE_SPEC,
    LS_SPEC,
    CAT_SPEC,
    GREP_SPEC,
    COMPACT_SPEC,
    LOAD_IMAGE_SPEC,
]
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PROVIDER_MODELS = {
    "groq": "llama-3.1-8b-instant",
    "openai": "openai/gpt-5",
    "anthropic": "anthropic/claude-opus-4.6",
    "google": "google/gemini-2.5-pro",
}
VISION_PROVIDER_MODELS = {
    "groq": "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai": "openai/gpt-4.1",
    "anthropic": "anthropic/claude-3.7-sonnet",
    "google": "google/gemini-2.5-pro",
}
SLASH_COMMANDS = ["calculate", "ls", "cat", "grep", "compact", "load_image", "stt", "voice"]


def _is_tool_validation_error(exc: Exception) -> bool:
    """Return True when provider rejected a hallucinated/invalid tool call.

    >>> _is_tool_validation_error(ValueError("x"))
    False
    >>> _is_tool_validation_error(RuntimeError("tool call validation failed"))
    True
    """
    return "tool call validation failed" in str(exc).lower()


def _json_safe(obj: Any) -> Any:
    """Convert SDK objects into JSON-safe nested primitives.

    >>> _json_safe({"a": 1, "b": [2, 3]})
    {'a': 1, 'b': [2, 3]}
    >>> class X:
    ...     def __init__(self):
    ...         self.name = "n"
    >>> _json_safe(X())
    {'name': 'n'}
    >>> _json_safe((1, 2, 3))
    [1, 2, 3]
    >>> class D:
    ...     def model_dump(self):
    ...         return {"k": 9}
    >>> _json_safe(D())
    {'k': 9}
    >>> class BadD:
    ...     def __init__(self):
    ...         self.ok = True
    ...     def model_dump(self):
    ...         raise ValueError("bad")
    >>> _json_safe(BadD())
    {'ok': True}
    >>> isinstance(_json_safe(object()), str)
    True
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, tuple):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        try:
            return _json_safe(obj.model_dump())
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {str(k): _json_safe(v) for k, v in vars(obj).items()}
    return str(obj)


def _path_completion_candidates(prefix: str) -> list[str]:
    """Return sorted path completions for a typed prefix.

    >>> vals = _path_completion_candidates("tools/")
    >>> any(v.startswith("tools/") for v in vals)
    True
    """
    pattern = f"{prefix}*" if prefix else "*"
    matches = sorted(glob.glob(pattern))
    out: list[str] = []
    for match in matches:
        if os.path.isdir(match):
            out.append(match.rstrip("/") + "/")
        else:
            out.append(match)
    return out


def _slash_completion_options(line: str, text: str) -> list[str]:
    """Return completion options for slash commands and file arguments.

    >>> _slash_completion_options("/", "/")
    ['/calculate', '/cat', '/compact', '/grep', '/load_image', '/ls', '/stt', '/voice']
    >>> _slash_completion_options("/l", "/l")
    ['/load_image', '/ls']
    >>> opts = _slash_completion_options("/ls .g", ".g")
    >>> ".git/" in opts or ".git" in opts
    True
    >>> _slash_completion_options("hello", "h")
    []
    >>> _slash_completion_options("/bogus x", "x")
    []
    >>> opts2 = _slash_completion_options("/ls ", "")
    >>> len(opts2) >= 1
    True
    >>> len(_slash_completion_options("/grep dog ", "")) >= 1
    True
    """
    if not line.startswith("/"):
        return []

    body = line[1:]
    parts = body.split()
    if not parts:
        return [f"/{cmd}" for cmd in sorted(SLASH_COMMANDS)]

    # Completing command name.
    if len(parts) == 1 and not line.endswith(" "):
        prefix = parts[0]
        return [f"/{cmd}" for cmd in sorted(SLASH_COMMANDS) if cmd.startswith(prefix)]

    cmd = parts[0]
    if cmd not in {"ls", "cat", "grep", "load_image", "stt"}:
        return []

    if line.endswith(" "):
        current = ""
        arg_index = len(parts) - 1
    else:
        current = text
        arg_index = len(parts) - 2

    if cmd in {"ls", "cat", "load_image", "stt"} and arg_index == 0:
        return _path_completion_candidates(current)
    if cmd == "grep" and arg_index == 1:
        return _path_completion_candidates(current)
    return []


def _build_readline_completer():
    """Create a readline completer function for slash commands.

    >>> comp = _build_readline_completer()
    >>> callable(comp)
    True
    >>> import readline
    >>> old = readline.get_line_buffer
    >>> readline.get_line_buffer = lambda: "/l"
    >>> comp("/l", 0)
    '/load_image'
    >>> comp("/l", 1)
    '/ls'
    >>> comp("/l", 2) is None
    True
    >>> readline.get_line_buffer = old
    """

    def _completer(text: str, state: int) -> str | None:
        import readline

        line = readline.get_line_buffer()
        options = _slash_completion_options(line, text)
        if state < len(options):
            return options[state]
        return None

    return _completer


def _audio_player_command(path: str) -> list[str]:
    """Return a platform-specific command for playing WAV audio.

    >>> _audio_player_command("x.wav")[0] in {"afplay", "aplay", "powershell"}
    True
    >>> old = platform.system
    >>> platform.system = lambda: "Linux"
    >>> _audio_player_command("x.wav")
    ['aplay', 'x.wav']
    >>> platform.system = lambda: "Windows"
    >>> _audio_player_command("x.wav")[0]
    'powershell'
    >>> platform.system = old
    """
    system = platform.system().lower()
    if system == "darwin":
        return ["afplay", path]
    if system == "linux":
        return ["aplay", path]
    return ["powershell", "-c", f"(New-Object Media.SoundPlayer '{path}').PlaySync();"]


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
        speak: bool = False,
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
        self.speak = speak
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
        >>> os.getenv = lambda key, default=None: "gsk_demo" if key == "GROQ_API_KEY" else None
        >>> c3 = Chat(client=None, provider="groq")
        >>> c3.client.__class__.__name__
        'Groq'
        >>> os.getenv = lambda key, default=None: "or_demo" if key == "OPENROUTER_API_KEY" else None
        >>> c4 = Chat(client=None, provider="openai")
        >>> c4.client.__class__.__name__
        'OpenAI'
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
        >>> c.run_tool("load_image", {"path": "../x.png"})
        'ERROR: unsafe path'
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
        if name == "load_image":
            return self.load_image_into_messages(str(args.get("path", "")))
        return f"ERROR: unknown tool: {name}"

    def _debug_tool(self, name: str, args: dict[str, Any]) -> None:
        """Print a debug line showing tool invocation when debug mode is enabled.

        >>> c = Chat(client=object(), debug=False)
        >>> c._debug_tool("ls", {"path": "."})
        >>> c2 = Chat(client=object(), debug=True)
        >>> c2._debug_tool("calculate", {"expression": "1+2"})
        [tool] /calculate 1+2
        >>> c2._debug_tool("ls", {"path": "."})
        [tool] /ls .
        >>> c2._debug_tool("cat", {"path": "README.md"})
        [tool] /cat README.md
        >>> c2._debug_tool("grep", {"pattern": "x", "path": "*.py"})
        [tool] /grep x *.py
        >>> c2._debug_tool("compact", {})
        [tool] /compact
        >>> c2._debug_tool("load_image", {"path": "x.png"})
        [tool] /load_image x.png
        >>> c2._debug_tool("weird", {"a": 1})
        [tool] /weird {'a': 1}
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
        elif name == "load_image":
            print(f"[tool] /load_image {args.get('path', '')}".rstrip())
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
        >>> class EmptySummary:
        ...     def create(self, **kwargs):
        ...         msg = SimpleNamespace(content=None, tool_calls=[])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c2 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=EmptySummary())))
        >>> _ = c2.send_message('hello')
        >>> c2.compact_messages()
        'No prior context to summarize.'
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
        safe_messages = _json_safe(self.messages)
        transcript = json.dumps(safe_messages, ensure_ascii=False)
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

    def load_image_into_messages(self, path: str) -> str:
        """Load a local image and append it to chat context as multimodal content.

        >>> import tempfile, os
        >>> from pathlib import Path
        >>> c = Chat(client=object())
        >>> with tempfile.TemporaryDirectory() as d:
        ...     p = Path(d) / "a.png"
        ...     _ = p.write_bytes(b"\\x89PNG\\r\\n\\x1a\\nabc")
        ...     old = os.getcwd()
        ...     os.chdir(d)
        ...     out = c.load_image_into_messages("a.png")
        ...     os.chdir(old)
        >>> out
        'Loaded image: a.png'
        >>> c.messages[-1]["role"]
        'user'
        >>> c.model == VISION_PROVIDER_MODELS["groq"]
        True
        >>> c.load_image_into_messages("../bad.png")
        'ERROR: unsafe path'
        """
        try:
            data_url = load_image_as_data_url(path)
        except ValueError as exc:
            return f"ERROR: {exc}"

        self.messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Image loaded from {path}"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        )
        # Switch to a vision-capable model after an image is loaded.
        if self.provider in VISION_PROVIDER_MODELS:
            self.model = VISION_PROVIDER_MODELS[self.provider]
        return f"Loaded image: {path}"

    def _groq_audio_client(self) -> Any:
        """Return a Groq client for audio APIs.

        >>> from types import SimpleNamespace
        >>> c = Chat(client=object())
        >>> c._groq_audio_client = lambda: SimpleNamespace(ok=True)
        >>> c._groq_audio_client().ok
        True
        >>> import os
        >>> old = os.getenv
        >>> os.getenv = lambda key: None
        >>> c2 = Chat(client=object())
        >>> try:
        ...     c2._groq_audio_client()
        ... except RuntimeError as e:
        ...     print("Missing GROQ_API_KEY" in str(e))
        True
        >>> os.getenv = old
        """
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GROQ_API_KEY in environment or .env")
        return Groq(api_key=api_key)

    def speech_to_text(self, audio_path: str) -> str:
        """Transcribe an audio file using Groq STT.

        >>> from types import SimpleNamespace
        >>> import tempfile, os
        >>> c = Chat(client=object())
        >>> class FakeTranscriptions:
        ...     def create(self, **kwargs):
        ...         return SimpleNamespace(text="hello from audio")
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(transcriptions=FakeTranscriptions())
        ... )
        >>> with tempfile.TemporaryDirectory() as d:
        ...     f = os.path.join(d, "x.wav")
        ...     _ = open(f, "wb").write(b"RIFF....WAVE")
        ...     old = os.getcwd()
        ...     os.chdir(d)
        ...     out = c.speech_to_text("x.wav")
        ...     os.chdir(old)
        >>> out
        'hello from audio'
        >>> c.speech_to_text("../bad.wav")
        'ERROR: unsafe path'
        >>> c.speech_to_text("missing.wav")
        'ERROR: audio file not found'
        >>> class FakeTranscriptions2:
        ...     def create(self, **kwargs):
        ...         return "plain text transcript"
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(transcriptions=FakeTranscriptions2())
        ... )
        >>> with tempfile.TemporaryDirectory() as d:
        ...     f = os.path.join(d, "x.wav")
        ...     _ = open(f, "wb").write(b"RIFF....WAVE")
        ...     old = os.getcwd()
        ...     os.chdir(d)
        ...     out2 = c.speech_to_text("x.wav")
        ...     os.chdir(old)
        >>> out2
        'plain text transcript'
        >>> class FakeTranscriptions3:
        ...     def create(self, **kwargs):
        ...         return SimpleNamespace(text="")
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(transcriptions=FakeTranscriptions3())
        ... )
        >>> with tempfile.TemporaryDirectory() as d:
        ...     f = os.path.join(d, "x.wav")
        ...     _ = open(f, "wb").write(b"RIFF....WAVE")
        ...     old = os.getcwd()
        ...     os.chdir(d)
        ...     out3 = c.speech_to_text("x.wav")
        ...     os.chdir(old)
        >>> out3
        'ERROR: empty transcript'
        """
        if not is_path_safe(audio_path):
            return "ERROR: unsafe path"
        if not os.path.isfile(audio_path):
            return "ERROR: audio file not found"

        client = self._groq_audio_client()
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
            )

        if isinstance(transcript, str):
            return transcript
        text = getattr(transcript, "text", "")
        return text or "ERROR: empty transcript"

    def text_to_speech(self, text: str, output_path: str | None = None) -> str:
        """Generate WAV speech from text with Groq TTS and return output path.

        >>> from types import SimpleNamespace
        >>> import tempfile, os
        >>> c = Chat(client=object())
        >>> class FakeSpeechResponse:
        ...     def __init__(self, data: bytes):
        ...         self.data = data
        ...     def write_to_file(self, path):
        ...         with open(path, "wb") as f:
        ...             _ = f.write(self.data)
        >>> class FakeSpeech:
        ...     def create(self, **kwargs):
        ...         return FakeSpeechResponse(b"RIFF....WAVE")
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(speech=FakeSpeech())
        ... )
        >>> with tempfile.TemporaryDirectory() as d:
        ...     out = c.text_to_speech("hello", os.path.join(d, "x.wav"))
        ...     os.path.exists(out)
        True
        >>> class FakeSpeechBytes:
        ...     def create(self, **kwargs):
        ...         return b"RIFF....WAVE"
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(speech=FakeSpeechBytes())
        ... )
        >>> out2 = c.text_to_speech("hello")
        >>> os.path.exists(out2)
        True
        >>> class FakeSpeechRead:
        ...     class Resp:
        ...         def read(self):
        ...             return b"RIFF....WAVE"
        ...     def create(self, **kwargs):
        ...         return self.Resp()
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(speech=FakeSpeechRead())
        ... )
        >>> with tempfile.TemporaryDirectory() as d:
        ...     out3 = c.text_to_speech("hello", os.path.join(d, "z.wav"))
        ...     os.path.exists(out3)
        True
        >>> class FakeSpeechBad:
        ...     def create(self, **kwargs):
        ...         return 123
        >>> c._groq_audio_client = lambda: SimpleNamespace(
        ...     audio=SimpleNamespace(speech=FakeSpeechBad())
        ... )
        >>> try:
        ...     c.text_to_speech("hello", "/tmp/w.wav")
        ... except RuntimeError as e:
        ...     print("Unsupported TTS response type" in str(e))
        True
        """
        client = self._groq_audio_client()
        if output_path is None:
            fd, output_path = tempfile.mkstemp(prefix="docchat_", suffix=".wav")
            os.close(fd)

        response = client.audio.speech.create(
            model="playai-tts",
            voice="Aaliyah-PlayAI",
            input=text,
            response_format="wav",
        )

        if hasattr(response, "write_to_file"):
            response.write_to_file(output_path)
        elif isinstance(response, (bytes, bytearray)):
            with open(output_path, "wb") as f:
                _ = f.write(bytes(response))
        elif hasattr(response, "read"):
            with open(output_path, "wb") as f:
                _ = f.write(response.read())
        else:
            raise RuntimeError("Unsupported TTS response type")

        return output_path

    def speak_text(self, text: str) -> str:
        """Generate and play spoken audio for the given text.

        >>> from types import SimpleNamespace
        >>> c = Chat(client=object())
        >>> c.text_to_speech = lambda text: "/tmp/docchat.wav"
        >>> old_run = subprocess.run
        >>> subprocess.run = lambda *a, **k: SimpleNamespace(returncode=0)
        >>> c.speak_text("hello")
        '/tmp/docchat.wav'
        >>> subprocess.run = old_run
        """
        wav_path = self.text_to_speech(text)
        cmd = _audio_player_command(wav_path)
        subprocess.run(cmd, check=False)
        return wav_path

    def record_then_transcribe(self, output_path: str = "recording.wav") -> str:  # pragma: no cover
        """Record microphone audio until Enter and return transcribed text.

        >>> c = Chat(client=object())
        >>> c.record_then_transcribe("/tmp/nope.wav")
        'ERROR: install sounddevice and soundfile for voice recording'
        """
        try:
            import numpy as np
            import sounddevice as sd
            import soundfile as sf
        except Exception:
            return "ERROR: install sounddevice and soundfile for voice recording"

        print("Press Enter to start recording.")
        _ = input("")
        print("Recording... press Enter to stop.")

        chunks: list[Any] = []

        def callback(indata, frames, time_info, status):
            del frames, time_info
            if status:
                pass
            chunks.append(indata.copy())

        with sd.InputStream(samplerate=16000, channels=1, callback=callback):
            _ = input("")

        if not chunks:
            return "ERROR: no audio captured"

        audio = np.concatenate(chunks, axis=0)
        sf.write(output_path, audio, 16000)
        return self.speech_to_text(output_path)

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
        >>> class ValidationFallback:
        ...     def __init__(self):
        ...         self.calls = 0
        ...     def create(self, **kwargs):
        ...         self.calls += 1
        ...         if self.calls == 1:
        ...             raise RuntimeError("tool call validation failed")
        ...         msg = SimpleNamespace(content="fallback ok", tool_calls=[])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c5 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=ValidationFallback())))
        >>> c5.send_message("x")
        'fallback ok'
        >>> class LoopNoResult:
        ...     def create(self, **kwargs):
        ...         func = SimpleNamespace(name='grep', arguments='{"pattern":"z","path":"__no_match__*.txt"}')
        ...         tc = SimpleNamespace(id='n1', function=func)
        ...         msg = SimpleNamespace(content=None, tool_calls=[tc])
        ...         return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        >>> c6 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=LoopNoResult())))
        >>> c6.send_message("loop", max_rounds=1)
        'ERROR: tool loop exceeded'
        >>> class HardFail:
        ...     def create(self, **kwargs):
        ...         raise RuntimeError("boom")
        >>> c7 = Chat(client=SimpleNamespace(chat=SimpleNamespace(completions=HardFail())))
        >>> try:
        ...     c7.send_message("x")
        ... except RuntimeError as e:
        ...     print(str(e))
        boom
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
        >>> c2.handle_slash_command('/compact now')
        'USAGE: /compact'
        >>> c2.handle_slash_command('/load_image')
        'USAGE: /load_image <path>'
        >>> c2.handle_slash_command('/stt')
        'USAGE: /stt <audio_path>'
        >>> import tempfile
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as d:
        ...     p = Path(d) / "note.txt"
        ...     _ = p.write_text("hi", encoding="utf-8")
        ...     old = os.getcwd()
        ...     os.chdir(d)
        ...     out = c2.handle_slash_command('/cat note.txt')
        ...     os.chdir(old)
        >>> out
        'hi'
        >>> with tempfile.TemporaryDirectory() as d:
        ...     p = Path(d) / "img.png"
        ...     _ = p.write_bytes(b"\\x89PNG\\r\\n\\x1a\\nabc")
        ...     old = os.getcwd()
        ...     os.chdir(d)
        ...     out2 = c2.handle_slash_command('/load_image img.png')
        ...     os.chdir(old)
        >>> out2
        'Loaded image: img.png'
        >>> c2.speech_to_text = lambda p: "transcribed"
        >>> c2.handle_slash_command('/stt audio.wav')
        'transcribed'
        >>> c2.record_then_transcribe = lambda: "hello from mic"
        >>> c2.send_message = lambda msg: "ECHO:" + msg
        >>> c2.handle_slash_command('/voice')
        'ECHO:hello from mic'
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
        elif command == "load_image":
            if len(params) != 1:
                return "USAGE: /load_image <path>"
            self._debug_tool("load_image", {"path": params[0]})
            result = self.load_image_into_messages(params[0])
        elif command == "stt":
            if len(params) != 1:
                return "USAGE: /stt <audio_path>"
            result = self.speech_to_text(params[0])
        elif command == "voice":
            if params:
                return "USAGE: /voice"
            transcript = self.record_then_transcribe()
            if transcript.startswith("ERROR:"):
                return transcript
            self.messages.append({"role": "user", "content": transcript})
            result = self.send_message(transcript)
        else:
            return f"ERROR: unknown command /{command}"

        self.messages.append({"role": "user", "content": f"/{command_line}"})
        self.messages.append({"role": "assistant", "content": result})
        return result


def repl(
    client: Any | None = None,
    provider: str = "groq",
    debug: bool = False,
    speak: bool = False,
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
    >>> def monkey_input3(prompt, items=['/calculate 1+1', 'hi']):
    ...     try:
    ...         x = items.pop(0)
    ...         print(f"{prompt}{x}")
    ...         return x
    ...     except IndexError:
    ...         raise KeyboardInterrupt
    >>> old_speak = Chat.speak_text
    >>> Chat.send_message = lambda self, msg: "OK"
    >>> Chat.speak_text = lambda self, text: (_ for _ in ()).throw(RuntimeError("audio down"))
    >>> builtins.input = monkey_input3
    >>> repl(client=object(), speak=True)
    chat> /calculate 1+1
    2
    (tts error) audio down
    chat> hi
    OK
    (tts error) audio down
    <BLANKLINE>
    >>> builtins.input = old_input
    >>> Chat.send_message = old_send
    >>> Chat.speak_text = old_speak
    """
    import readline

    chat = Chat(client=client, provider=provider, debug=debug, speak=speak)
    readline.parse_and_bind("tab: complete")
    readline.set_completer_delims(" \t\n")
    readline.set_completer(_build_readline_completer())
    try:
        while True:
            user_input = input("chat> ")
            if user_input.startswith("/"):
                reply = chat.handle_slash_command(user_input)
                print(reply)
                if chat.speak and not reply.startswith("ERROR:"):
                    try:
                        _ = chat.speak_text(reply)
                    except Exception as exc:
                        print(f"(tts error) {exc}")
            else:
                reply = chat.send_message(user_input)
                print(reply)
                if chat.speak and not reply.startswith("ERROR:"):
                    try:
                        _ = chat.speak_text(reply)
                    except Exception as exc:
                        print(f"(tts error) {exc}")
    except (KeyboardInterrupt, EOFError):
        print()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the chat CLI.

    >>> ns = parse_args(["--debug", "--speak", "--provider", "google", "hello"])
    >>> (ns.debug, ns.speak, ns.provider, ns.message)
    (True, True, 'google', 'hello')
    """
    parser = argparse.ArgumentParser(description="Chat with local documents using tool-calling.")
    parser.add_argument("message", nargs="?", help="Optional one-shot message to send.")
    parser.add_argument("--debug", action="store_true", help="Print tool calls as they happen.")
    parser.add_argument("--speak", action="store_true", help="Read assistant replies aloud with TTS.")
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
    >>> old_send = Chat.send_message
    >>> Chat.send_message = lambda self, msg: "OK:" + msg
    >>> run_cli(["hello"], client=object())
    OK:hello
    0
    >>> old_speak = Chat.speak_text
    >>> Chat.speak_text = lambda self, text: "/tmp/fake.wav"
    >>> run_cli(["--speak", "hello"], client=object())
    OK:hello
    0
    >>> Chat.speak_text = lambda self, text: (_ for _ in ()).throw(RuntimeError("tts broke"))
    >>> run_cli(["--speak", "hello"], client=object())
    OK:hello
    (tts error) tts broke
    0
    >>> Chat.speak_text = old_speak
    >>> Chat.send_message = old_send
    """
    args = parse_args(argv)
    chat = Chat(
        client=client,
        provider=args.provider,
        debug=args.debug,
        speak=args.speak,
    )

    if args.message is not None:
        if args.message.startswith("/"):
            reply = chat.handle_slash_command(args.message)
        else:
            reply = chat.send_message(args.message)
        print(reply)
        if chat.speak and not reply.startswith("ERROR:"):
            try:
                _ = chat.speak_text(reply)
            except Exception as exc:
                print(f"(tts error) {exc}")
        return 0

    repl(client=client, provider=args.provider, debug=args.debug, speak=args.speak)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
