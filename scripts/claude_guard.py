"""Static Bash/Read backstop; see docs/specs/claude-guard-shell-policy.md."""

import importlib.util
import json
import re
import sys
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from claude_guard_shell import Command, UnsupportedShell, bounded_text, commands


def load_policy():
    # By file path, so the hook never runs bond_management package init.
    path = Path(__file__).resolve().parent.parent / "bond_management" / "agent_policy.py"
    spec = importlib.util.spec_from_file_location("bond_management_agent_policy", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent_policy = load_policy()
PROTECTED_FILES = agent_policy.PROTECTED_FILES
SECRET_NAME = agent_policy.SECRET_NAME
destructive_violation = agent_policy.destructive_site_violation
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"sudo", "command", "exec", "nohup", "time", "builtin", "timeout", "nice", "xargs"}
UNSUPPORTED_COMMANDS = {
    "if",
    "then",
    "elif",
    "else",
    "fi",
    "for",
    "while",
    "until",
    "do",
    "done",
    "case",
    "esac",
    "in",
    "select",
    "function",
    "coproc",
    "eval",
    "alias",
    "unalias",
    "trap",
    "let",
    "local",
    "declare",
    "typeset",
    "readonly",
    "shopt",
    "enable",
    "history",
    "fc",
    "read",
    "readarray",
    "mapfile",
}


def violation(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("tool_name"), str):
        return "Invalid hook payload."
    tool = payload["tool_name"]
    if tool not in ("Bash", "Read"):
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return "Invalid hook payload."
    value = tool_input.get("command" if tool == "Bash" else "file_path")
    if not isinstance(value, str):
        return "Invalid tool input."
    if tool == "Read":
        if not value or not bounded_text(value):
            return "Invalid file path."
        return protected_file_reason() if name(value) in PROTECTED_FILES else None
    try:
        parsed = commands(value)
        for command in parsed:
            reason = command_violation(command)
            if reason:
                return reason
    except UnsupportedShell:
        return "Unsupported shell syntax; use literal arguments or a reviewed project script."
    return None


def command_violation(command: Command):
    words = command.words
    bench_seen = False
    for word in words:
        bench_seen |= name(word.value) == "bench"
        if word.glob and (bench_seen or ASSIGNMENT.match(word.value) or short_option(word.value)):
            raise UnsupportedShell("Nonliteral bench argument, assignment or short option")
    for word in (*words, *command.targets):
        if any(SECRET_NAME.search(reference) for reference in word.references):
            return "Do not expand secret-named variables."
        if word.references:
            raise UnsupportedShell("Variable expansion")
    if any(protected_names(word) for word in (*words, *command.targets)):
        return protected_file_reason()
    if any(name(word.value) == "printenv" for word in words):
        return "Do not print the environment."
    reason = destructive_violation([word.value for word in words])
    if reason:
        return reason
    index = executable_index(words)
    if index == len(words):
        return None
    program = name(words[index].value)
    arguments = [word.value for word in words[index + 1 :]]
    if program in UNSUPPORTED_COMMANDS:
        raise UnsupportedShell("Unsupported shell command")
    if program in ("source", "."):
        return "Do not source files; scripts/verify.sh loads browser credentials itself."
    if program == "set":
        validate_set(arguments)
    if program == "export" and (not arguments or any(not ASSIGNMENT.match(arg) for arg in arguments)):
        return "Only literal export assignments are supported."
    return None


def protected_names(word):
    base = name(word.value)
    # Option and assignment values name files too: if=FILE, --opt=FILE, -fFILE.
    patterns = {base, base.partition("=")[2], base.rpartition("=")[2]}
    if short_option(base) and base.endswith(tuple(PROTECTED_FILES)):
        return True
    return any(
        pattern in PROTECTED_FILES
        or (word.glob and any(fnmatchcase(file, pattern) for file in PROTECTED_FILES))
        for pattern in patterns
        if pattern
    )


def short_option(value):
    return value.startswith("-") and not value.startswith("--")


def protected_file_reason():
    return "Protected credential/configuration file."


def name(word):
    return "." if word == "." else PurePosixPath(word).name.casefold()


def executable_index(words):
    index = 0
    while index < len(words) and words[index].assignment:
        index += 1
    while index < len(words):
        word = words[index]
        if word.references or word.glob or not word.value or word.value.startswith("-") or "=" in word.value:
            raise UnsupportedShell("Nonliteral or missing executable")
        program = name(word.value)
        if program == "env":
            index += 1
            while index < len(words) and ASSIGNMENT.match(words[index].value):
                index += 1
            if index == len(words):
                raise UnsupportedShell("Environment dump")
            continue
        if program not in WRAPPERS:
            return index
        index = wrapper_command(words, index, program)
    return index


def wrapper_command(words, index, program):
    start = index
    index += 1
    terminated = index < len(words) and words[index].value == "--"
    if terminated:
        index += 1
    if program == "timeout":
        if index == len(words) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?[smhd]?", words[index].value):
            raise UnsupportedShell("Invalid duration")
        index += 1
    elif not terminated and program == "sudo":
        if index < len(words) and words[index].value.startswith("--user="):
            if not words[index].value.removeprefix("--user="):
                raise UnsupportedShell("Missing wrapper operand")
            index += 1
        elif index < len(words) and words[index].value in ("-u", "--user"):
            index = operand(words, index, r"[^-].*")
    elif (
        not terminated and program in ("nice", "xargs") and index < len(words) and words[index].value == "-n"
    ):
        index = operand(words, index, r"-?[0-9]+" if program == "nice" else r"[1-9][0-9]*")
    if not terminated and index < len(words) and words[index].value == "--":
        index += 1
    if index == len(words) or words[index].value.startswith("-"):
        raise UnsupportedShell("Unsupported wrapper option or missing command")
    if any(word.glob for word in words[start:index]):
        raise UnsupportedShell("Nonliteral wrapper operand")
    return index


def operand(words, index, pattern):
    if index + 1 == len(words) or not re.fullmatch(pattern, words[index + 1].value):
        raise UnsupportedShell("Invalid wrapper operand")
    return index + 2


def validate_set(arguments):
    if not arguments:
        raise UnsupportedShell("Environment dump")
    index = 0
    while index < len(arguments):
        option = arguments[index]
        if len(option) < 2 or option[0] not in "+-" or any(c not in "aeuo" for c in option[1:]):
            raise UnsupportedShell("Unsupported shell setup")
        if "o" in option[1:]:
            if (
                option.count("o") != 1
                or not option.endswith("o")
                or index + 1 == len(arguments)
                or arguments[index + 1] != "pipefail"
            ):
                raise UnsupportedShell("Unsupported shell setup")
            index += 1
        index += 1


def main():
    try:
        reason = violation(json.load(sys.stdin))
    except (ValueError, TypeError, RecursionError):
        reason = "Invalid hook payload."
    if reason:
        print(f"Blocked by scripts/claude_guard.py: {reason} See docs/verification.md.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
