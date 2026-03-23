# Plan

Delegate to the Planner agent for an implementation strategy.

Invoke the Planner with:
- What needs to be built or changed (WHAT)
- Current state of the codebase (what exists, what's relevant)
- Constraints (tech stack, existing patterns, known blockers)
- Success criteria (what done looks like)

The Planner returns:
- Step-by-step implementation plan
- Files to create/modify
- Key architectural decisions
- Risks or trade-offs

Once the plan is returned, present it to the Director for approval before delegating to the Coder.
