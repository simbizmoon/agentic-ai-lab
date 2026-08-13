"""Print the Phase 10A heterogeneous role-routing contract."""

from __future__ import annotations

import json

from app.research.hybrid_role_policy import (
    HybridResearchRolePolicy,
    ResearchExecutionProvider,
)


def main() -> int:
    policy = HybridResearchRolePolicy.phase10_default()

    payload = {
        "phase": "10A",
        "purpose": (
            "Define explicit role-level provider routing before changing "
            "production runtime composition."
        ),
        "policy": {
            role.value: provider.value
            for role, provider in policy.as_role_map().items()
        },
        "provider_groups": {
            provider.value: [
                role.value
                for role in policy.roles_for(provider)
            ]
            for provider in ResearchExecutionProvider
        },
        "safety_boundaries": {
            "local_final_quality_authority": False,
            "local_roles_are_bounded_workers": True,
            "planning_remains_deterministic": True,
        },
        "production_behavior_changed": False,
        "next": (
            "Phase 10B wires this policy into live research composition."
        ),
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
