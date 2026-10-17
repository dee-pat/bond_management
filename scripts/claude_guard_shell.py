"""Scanner for the bounded grammar in docs/specs/claude-guard-shell-policy.md."""

import re
import string
from dataclasses import dataclass

NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SAFE = frozenset(string.ascii_letters + string.digits + "_./:=,@%+-")
MAX_INPUT = 65536
MAX_TOKENS = 4096


class UnsupportedShell(ValueError):
    """Input is outside the declared grammar; messages must never contain input."""


@dataclass(frozen=True)
class Token:
    value: str
    kind: str = "word"
    references: tuple[str, ...] = ()
    glob: bool = False
    assignment: bool = False


@dataclass(frozen=True)
class Command:
    words: tuple[Token, ...]
    targets: tuple[Token, ...]


def bounded_text(text, allowed_controls=""):
    return len(text) <= MAX_INPUT and all(
        ord(char) != 127 and (ord(char) >= 32 or char in allowed_controls) for char in text
    )


def commands(text):
    found, current, pending = [], [], False
    for token in Scanner(text).scan():
        if token.kind != "separator":
            current.append(token)
            continue
        if current:
            found.append(_command(current))
            current = []
        elif token.value == "\n":
            continue
        else:
            raise UnsupportedShell("Missing command")
        pending = token.value in ("&&", "||", "|")
    if current:
        found.append(_command(current))
    elif pending:
        raise UnsupportedShell("Missing command")
    return found


def _command(tokens):
    words, targets, index = [], [], 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if token.kind == "word":
            words.append(token)
            continue
        if index == len(tokens) or tokens[index].kind != "word":
            raise UnsupportedShell("Missing redirection target")
        target = tokens[index]
        index += 1
        if token.value.endswith("&"):
            if target.references or target.glob or not re.fullmatch(r"[0-9]+|-", target.value):
                raise UnsupportedShell("Invalid descriptor target")
        else:
            targets.append(target)
    return Command(tuple(words), tuple(targets))


class Scanner:
    def __init__(self, text):
        if not bounded_text(text, allowed_controls="\t\n"):
            raise UnsupportedShell("Input limit or control character")
        self.text = text
        self.index = 0
        self.tokens = []
        self.parts, self.references = [], []
        self.glob, self.plain = False, True
        self.assignment = False

    def scan(self):
        while self.index < len(self.text):
            char = self.text[self.index]
            if char in " \t":
                self._end_word()
                self.index += 1
            elif char == "\\":
                self._escape()
            elif char == "'" or self.text.startswith("$'", self.index):
                self._literal_quote(ansi=char == "$")
            elif self.text.startswith('$"', self.index):
                raise UnsupportedShell("Locale-dependent quotes")
            elif char == '"':
                self._double_quote()
            elif char == "$":
                self._parameter()
            elif char == "#":
                if self.parts:
                    self.parts.append(char)
                    self.index += 1
                else:
                    end = self.text.find("\n", self.index)
                    self.index = len(self.text) if end < 0 else end
            elif char in "<>":
                self._redirection()
            elif char in ";\n&|":
                self._separator()
            elif char == "=" and self.plain:
                prefix = "".join(self.parts)
                if NAME.fullmatch(prefix):
                    self.assignment = True
                elif prefix.endswith("+") and NAME.fullmatch(prefix[:-1]):
                    raise UnsupportedShell("Append assignment")
                self.parts.append(char)
                self.index += 1
            elif char in "*?" or char in SAFE:
                self.parts.append(char)
                self.glob |= char in "*?"
                self.index += 1
            else:
                raise UnsupportedShell("Unsupported active punctuation")
        self._end_word()
        return self.tokens

    def _emit(self, token):
        self.tokens.append(token)
        if len(self.tokens) > MAX_TOKENS:
            raise UnsupportedShell("Token limit")

    def _end_word(self):
        if self.parts:
            self._emit(
                Token(
                    "".join(self.parts),
                    references=tuple(self.references),
                    glob=self.glob,
                    assignment=self.assignment,
                )
            )
        self.parts, self.references = [], []
        self.glob, self.plain = False, True
        self.assignment = False

    def _literal_quote(self, ansi=False):
        start = self.index + (2 if ansi else 1)
        end = self.text.find("'", start)
        if end < 0:
            raise UnsupportedShell("Unterminated quote")
        literal = self.text[start:end]
        if ansi and "\\" in literal:
            raise UnsupportedShell("ANSI-C escape")
        self.parts.append(literal)
        self.plain = False
        self.index = end + 1

    def _double_quote(self):
        self.parts.append("")
        self.plain = False
        self.index += 1
        while self.index < len(self.text):
            char = self.text[self.index]
            if char == '"':
                self.index += 1
                return
            if char == "\\":
                self._escape(quoted=True)
            elif char == "$":
                self._parameter(quoted=True)
            elif char == "`":
                raise UnsupportedShell("Command substitution")
            else:
                self.parts.append(char)
                self.index += 1
        raise UnsupportedShell("Unterminated quote")

    def _escape(self, quoted=False):
        if self.index + 1 == len(self.text):
            raise UnsupportedShell("Dangling escape")
        char = self.text[self.index + 1]
        if quoted and char not in '$`"\\\n':
            self.parts.append("\\")
            self.index += 1
            return
        if char != "\n":
            self.parts.append(char)
            self.plain = False
        self.index += 2

    def _parameter(self, quoted=False):
        start = self.index
        if self.text.startswith("${", start):
            end = self.text.find("}", start + 2)
            name = self.text[start + 2 : end] if end >= 0 else ""
            if not NAME.fullmatch(name):
                raise UnsupportedShell("Unsupported parameter expansion")
            self.index = end + 1
        else:
            match = NAME.match(self.text, start + 1)
            if not match:
                following = self.text[start + 1 : start + 2]
                if not quoted or following in "0123456789@*#?!$-(":
                    raise UnsupportedShell("Unsupported expansion")
                self.parts.append("$")
                self.index += 1
                return
            name = match[0]
            self.index = match.end()
        self.parts.append(self.text[start : self.index])
        self.references.append(name)
        self.plain = False

    def _separator(self):
        self._end_word()
        char = self.text[self.index]
        pair = self.text[self.index : self.index + 2]
        if pair == ";;" or (char == "&" and pair != "&&"):
            raise UnsupportedShell("Unsupported command operator")
        value = pair if pair in ("&&", "||") else char
        self._emit(Token(value, "separator"))
        self.index += len(value)

    def _redirection(self):
        prefix = "".join(self.parts)
        if self.plain and prefix and prefix.isascii() and prefix.isdecimal():
            self.parts = []
        else:
            prefix = ""
        self._end_word()
        pair = self.text[self.index : self.index + 2]
        if pair in ("<<", "<(", ">("):
            raise UnsupportedShell("Unsupported redirection")
        value = pair if pair in (">>", ">&", "<&") else pair[0]
        self._emit(Token(prefix + value, "redirect"))
        self.index += len(value)
