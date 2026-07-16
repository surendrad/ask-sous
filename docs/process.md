# Claude Code Project Framework

A repeatable process for starting and running projects in [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Use this as the starting point for all new projects, and share with your team so everyone follows the same workflow.

The framework uses [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) — reusable prompt templates that guide Claude through each step with consistent quality. You invoke them by typing `/skill-name` in Claude Code.

## Getting Started

### Prerequisites

- **Claude Code** installed and working. [Get Claude Code here](https://docs.anthropic.com/en/docs/claude-code/overview) — you'll need an Anthropic account with a Max plan, or API access.

### Setup

1. **Clone this repo** into a location on your machine (not inside a project):

   ```bash
   git clone https://github.com/petebulley/claude-code-framework.git ~/claude-code-framework
   ```

2. **Symlink the framework skills into your global Claude skills directory.** This makes them available in every Claude Code session, regardless of which project you're working in:

   ```bash
   mkdir -p ~/.claude/skills
   for skill in ~/claude-code-framework/.claude/skills/*/; do
     ln -sf "$skill" ~/.claude/skills/
   done
   ```

   This creates symlinks in `~/.claude/skills/` pointing back to the cloned repo, so the skills stay git-tracked and updatable.

3. **Start a new project.** Create your project directory, open Claude Code, and type:

   ```
   /start-project
   ```

   The skill will scaffold your documentation, walk you through creating the master plan, and configure Claude's permissions. From there, follow the steps below in order.

   **Existing project?** If you already have a project and want to bring it into the framework, use:

   ```
   /adopt
   ```

   This will audit your project, map what exists against the framework, and create a plan to fill the gaps — preserving your existing code and conventions.

### Recommended: Playwright MCP

For visual verification during design and implementation, set up the Playwright MCP:

```bash
claude mcp add playwright npx '@playwright/mcp@latest'
```

This lets Claude open pages in a real browser, take screenshots, and verify UI work. The `/designer` skill will prompt you to set this up, but you can do it in advance.

### Updating the Framework

Since you cloned the repo, you can pull updates at any time:

```bash
cd ~/claude-code-framework && git pull
```

Updated skills are available immediately in your next Claude Code session — no reconfiguration needed.

---

## Overview

**Steps 1-6** take you from idea to deployed, tested product. Run them in order for the initial build. **Step 7** is your ongoing development workflow — use it for all work after the initial build is complete. **Already have a project?** Use `/adopt` to retrofit the framework — see [Adopting the Framework for Existing Projects](#adopting-the-framework-for-existing-projects).

| Step | Name | Skill | Output |
|------|------|-------|--------|
| 1 | Start Project | `/start-project` | Project docs scaffold, master plan, Claude permissions |
| 2 | CTO | `/cto` | Tech stack, implementation plan, conventions, CLAUDE.md |
| 3 | Designer | `/designer` | Design guidelines, design system showcase |
| 4 | Implement | `/implement` | Working code, tests, documentation per phase |
| 5 | First Deploy | `/first-deploy` | First-time deployment guide, project deploy skill |
| 6 | UAT | `/uat` | Test results, issue log, sign-off |
| 7 | Work | `/work` | Bug fixes, features, tweaks, refactors |

---

## Step 1: Start Project

Scaffold the project documentation and create the master plan.

**Skill:** `/start-project`
**When:** Beginning of every new project.

### What happens
1. Scaffold the `/docs` directory structure with empty files and sub-directories
2. Prompt the user to add any existing documentation or references to `docs/reference/`
3. Walk through an interactive process to define and document the master plan
4. Configure Claude Code permissions based on user's risk appetite (`.claude/settings.local.json`)

### What gets created

```
docs/
  process.md
  changelog.md
  tasks.md
  uat.md
  definition/
    master-plan.md
    design-guidelines.md
    implementation-plan.md
  decisions/
  plans/
  deployment/
  reference/
```

---

## Step 2: CTO

Agree technology choices, establish conventions, and create the implementation plan. This step is about decisions and documentation only — no code is written.

**Skill:** `/cto`
**When:** After the master plan is agreed in Step 1.

### What happens
1. Review the master plan and understand technical requirements
2. Choose the tech stack (language, framework, database, hosting, etc.), considering existing infrastructure
3. Choose testing framework and establish testing methodology (TDD/red-green-refactor as default)
4. Choose code quality tooling (linter, formatter, git hooks, commit conventions)
5. Establish project conventions (structure, naming, API design, database patterns, error handling)
6. Establish documentation principles (ADRs, plans in `/docs/plans`, changelog, living docs)
7. Create the phased implementation plan with dependencies, risks, and MVP definition
8. Generate `CLAUDE.md` codifying all conventions for future Claude sessions

### What gets created
- `docs/definition/implementation-plan.md` — phased build plan
- `docs/definition/stack.md` — full tech stack reference
- `docs/decisions/_template.md` — ADR template
- `docs/decisions/001-documentation-first.md` — documentation principles ADR
- `CLAUDE.md` — project conventions for Claude Code

---

## Step 3: Designer

Agree design direction and create the design system. The user is encouraged to share design inspiration (websites, screenshots, mood words) to guide the process.

**Skill:** `/designer`
**When:** After tech choices are agreed in Step 2.

### What happens
1. Gather design inspiration and references from the user
2. Establish design philosophy and core visual direction
3. Create HTML showcase pages in `docs/` with multiple options for each design decision (colour palette, typography, icons, components, layouts, motion) — the user opens these to compare options and give feedback
4. Iterate on each showcase until the user locks in their choice
5. Write the design guidelines document
6. Build a final consolidated design system showcase (single-page HTML)
7. Iterate with the user until they're happy with the design

### What gets created
- `docs/showcase-*.html` — decision showcase pages with multiple options (colour palette, typography, icons, components, layouts)
- `docs/definition/design-guidelines.md` — full design system specification
- `docs/definition/design-system.html` — live interactive showcase of all agreed design elements

---

## Step 4: Implement

Build the project one phase at a time. Each invocation of `/implement` works on a single phase — planning it, implementing it, testing it, and documenting it.

**Skill:** `/implement`
**When:** After design is agreed in Step 3. Run once per phase, repeatedly, until all phases are complete.

### What happens
1. Show overall progress and identify the next phase to implement
2. Read all documentation and understand the current codebase
3. Create a detailed plan for the phase (stored in `/docs/plans`)
4. Present the plan for user review and approval
5. Add approved tasks to `docs/tasks.md` (the master task list)
6. Implement the phase: code, tests, and documentation together
7. Keep `docs/tasks.md` updated in real-time as tasks are completed
8. Record any technical decisions as ADRs in `docs/decisions/`
9. Write UAT scenarios for the phase in `docs/uat.md`
10. Present local testing guide so the user can verify the phase
11. Update changelog, implementation plan status, and CLAUDE.md at phase completion

### What gets created
- `docs/plans/phase-[N]-[name].md` — detailed phase plan
- Application code and tests for the phase
- ADRs in `docs/decisions/` for any technical decisions made
- Updated `docs/tasks.md` with task progress
- Updated `docs/uat.md` with UAT scenarios for the phase
- Updated `docs/changelog.md` with phase summary

---

## Step 5: First Deploy

Set up first-time deployment to production and create a project-specific deploy skill for ongoing use.

**Skill:** `/first-deploy`
**When:** After the first implementable phase is complete.

### What happens
1. Read project documentation to understand the deployment landscape (hosting, database, services, env vars)
2. Ask the user about accounts, domains, and manual setup requirements
3. Create a comprehensive first-time deployment guide with every step spelled out
4. Create a project-specific `/deploy-[project]` skill for all future deployments
5. Present both documents for review

### What gets created
- `docs/deployment/first-time-setup.md` — step-by-step first-time deployment guide
- `.claude/skills/deploy-[project]/SKILL.md` — ongoing deployment skill (invoked as `/deploy-[project]`)

---

## Step 6: UAT

User acceptance testing of the deployed project. The test scenarios were written during each `/implement` phase and live in `docs/uat.md`.

**Skill:** `/uat`
**When:** After deployment to production. Can be re-run after significant changes.

### What happens
1. Show UAT progress summary (passed/failed/not started counts)
2. Find the next uncompleted test
3. Prepare the test environment (browser state, accounts, device, prerequisites)
4. Walk through test steps one at a time with explicit, detailed instructions
5. If an issue is found: investigate, fix, deploy via `/deploy-[project]`, and retest from the beginning
6. Mark tests as passed or failed in `docs/uat.md`
7. Continue to the next test or stop — progress is saved

### What gets created
- Updated `docs/uat.md` with test results (pass/fail status, failure notes)

---

## Step 7: Work

Ongoing development — bug fixes, new features, tweaks, and refactors. This is the skill used for all work after the initial build is complete.

**Skill:** `/work`
**When:** Ongoing, after initial build and UAT. This is the day-to-day development skill.

### What happens
1. Ask the user: pick from the task list or work on something new?
2. If task list: show open tasks, failed UAT tests, and blocked items
3. If new: classify the work (bug fix, feature, tweak, refactor)
4. Read relevant code, conventions, and design guidelines
5. Plan (scaled to work size — full plan for features, diagnosis for bugs, brief statement for tweaks)
6. Implement using red-green-refactor: failing tests first, then code
7. Verify (test suite, lint, type checks, build)
8. Update documentation (tasks.md, changelog, UAT scenarios for new features, ADRs for decisions)
9. Suggest deploying via `/deploy-[project]`

### What gets created
- `docs/plans/feature-[name].md` — plan for new features (not for bugs/tweaks)
- Updated application code and tests
- Updated `docs/tasks.md` with task status
- Updated `docs/changelog.md` with change summary
- Updated `docs/uat.md` with UAT scenarios (for new user-facing features)
- ADRs in `docs/decisions/` (for non-trivial decisions)

---

## Adopting the Framework for Existing Projects

Already have a project? Use `/adopt` to bring it into the framework without starting from scratch.

**Skill:** `/adopt`
**When:** You have an existing project with code, possibly some documentation, and want to use the framework's workflow and skills going forward.

### What happens

1. **Audit** — explores the project thoroughly: code, docs, conventions, tests, deployment, project maturity
2. **Map** — compares what exists against every framework artifact in a clear table, categorised as: fine (no changes needed), needs reorganising (content exists but in wrong place/format), or missing (needs creating)
3. **Plan** — writes a phased adoption plan to `docs/plans/framework-adoption.md`:
   - Phase 1: Foundation — `CLAUDE.md`, `docs/` structure, retroactive master plan, stack reference
   - Phase 2: History capture — retroactive ADRs for key decisions already made, changelog from git history
   - Phase 3: Planning — implementation plan (existing features as completed phases, future work as upcoming phases), task list from issues/TODOs
   - Phase 4: Design documentation — design guidelines and showcase extracted from existing UI (skipped if no frontend)
   - Phase 5: Operations — UAT scenarios for existing features, deployment docs, deploy skill
4. **Execute** — works through the plan conversationally, creating each artifact from the existing codebase rather than from a blank slate
5. **Verify** — confirms everything's in place, then hands off to the normal workflow

### Key principles

- **No code changes** — only documentation and configuration are created. Your application code is untouched.
- **Preserves existing conventions** — if your project uses Black, the framework uses Black. It adapts to your project, not the other way around.
- **Retroactive docs reflect reality** — the master plan describes what IS built, not a hypothetical. The implementation plan marks existing features as done.
- **Skip what doesn't apply** — no frontend means no design system. CLI tool means no UI-focused UAT scenarios.
- **Phases are optional** — Phase 1 (foundation) is the minimum. The rest depends on your goals.

### What gets created

- `CLAUDE.md` — project conventions derived from existing code and config
- `docs/definition/master-plan.md` — product specification (retroactive, from README and codebase)
- `docs/definition/stack.md` — tech stack reference (generated from project config)
- `docs/definition/implementation-plan.md` — completed phases for existing features, future phases for planned work
- `docs/definition/design-guidelines.md` — design system extracted from existing UI (if frontend)
- `docs/definition/design-system.html` — interactive showcase (if frontend)
- `docs/tasks.md` — task list from issues, TODOs, and planned work
- `docs/uat.md` — UAT scenarios for existing features
- `docs/changelog.md` — project history from git log
- `docs/decisions/` — retroactive ADRs for key technical decisions
- `docs/deployment/first-time-setup.md` — existing deployment process documented
- `.claude/skills/deploy-[project]/SKILL.md` — deploy skill for ongoing use
- `.claude/settings.local.json` — Claude Code permissions

After adoption, you can use all the ongoing skills: `/work`, `/status`, `/new-issue`, `/implement`, `/uat`, and `/deploy-[project]`.

---

## Utility Skills

Skills used throughout the project lifecycle, not tied to a specific step.

| Skill | Description |
|-------|-------------|
| `/new-issue` | Quickly capture a bug, feature idea, or improvement to `docs/tasks.md` without breaking your current flow. Designed for speed — log it and get back to work. |
| `/status` | Check where the project stands — implementation progress, open tasks, UAT results, recent activity — and get a recommendation for what to do next. |

---

## Feedback and Contributing

This framework is open source and actively improved based on real-world usage. If you've used it to build a project, I'd love to hear how it went.

- **Share feedback** — [Open an issue](https://github.com/petebulley/claude-code-framework/issues) with your experience, suggestions, or questions
- **Report a problem** — if a skill didn't work well or produced poor results, [open an issue](https://github.com/petebulley/claude-code-framework/issues) describing what happened
- **Suggest improvements** — [open a pull request](https://github.com/petebulley/claude-code-framework/pulls) with your proposed changes

The most useful feedback is specific: which skill, what happened, what you expected, and what would have been better.
