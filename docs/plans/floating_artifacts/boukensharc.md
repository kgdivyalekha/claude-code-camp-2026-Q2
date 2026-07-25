# Floating artifact: `~/.boukensharc`

> **Resolved.** Option 1 below ("Restore YAML support in step 10+ loaders")
> has been implemented: `10_standard_tool_library/lib/boukensha_loader.rb`
> now parses `~/.boukensharc` with `YAML.safe_load`, accepts both the step-9
> `boukensha_path:`/`boukensha_dir:` mapping and the pre-step-9 bare-path
> string, and rescues `Psych::SyntaxError` with a clear message instead of
> silently mis-parsing a multi-line file. The narrative below (the buggy
> `File.read(rc).strip`-only loader) describes the state that led to this
> decision, not the current code — kept for context on why option 1 was
> chosen. See the current `lib/boukensha_loader.rb` for the actual contract.

## What makes it "floating"

Step 9 built real functionality: a YAML `~/.boukensharc` with `boukensha_path:`
and `boukensha_dir:` keys, plus explicit backward compatibility for the
older bare-string format. That's a deliberate feature with a migration path
already thought through.

Step 10's `lib/boukensha_loader.rb` was rewritten for the MCP tool-library
refactor, and in that rewrite the YAML/`boukensha_dir` support **wasn't
carried forward** — not removed on purpose, just not reimplemented. The
capability is "floating": it exists in step 9's code, has no home in step
10 or any step after it, and nothing marks it as intentionally dropped
versus accidentally lost. Each step directory is a standalone snapshot, so
there's no diff or changelog forcing someone to notice a prior step's logic
didn't make it into the next one.

`~/.boukensharc` living in `$HOME` is just what makes the gap *visible* —
a dev machine that ran step 9 has an rc file in the format step 9 taught,
and step 10's loader was never built to understand it. The bug isn't about
the file's location; it's that step 10 doesn't contain logic step 9 already
proved out.

## The two incompatible formats

### Step 9 (`09_global_executable/lib/boukensha_loader.rb`) — YAML mapping

Introduced `boukensha_dir:` alongside `boukensha_path:`, parsed as YAML:

```yaml
boukensha_path: ~/Sites/boukensha/09_global_executable
boukensha_dir: ~/projects/mybot/.boukensha
```

`load_rc` calls `YAML.safe_load`, and explicitly keeps backward compatibility
for a bare string (the pre-step-9 format):

```ruby
case parsed
when Hash   then parsed
when String then { "boukensha_path" => parsed }   # old format
when nil    then {}
end
```

### Step 10 (`10_standard_tool_library/lib/boukensha_loader.rb`) — bare path string

Step 10's loader was rewritten and **dropped YAML parsing entirely**. It
expects the file to contain nothing but a single path:

```ruby
rc = File.expand_path("~/.boukensharc")
if File.exist?(rc)
  dir = File.read(rc).strip
  ...
```

There is no `boukensha_dir` concept in this rc file anymore — config-dir
selection moved to the `BOUKENSHA_DIR` env var only. Critically, there is
also no format detection: `File.read(rc).strip` happily swallows a
multi-line YAML file as if it were one (very long, invalid) path string.

The **installed gem** (`boukensha-0.10.0`, at
`~/.rvm/gems/ruby-4.0.5/gems/boukensha-0.10.0/lib/boukensha_loader.rb`) is
byte-for-byte the step 10 loader — this is what actually runs when you type
`boukensha` at a shell prompt, not whatever step directory you happen to be
sitting in.

## Failure mode observed

A dev machine had `~/.boukensharc` left over from step 9 work:

```
boukensha_path: /home/.../week1_baseline/ruby/10_standard_tool_library
boukensha_dir: /home/.../claude-code-camp-2026-Q2/.boukensha
```

Running `boukensha` (resolving to the installed 0.10.0 gem, i.e. the step 10
loader) produced:

```
boukensha: ~/.boukensharc points to boukensha_path: /home/.../10_standard_tool_library
boukensha_dir: /home/.../claude-code-camp-2026-Q2/.boukensha
       but no lib/boukensha.rb was found there.
       Update ~/.boukensharc or remove it to use the bundled default.
```

The two-line YAML file got read whole and `.strip`ped as a single path.
`File.expand_path` of that multi-line garbage doesn't raise — it just
produces a directory that can't possibly contain `lib/boukensha.rb`, so the
loader aborts. The abort message interpolates the raw (still multi-line)
`dir` value, which is why the error appears to "echo the file back" — that
*is* what got treated as the path.

The `lib/boukensha.rb` step 10 was pointing at genuinely existed on disk;
the file was never the problem. The rc file's **format** was the problem.

## Fix applied (this machine, this incident)

Rewrote `~/.boukensharc` down to the single-line format step 10's loader
expects, and dropped `boukensha_dir` (not supported by that loader — use
`BOUKENSHA_DIR=...` env var instead if a non-default config dir is needed):

```

```

This is a workaround for one machine, not a repo fix — the underlying
contract mismatch between step 9 and step 10 loaders is unchanged.

## What future steps need to do about this

~~Pick one, deliberately, rather than letting it keep drifting~~ — **option 1
was chosen and is implemented** 

1. **Restore YAML support in step 10+ loaders**, keeping the step-9
   `boukensha_path` / `boukensha_dir` keys and the bare-string backward-compat
   branch. This is the only option that doesn't strand step-9-era rc files.
   ✅ **Done** — see `10_standard_tool_library/lib/boukensha_loader.rb`'s
   `load_rc`: `YAML.safe_load` with `Hash` (new mapping) / `String` (legacy
   bare path) / `nil` (absent file) handling, plus a `Psych::SyntaxError`
   rescue with a named-file error message instead of a silent mis-parse.

Options not taken, kept here for the record:

2. Keep step 10's simpler bare-path contract, but make the loader *detect* a
   YAML/multi-line rc file and abort with a message naming the mismatch
   instead of silently mis-parsing it.
3. Document the breaking change explicitly instead of restoring compatibility.

Any Python port of a future loader-equivalent step should follow option 1's
precedent (accept both formats) rather than reintroducing this gap — though
as of `10_standard_tool_library`, Python has no `boukensha_loader.rb` /
`~/.boukensharc` equivalent at all (see that step's README), so this is
forward guidance, not a current gap.

See also: [`docs/plans/floating_artifacts/README.md`](README.md) for the
running list of functionality that a step built but a later step's rewrite
failed to carry forward.