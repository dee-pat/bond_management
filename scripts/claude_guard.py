"""Static Bash/Read backstop; see docs/specs/claude-guard-shell-policy.md."""

import json
import re
import sys
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

from claude_guard_shell import Command, UnsupportedShell, commands

PERSISTENT_SITES = {"bond-management-dev.localhost", "bond-management-test.localhost"}
TEMPORARY_SITE = re.compile(r"bond-management-[a-z0-9-]+-[0-9a-f]{32}\.localhost")
DESTRUCTIVE_VERBS = {"drop-site", "trim-database", "trim-tables", "restore", "partial-restore", "reinstall"}
POSITIONAL_SITE_VERBS = {"drop-site", "new-site"}
PROTECTED_FILES = {"site_config.json", "common_site_config.json", "test-browser.env"}
CREDENTIAL_FILE = "test-browser.env"
HOME_CREDENTIAL_PATHS = {
    "$HOME/.config/bond_management/test-browser.env",
    "${HOME}/.config/bond_management/test-browser.env",
}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
SECRET_NAME = re.compile(r"PASSWORD|SECRET|TOKEN|API_KEY", re.IGNORECASE)
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
        if not value or any(ord(char) < 32 for char in value):
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
    source = credential_source(command)
    bench_seen = False
    for word in words:
        bench_seen |= name(word.value) == "bench"
        if word.glob and (bench_seen or ASSIGNMENT.match(word.value)):
            raise UnsupportedShell("Nonliteral bench argument or assignment")
    for word in (*words, *command.targets):
        if any(SECRET_NAME.search(reference) for reference in word.references):
            return "Do not expand secret-named variables."
        if word.references and not source:
            raise UnsupportedShell("Variable expansion")
    if any(protected_names(word) for word in (*words, *command.targets)) and not source:
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
    if program in ("source", ".") and not source:
        return "Only the credential file may be sourced, without extra arguments."
    if program == "set":
        validate_set(arguments)
    if program == "export" and (not arguments or any(not ASSIGNMENT.match(arg) for arg in arguments)):
        return "Only literal export assignments are supported."
    return None


def credential_source(command):
    if command.targets or len(command.words) != 2:
        return False
    program, path = command.words
    if program.value not in ("source", ".") or program.references or program.glob or path.glob:
        return False
    if path.references:
        return path.references == ("HOME",) and path.value in HOME_CREDENTIAL_PATHS
    return name(path.value) == CREDENTIAL_FILE


def protected_names(word):
    pattern = name(word.value)
    return pattern in PROTECTED_FILES or (
        word.glob and any(fnmatchcase(file, pattern) for file in PROTECTED_FILES)
    )


def protected_file_reason():
    return "Protected credential/configuration file; only the exact credential source command is allowed."


def name(word):
    return "." if word == "." else PurePosixPath(word).name.casefold()


def destructive_violation(words):
    for index, word in enumerate(words):
        if name(word) != "bench":
            continue
        arguments = words[index + 1 :]
        verbs = [arg for arg in arguments if arg in DESTRUCTIVE_VERBS | {"new-site"}]
        if not verbs or (verbs == ["new-site"] and "--force" not in arguments):
            continue
        if len(verbs) != 1:
            return "Ambiguous destructive bench command."
        site = site_argument(arguments, verbs[0])
        if site in PERSISTENT_SITES:
            return "Never destroy or overwrite the persistent Bond Management sites."
        if not site or not TEMPORARY_SITE.fullmatch(site):
            return "Destructive bench commands require one literal temporary Bond Management site."
    return None


def site_argument(words, verb):
    sites = []
    for index, word in enumerate(words):
        if word.startswith("--site="):
            sites.append(word.removeprefix("--site="))
        elif word == "--site":
            sites.append(words[index + 1] if index + 1 < len(words) else "")
    if verb in POSITIONAL_SITE_VERBS:
        if sites:
            return None
        after = words[words.index(verb) + 1 :]
        return after[0] if after and not after[0].startswith("-") else None
    return sites[0] if len(sites) == 1 else None


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
