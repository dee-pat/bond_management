"""Claude Code PreToolUse hook: block destructive site commands and secret output.

Reads the hook payload on stdin. Exit status 2 blocks the tool call and shows
stderr to the agent; 0 allows it. The rules mirror docs/verification.md, which
stays the source of truth. The hook fails closed on the forms it recognises,
but it is a backstop: code that runs other code (python -c, eval, scripts) can
always get past it.
"""

import json
import re
import sys
from fnmatch import fnmatchcase
from pathlib import PurePosixPath

PERSISTENT_SITES = {"bond-management-dev.localhost", "bond-management-test.localhost"}
TEMPORARY_SITE = re.compile(r"bond-management-[a-z0-9-]+-[0-9a-f]{32}\.localhost")
DESTRUCTIVE_VERBS = {"drop-site", "trim-database", "trim-tables", "restore", "partial-restore", "reinstall"}
POSITIONAL_SITE_VERBS = {"drop-site", "new-site"}
PROTECTED_FILES = {"site_config.json", "common_site_config.json", "test-browser.env"}
CREDENTIAL_FILE = "test-browser.env"
COMMAND_PREFIXES = {"sudo", "command", "exec", "nohup", "time", "builtin"}
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
SECRET_NAME = re.compile(r"\w*(PASSWORD|SECRET|TOKEN|API_KEY)\w*")
SECRET_REFERENCE = re.compile(r"\$\{?\w*(PASSWORD|SECRET|TOKEN|API_KEY)")
VARIABLE_LISTERS = {"export", "declare", "typeset", "readonly"}
REDIRECTIONS = {"<", ">"}
GLOB_ONLY = re.compile(r"[*?]+")
# Stands in for a $ or backtick that Bash treats as literal (single quotes or
# an escape), so only real expansions read as "$" below.
LITERAL = "\x00"
SEPARATORS = set(";&|\n()")


def segments(command):
    """Split a Bash command into simple commands, each a list of words.

    Quotes are honoured: single-quoted text is literal, while $( ) and
    backticks, bare or inside double quotes, become nested commands of their own.
    """
    found = []
    _scan(command.replace("\\\n", ""), 0, found, closer=None)
    return found


def _scan(text, index, found, closer):
    words, word = [], []

    def end_word():
        if word:
            words.append("".join(word))
            word.clear()

    def end_segment():
        end_word()
        if words:
            found.append(list(words))
            words.clear()

    while index < len(text):
        char = text[index]
        if closer and char == closer:
            end_segment()
            return index + 1
        if char == "\\":
            word.append(text[index + 1 : index + 2].replace("$", LITERAL).replace("`", LITERAL) or "\\")
            index += 2
        elif char == "'":
            end = _find(text, "'", index + 1)
            word.append(text[index + 1 : end].replace("$", LITERAL).replace("`", LITERAL))
            index = end + 1
        elif char == '"':
            index = _scan_double(text, index + 1, word, found)
        elif text.startswith("$(", index):
            index = _scan(text, index + 2, found, closer=")")
            word.append("$")
        elif char == "`":
            end = _find(text, "`", index + 1)
            _scan(text[index + 1 : end], 0, found, closer=None)
            word.append("$")
            index = end + 1
        elif char in " \t":
            end_word()
            index += 1
        elif char in REDIRECTIONS:
            # Redirections are their own words, so `a.json>b` names a.json; a
            # leading file-descriptor number (2>) is dropped.
            if "".join(word).isdigit():
                word.clear()
            end_word()
            words.append(char)
            index += 1
        elif char in SEPARATORS:
            end_segment()
            index += 1
        else:
            word.append(char)
            index += 1
    end_segment()
    return index


def _scan_double(text, index, word, found):
    while index < len(text) and text[index] != '"':
        char = text[index]
        if char == "\\" and text[index + 1 : index + 2] in ('"', "\\", "$", "`"):
            word.append(text[index + 1].replace("$", LITERAL).replace("`", LITERAL))
            index += 2
        elif text.startswith("$(", index):
            index = _scan(text, index + 2, found, closer=")")
            word.append("$")
        elif char == "`":
            end = _find(text, "`", index + 1)
            _scan(text[index + 1 : end], 0, found, closer=None)
            word.append("$")
            index = end + 1
        else:
            word.append(char)
            index += 1
    return index + 1


def _find(text, char, start):
    end = text.find(char, start)
    return len(text) if end < 0 else end


def command_words(words):
    """Drop leading assignments and transparent prefixes such as sudo."""
    while words and (ASSIGNMENT.match(words[0]) or words[0] in COMMAND_PREFIXES):
        words = words[1:]
    return words


def name(word):
    return PurePosixPath(word).name


def split_redirections(words):
    """Separate redirection targets from the command's own words."""
    plain, targets, redirecting = [], [], False
    for word in words:
        if word in REDIRECTIONS:
            redirecting = True
        elif redirecting:
            targets.append(word)
            redirecting = False
        else:
            plain.append(word)
    return plain, targets


def bash_violation(command):
    for words in segments(command):
        plain, targets = split_redirections(words)
        reason = segment_violation(command_words(plain), targets)
        if reason:
            return reason
    return None


def segment_violation(words, targets=()):
    if not words:
        return protected_file_violation(list(targets), ())
    return (
        destructive_violation(words)
        or protected_file_violation(words, targets)
        or environment_violation(words)
    )


def destructive_violation(words):
    if name(words[0]) != "bench":
        return None
    verb = next((word for word in words[1:] if word in DESTRUCTIVE_VERBS | {"new-site"}), None)
    if verb is None or (verb == "new-site" and "--force" not in words):
        return None
    site = site_argument(words, verb)
    if site in PERSISTENT_SITES:
        return "Never drop, trim, restore, reinstall or overwrite the persistent Bond Management sites."
    if not site or not TEMPORARY_SITE.fullmatch(site):
        # Other apps' sites share this bench and need the user's approval.
        return (
            "Destructive bench commands need a literal temporary site named "
            "bond-management-<name>-<32-hex-id>.localhost; ask before touching any other site."
        )
    return None


def site_argument(words, verb):
    for index, word in enumerate(words):
        if word.startswith("--site="):
            return word.removeprefix("--site=")
        if word == "--site" and index + 1 < len(words):
            return words[index + 1]
    if verb in POSITIONAL_SITE_VERBS:
        after = words[words.index(verb) + 1 :]
        return next((word for word in after if not word.startswith("-")), None)
    return None


def protected_names(words):
    """Protected files a word names, literally or through a wildcard such as site_conf*."""
    found = set()
    for word in words:
        pattern = name(word)
        if pattern in PROTECTED_FILES:
            found.add(pattern)
        elif not GLOB_ONLY.fullmatch(pattern):
            found.update(file for file in PROTECTED_FILES if fnmatchcase(file, pattern))
    return found


def protected_file_violation(words, targets):
    names = protected_names([*words, *targets])
    if not names:
        return None
    if words and words[0] in ("source", ".") and names == {CREDENTIAL_FILE}:
        return None
    return "This file holds credentials or site secrets; load test-browser.env with `source` and read nothing else."


def environment_violation(words):
    program, arguments = name(words[0]), words[1:]
    if program == "env":
        index = 0
        while index < len(arguments) and (
            arguments[index].startswith("-") or ASSIGNMENT.match(arguments[index])
        ):
            index += 2 if arguments[index] in ("-u", "--unset", "-C", "--chdir", "-S") else 1
        if index >= len(arguments):
            return "Do not print the environment."
        return segment_violation(command_words(arguments[index:]))
    if program == "printenv":
        return "Do not print the environment."
    if program == "set" and not arguments:
        return "Do not print the environment."
    if program in VARIABLE_LISTERS:
        operands = [arg for arg in arguments if not arg.startswith("-")]
        if not operands:
            return "Do not print the environment."
        if any(SECRET_NAME.fullmatch(operand) for operand in operands if "=" not in operand):
            return "Do not print passwords or tokens."
    if program in ("echo", "printf") and any(SECRET_REFERENCE.search(arg) for arg in arguments):
        return "Do not print passwords or tokens."
    return None


def read_violation(file_path):
    if name(file_path) in PROTECTED_FILES:
        return "This file holds credentials or site secrets; do not read it into the conversation."
    return None


def violation(payload):
    tool_input = payload.get("tool_input") or {}
    if payload.get("tool_name") == "Bash":
        return bash_violation(str(tool_input.get("command", "")))
    if payload.get("tool_name") == "Read":
        return read_violation(str(tool_input.get("file_path", "")))
    return None


def main():
    reason = violation(json.load(sys.stdin))
    if reason:
        print(f"Blocked by scripts/claude_guard.py: {reason} See docs/verification.md.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
