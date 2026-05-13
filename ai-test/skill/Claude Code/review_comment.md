---
name: pr-review-with-issue
description: >
  Reviews a GitHub Pull Request by cross-referencing it against the linked issue requirements.
  Use this skill whenever the user asks to review a PR, wants code review on a pull request,
  mentions a GitHub PR URL, or says things like "review this PR", "/review", "look at this pull request",
  "check this PR against the issue", or "give feedback on these changes". Also trigger when
  the user provides a GitHub URL containing "/pull/". Produces inline diff comments posted
  directly to GitHub covering: requirements vs implementation gaps, test coverage completeness,
  code correctness bugs, and optimization suggestions.
---

# PR Review with Issue Cross-Reference

You are conducting a thorough GitHub PR review, posting inline comments directly onto the diff lines where issues are found, and a general comment for anything that cannot be tied to a specific line.

## Step 1 -- Parse the PR URL

Extract `owner`, `repo`, and `pr_number` from the URL the user provided.

Examples:
- `https://github.com/acme/myrepo/pull/42` -> owner=`acme`, repo=`myrepo`, pr_number=`42`
- `https://github.com/acme/myrepo/pull/42/changes` -> same

## Step 2 -- Fetch PR data

Run these PowerShell commands using the full path to gh (it may not be in PATH):

```powershell
$gh = "C:\Program Files\GitHub CLI\gh.exe"

# PR metadata (title, body, author, head SHA)
& $gh pr view <pr_number> --repo <owner>/<repo>

# Full diff
& $gh pr diff <pr_number> --repo <owner>/<repo>

# Head commit SHA (needed for inline comments)
& $gh api repos/<owner>/<repo>/pulls/<pr_number> --jq '.head.sha'

# File list with patches (for position counting)
& $gh api repos/<owner>/<repo>/pulls/<pr_number>/files
```

## Step 3 -- Find and fetch the linked issue

Scan the PR title and body for an issue reference. Common patterns:
- `#123`, `Closes #123`, `Fixes #123`, `Resolves #123`
- A full GitHub issue URL: `https://github.com/owner/repo/issues/123`

If found, fetch it:
```powershell
& $gh issue view <issue_number> --repo <owner>/<repo>
```

If no issue is found, skip the requirements-comparison section and focus only on code quality.

## Step 4 -- Analyze the changes

Read the diff carefully against the issue requirements. Produce findings across four dimensions:

### A. Requirements Understanding
Compare what the issue asked for vs what was actually implemented. Flag:
- Features specified in the issue that are missing entirely
- Behaviours described in the issue that are implemented incorrectly
- Spec details (edge cases, formats, constraints) that were overlooked

### B. Test Coverage
Check whether tests exist and whether they are complete:
- Are there tests for the happy path?
- Are edge cases and boundary values covered?
- Are there tests for every public API method/property specified?
- Are any test files empty or stub-only?

### C. Code Correctness
Identify actual bugs -- logic errors, wrong calculations, wrong API calls, crashes:
- Incorrect output for valid inputs
- Runtime errors (undefined references, type mismatches)
- Module system inconsistencies (e.g. mixing CommonJS and ES modules)
- Off-by-one errors, wrong math, incorrect flag usage

### D. Optimisation & Style
Point out things that don't affect correctness but make the code worse:
- Dead code / no-ops (assignments whose value is immediately discarded)
- Confusing naming (parameter shadows method name, misleading variable names)
- Unnecessary flags on regex, redundant conditions
- Style violations (indentation, missing EOF newline, trailing whitespace)

## Step 5 -- Calculate diff positions line by line

For every finding that points to a specific line of code, you must determine its **position** in the diff before you can post an inline comment. Do this methodically -- wrong positions cause GitHub to reject the entire review with HTTP 422.

### How to count positions

Fetch the raw patch for each file:
```powershell
& $gh api repos/<owner>/<repo>/pulls/<pr_number>/files | ConvertFrom-Json | Select-Object filename, patch
```

Then count through the patch string **line by line**:

| Line type | Counts? |
|---|---|
| `@@ ... @@` hunk header | NO -- resets counter, position 0 |
| `+` added line | YES |
| `-` removed line | YES |
| ` ` context line | YES |
| `\ No newline at end of file` | YES |

The first line immediately below `@@` is **position 1**. Every line after it increments by 1. When a new `@@` appears, reset to 1.

**Worked example:**
```
@@ -0,0 +1,5 @@          <- position 0 (NOT counted)
+import foo from 'bar';  <- position 1
+                        <- position 2
+function greet() {      <- position 3
+  return 'hello';       <- position 4
+}                       <- position 5
\ No newline at end of file  <- position 6
```

**Annotate findings while counting.** As you read through the patch, note each issue with its path and position immediately. Keep a running list like:

```
src/foo.js  pos 46   regex has unnecessary `i` flag
src/foo.js  pos 52   no-op ternary assignment
src/foo.js  pos 129  %y padStart doesn't truncate -- bug
main.js     pos 7    ClassAsync undefined -- runtime crash
```

**Which findings go inline vs general:**
- **Inline**: any finding tied to a specific line of added/changed code
- **General comment**: architectural issues, missing whole files, module-system-level problems, empty test files, PR checklist

## Step 6 -- Build and post the review

### 6a. Inline comments

Build one JSON object containing **all** inline comments and write it to a temp file. The critical requirement is UTF-8 **without BOM** -- the Windows default UTF-8 encoding includes a BOM that causes GitHub to return HTTP 400.

**The correct pattern -- always use this exactly:**

```powershell
# 1. Build the JSON using a single-quoted here-string.
#    @'...'@ is completely literal: no variable expansion, no escape processing.
#    Single quotes inside the string are fine -- no escaping needed.
#    Write \n (backslash-n) for newlines inside JSON string values.
$json = @'
{
  "commit_id": "<head_sha>",
  "event": "COMMENT",
  "comments": [
    {
      "path": "src/foo.js",
      "position": 46,
      "body": "The `i` flag is unnecessary here -- remove it:\n```js\nconst regex = /(\\d+)/g;\n```"
    },
    {
      "path": "src/foo.js",
      "position": 52,
      "body": "No-op: `match[2]` is already the matched string. Simplify to `const unit = match[2];`"
    },
    {
      "path": "src/main.js",
      "position": 7,
      "body": "`ClassAsync` is not defined anywhere -- this throws a ReferenceError at runtime."
    }
  ]
}
'@

# 2. Write to temp file with UTF-8 NO-BOM encoding.
#    Do NOT use Out-File or Set-Content -- both add BOM by default on Windows.
$tmpFile = "$env:TEMP\pr_review.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($tmpFile, $json, $utf8NoBom)

# 3. Validate the JSON parses correctly before sending.
$json | ConvertFrom-Json | Out-Null
Write-Host "JSON valid, comment count: $(($json | ConvertFrom-Json).comments.Count)"

# 4. POST the review.
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$result = & $gh api repos/<owner>/<repo>/pulls/<pr_number>/reviews --method POST --input $tmpFile 2>&1
if ($LASTEXITCODE -eq 0) {
    ($result | ConvertFrom-Json).html_url
} else {
    $result
}
```

**JSON body writing rules:**
- Use `--` instead of `--` (em dash) and `->` instead of arrows -- Unicode punctuation can cause encoding failures
- Use `\n` for newlines inside string values (valid JSON escape sequence)
- Escape backslashes in code snippets: `\\d` not `\d`
- Every comment object must have exactly: `path` (string), `position` (integer), `body` (string)

### 6b. General comment (for findings not tied to a line)

```powershell
$gh = "C:\Program Files\GitHub CLI\gh.exe"
& $gh pr comment <pr_number> --repo <owner>/<repo> --body @"
## General Review Notes

...markdown here...
"@
```

## Step 7 -- Report back

Tell the user:
- The URL of the posted review
- A brief summary of how many inline comments were posted and what categories were covered
- Whether the overall recommendation is Approve / Request Changes / Comment

## Error handling

| Problem | Fix |
|---|---|
| `gh: command not found` | Use full path `C:\Program Files\GitHub CLI\gh.exe` |
| `HTTP 400 Problems parsing JSON` | JSON has BOM or bad encoding -- use `System.IO.File::WriteAllText` with `UTF8Encoding($false)` |
| `HTTP 422 Position could not be resolved` | Position is wrong -- recount from the `@@` line (it is NOT position 1; the line below it is) |
| `HTTP 404` | Repo is private and `gh auth login` has not been run -- ask user to authenticate first |
| No issue number in PR | Skip requirements section; review code quality only |
