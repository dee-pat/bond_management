# Bounded Claude guard shell policy

## Goal and guarantee

The Bash/Read PreToolUse hook is a conservative, static backstop for accidental
destructive site operations and secret disclosure. It accepts a documented
shell subset, then applies policy to the resulting literal words. It never
executes input, reads variable values, follows files or expands globs.

For accepted Bash input, protected basenames and matching supported glob
patterns are checked in every argument and redirection target, including the
value after the first or last `=` (`if=FILE`, `--opt=FILE`, `NAME=FILE`) and the
tail of a single-dash option (`-fFILE`, `-xfFILE`). Destructive
`bench` words require a literal temporary site in their own command segment.
All `bench` arguments, assignment values and wrapper operands must be literal;
globs cannot be used to hide verbs or change wrapper argument positions.
For `drop-site`/forced `new-site`, the site must immediately follow the verb;
global `--site` selectors cannot be combined with that positional form.
The declared environment-dump commands and shell variable-listing forms are
blocked. Unsupported syntax and malformed payloads
fail closed with exit 2 and a diagnostic that contains no command contents.

This is **not a sandbox or a general Bash interpreter**. Transitive behavior of
external programs, scripts, interpreters,
ambient aliases/functions/PATH/options/environment, filesystem aliases/symlinks, and alternative
secret stores are outside the guarantee. Those need execution/storage controls,
not further syntax exceptions. No claim is made that an arbitrary accepted
program cannot read or output a secret internally.

Bench disclosure and configuration rules are separate from destructive-site
rules: see the [agent safety contract](agent-safety-policy.md#contract).
Disclosure commands are denied even on temporary sites; only the documented
boolean verification flags and password recovery are allowed on test sites.

## Supported syntax

| Form | Contract |
| --- | --- |
| Simple commands | Literal executable and arguments; adjacent quoted/unquoted fragments concatenate. Executable names containing `=` are rejected. Unquoted text is ASCII letters/digits and `_./:=,@%+-`, subject to the grammar below; other literal punctuation must be quoted or escaped. |
| Quotes | Ordinary single/double quotes and ANSI-C quotes without escapes. Single quotes and plain ANSI-C quotes are literal. Double quotes permit Bash's ordinary quote/backslash/dollar escapes. |
| Escapes | Escaped literal characters and line continuations outside single quotes. Unterminated quotes and dangling escapes are rejected. |
| Sequences | `;`, newline, `&&`, `||`, and pipelines `|`; each segment is checked independently. No background execution or compound grammar. |
| Comments | An unquoted `#` at the start of a word is ignored through the newline. Quoted/escaped hashes and hashes inside words are literal. Commands on following lines are checked. |
| Redirections | `<`, `>`, `>>`, optional unquoted numeric descriptors, and `<&`/`>&` with a literal descriptor or `-`. Every file target is checked. Missing targets and other operators are rejected. |
| Globs | Only unquoted `*` and `?`, in arguments/targets, checked conservatively against protected basenames. A bare `*` is blocked because it can include a protected file. Executable and single-dash option globs are rejected. |
| Assignments | Raw unquoted `NAME=` followed by a literal value, alone or before a command; literal assignment arguments after `export`/`env`. Assignment-shaped words are not executable names, and post-wrapper assignments are unsupported. No append assignments, parameter evaluation or variable declarations. |
| Sourcing | Unsupported. Every `source` and `.` command is rejected, and a source of `test-browser.env` is blocked like any other use of a protected file. The former exact credential-source exception was retired in rollout step 2 of the [agent safety policy](agent-safety-policy.md); `scripts/verify.sh ui` loads the browser credentials itself. |
| Shell setup | `set` may toggle only `a`, `e`, `u`, and `o pipefail`; xtrace and environment dumps are rejected. |
| Wrappers | Option-free `command`, `exec`, `nohup`, `time`, `builtin`, `sudo`, `nice`, `xargs`; optional `--`. Additionally `sudo -u USER`/`--user USER`/`--user=USER`, `nice -n INTEGER`, `xargs -n POSITIVE_INTEGER`, and `timeout DURATION` (numeric, optional `s/m/h/d`). Unknown options, missing operands/commands, and nonliteral executable positions are rejected. |
| `env` | Literal assignments followed by a supported command. No options, split strings, or environment-only invocations. Wrapped commands undergo the same checks. |

All other active expansions are unsupported: named/positional/special
parameters; indirect, default, length,
array, substring and replacement parameters; command/arithmetic/process
substitutions; backticks; brace/bracket/extended globs; and tilde expansion.
ANSI-C escapes and locale-dependent quotes are rejected. Here-documents,
here-strings, subshells, groups, functions and shell control structures
are unsupported. Quoted/escaped mentions remain literal, subject to ordinary
protected-basename checks. Shell declaration/introspection and code-evaluation
builtins are rejected; this does not purport to identify every external
interpreter or transitive code-execution mechanism.

## Compatibility and implementation

This deliberately narrows the former heuristic policy: non-secret variable
arguments, substitutions, literal here-strings, harmless brace paths, bare globs,
and undeclared wrapper options are now rejected uniformly. Agent safety policy
step 2 also removed the credential-source exception, so no variable expansion
and no `source` command is accepted. Use literal tool
arguments, supported quoting, or a reviewed project script for work outside the
subset. Previously blocked unsafe regressions must remain blocked.

Keep a standard-library scanner with explicit word/operator tokens and quote,
glob and variable provenance. Separate syntax validation from semantic policy;
do not guess wrapper option arity or emulate additional expansion families.
Validate complete input before allowing any segment. A shared validator bounds
both the Bash command string and Read path to 65,536 characters and rejects
ASCII C0/DEL controls; Bash alone permits tab/newline as grammar or literal text.
Bash is also limited to 4,096 tokens. Reject invalid JSON and wrong runtime types.
The public hook payload and valid-input exit contract remain unchanged: 0
allows, 2 blocks; diagnostics never echo input or secret values.

## Acceptance and verification

The executable matrix covers literals/quotes, escapes, expansions, operators,
redirections, globs, assignments, wrappers, rejected sourcing, shell setup, protected sites/files,
environment disclosure and invalid payloads. Each syntax family has safe literal
counterparts and rejected active forms. Generated cross-products exercise quote
fragments and wrappers around both allowed temporary-site and blocked persistent
operations. Tests pass command text only to the guard, never execute it as Bash.

Run the guard suite and bench-root `verify.sh pre-push`; require green CI on the
fixing commit. Request **one final design review** of this contract, its adequacy,
scanner/policy enforcement and matrix coverage. A concrete P1/P2 contract breach
or material gap in the stated threat model must be fixed; supporting additional
Bash forms is a follow-up, not a condition for acceptance. No automatic chain of
new reviews. No unresolved P1/P2 findings, passing matrix/gates/CI, and the final
review evidence are the stopping criteria.

No application schema, financial rule, API or permission changes. Rollback is a
code revert; no data recovery or migration is needed. `docs/domain-model.md`
was reviewed and its mapped relationships/flows do not change.
