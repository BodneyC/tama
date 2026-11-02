---
description: Implement the next incomplete milestone from docs/ROADMAP.md
---

1. Read `CLAUDE.md`, `docs/ROADMAP.md`, and the docs relevant to the first milestone that
   still has unchecked items. $ARGUMENTS
2. Make a short plan for the remaining items in that milestone. Order it so that domain logic
   and tests come before the UI.
3. Implement the items one at a time. For domain logic, write the tests first. Commit after
   each coherent step with a Conventional Commit message.
4. Tick off completed items in `docs/ROADMAP.md`. If you had to diverge from the SPEC or
   ARCHITECTURE, update those docs too, and add an ADR if the decision is architectural.
5. Finish by running `/check`. The milestone is done only when the check is green and its
   **Accept** criterion has been shown to hold.
6. Summarise what you did, any deviations, and anything you deferred.
