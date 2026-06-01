"""
Tier summary — inspect the model tier map and cascade profiles.

Usage:
    python -m examples.23_tier_summary
"""

from agentpipe import CASCADE_PROFILES, ModelTier, tier_summary


def main():
    print("=== Model Tiers ===\n")

    summary = tier_summary()
    for tier in ModelTier:
        models = summary[tier]
        print(f"{tier.name} ({tier.value}):")
        for entry in models:
            print(f"  {entry['model']:45s} provider={entry['provider']}")
        print()

    print("=== Cascade Profiles ===\n")

    for profile, models in CASCADE_PROFILES.items():
        print(f"{profile}:")
        for m in models:
            print(f"  {m}")
        print()


if __name__ == "__main__":
    main()
