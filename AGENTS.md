# AGENTS.md

## Instruction Priority
This file defines the authoritative workflow for this repository.
If other instructions conflict with this file, follow AGENTS.md.

---

## Overview
This repository uses a structured multi-agent workflow:

- Planner: breaks down spec into tasks
- Developer: implements tasks
- Tester: validates tasks
- Reviewer: adjudicates defects or ambiguities

All work MUST follow task packets and acceptance criteria.

---

## Workflow

### Task execution loop

1. Developer picks next task
2. Developer implements task
3. Tester validates against acceptance criteria
4. If PASS -> write devlog entry
5. If FAIL or AMBIGUOUS -> spawn Reviewer
6. If defect confirmed -> Developer fixes -> Tester revalidates
7. Repeat until PASS

---

## Roles

### Developer
- Implement ONLY the current task
- Keep changes minimal
- Respect module boundaries
- Map implementation to acceptance criteria
- Write tests for all acceptance criteria
- Update tests when behavior changes
- Do NOT self-approve

### Tester
- Validate strictly against acceptance criteria
- Run all quality checks:
  - `ruff check . --fix`
  - `mypy .`
  - `pytest`
- Verify tests actually cover acceptance criteria
- Add missing edge-case tests when necessary
- Do NOT trust Developer tests blindly
- Check edge cases:
  - fees, rounding, stale data, volume
- Return: PASS / FAIL / AMBIGUOUS

### Reviewer (only on failure)
- Compare:
  - defect report
  - acceptance criteria
  - original spec
- Return:
  - CONFIRMED_DEFECT
  - NOT_A_DEFECT
  - SPEC_UNCLEAR

---

## Testing Responsibilities

Developer:
- Must write tests for all acceptance criteria
- Must map acceptance criteria to specific tests

Tester:
- Must run all tests
- Must verify tests truly validate acceptance criteria
- Must add tests for missing edge cases when needed
- Must challenge incorrect or weak test coverage

---

## Task rules

- Only ONE task in progress at a time
- Do not start next task until current task = PASS
- Do not expand scope beyond task packet

---

## Definition of Done

A task is DONE only if:
- All acceptance criteria are satisfied
- Tests exist for acceptance criteria
- Lint passes
- Type checks pass
- Tests pass
- Devlog entry is written

---

## Commands

### Install
```bash
uv sync
