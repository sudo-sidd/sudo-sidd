# Workflow Versions

This folder keeps a reference copy of the **best experience** workflow while the repository runs the **free-optimized** workflow in production.

## Why the free version is active

I chose the free version to keep GitHub Actions usage as low as possible.
The free version avoids expensive extra runtime and is better for long-term zero-cost operation.

## Differences

### Active (free-optimized)
- File: `.github/workflows/pet_loop.yml`
- Goal: Minimize Action minutes.
- No post-action `sleep` and no forced second run.
- Uses `concurrency` to cancel overlapping runs.
- Lowest cost, but action animation may stay until the next trigger.

### Optional (best experience)
- File: `workflow-versions/best-experience/pet_loop.yml`
- Goal: Better visual behavior after interactions.
- Includes a `sleep 130` + second update to revert animation quickly.
- Smoother user-facing animation behavior.
- Higher Action-minute usage.

## You can use either version

Anyone can choose either setup based on their priorities:
- Pick the free version for lowest cost.
- Pick the best-experience version for smoother animation behavior.

To switch, copy the desired workflow into `.github/workflows/pet_loop.yml`.
