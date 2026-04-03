"""
LLM chat class + REPL.

>>> from types import SimpleNamespace
>>> fake_resp = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))])
>>> fake_client = SimpleNamespace(
...     chat=SimpleNamespace(
...         completions=SimpleNamespace(create=lambda **kwargs: fake_resp)
...     )
... )
>>> c = Chat(client=fake_client)
>>> c.send_message("ping")
'hello'
"""

import os
from groq import Groq
from dotenv import load_dotenv


class Chat:
    def __init__(self, model: str = "llama-3.1-8b-instant", client=None):
        self.model = model
        if client is not None:
            self.client = client
            return

        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GROQ_API_KEY in environment or .env")
        self.client = Groq(api_key=api_key)

    def send_message(self, user_input: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_input},
            ],
            temperature=0,
            max_tokens=200,
        )
        return response.choices[0].message.content


def repl() -> None:
    """
    >>> def monkey_input(prompt, user_inputs=['I am bob.', 'What is my name?']):
    ...     try:
    ...         user_input = user_inputs.pop(0)
    ...         print(f'{prompt}{user_input}')
    ...         return user_input
    ...     except IndexError:
    ...         raise KeyboardInterrupt
    >>> import builtins
    >>> old_input = builtins.input
    >>> old_send = Chat.send_message
    >>> builtins.input = monkey_input
    >>> Chat.send_message = lambda self, msg: f'ECHO: {msg}'
    >>> repl()
    chat> I am bob.
    ECHO: I am bob.
    chat> What is my name?
    ECHO: What is my name?
    <BLANKLINE>
    >>> builtins.input = old_input
    >>> Chat.send_message = old_send
    """
    import readline  # noqa: F401

    chat = Chat()
    try:
        while True:
            user_input = input("chat> ")
            response = chat.send_message(user_input)
            print(response)
    except (KeyboardInterrupt, EOFError):
        print()


if __name__ == "__main__":
    repl()
