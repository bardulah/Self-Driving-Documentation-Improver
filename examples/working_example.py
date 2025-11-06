#!/usr/bin/env python3
"""
Working example demonstrating the documentation improver in action.

This script shows a complete workflow:
1. Analyze code to find documentation gaps
2. Generate improvements (without actually calling Claude API for this example)
3. Display the results

To run with real API:
    export ANTHROPIC_API_KEY="your-key-here"
    python examples/working_example.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from doc_improver.models import ExplorationConfig, TargetType
from doc_improver.explorer.code_explorer_v2 import CodeExplorerV2
from doc_improver.analyzer.gap_detector import GapDetector


def main():
    """Run the working example."""
    print("=" * 70)
    print("Self-Driving Documentation Improver - Working Example")
    print("=" * 70)
    print()

    # Step 1: Configure exploration
    print("Step 1: Configuring exploration...")
    target_path = Path(__file__).parent / "test_project"

    if not target_path.exists():
        target_path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {target_path}")

    config = ExplorationConfig(
        target_type=TargetType.CODE,
        target_path_or_url=str(target_path)
    )
    print(f"  Target: {target_path}")
    print(f"  Mode: {config.mode}")
    print()

    # Step 2: Explore code
    print("Step 2: Exploring code...")
    explorer = CodeExplorerV2(config, use_cache=False)
    entities = explorer.explore()

    print(f"  Found {len(entities)} code entities")
    print()

    # Step 3: Display discovered entities
    print("Step 3: Discovered entities:")
    for entity in entities:
        status = "✓ Documented" if entity.docstring else "✗ Missing docs"
        print(f"  {entity.name} ({entity.type}) - {status}")
    print()

    # Step 4: Detect documentation gaps
    print("Step 4: Detecting documentation gaps...")
    detector = GapDetector()
    gaps = detector.analyze_code_entities(entities)

    print(f"  Found {len(gaps)} documentation gaps")
    print()

    # Step 5: Display gaps by severity
    print("Step 5: Gaps by severity:")
    from doc_improver.models import Severity

    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        severity_gaps = [g for g in gaps if g.severity == severity]
        if severity_gaps:
            print(f"  {severity.value.upper()}: {len(severity_gaps)} gaps")
            for gap in severity_gaps[:3]:  # Show first 3
                print(f"    - {gap.description}")
    print()

    # Step 6: Show what improvements would look like
    print("Step 6: Example improvement needed:")
    if gaps:
        example_gap = gaps[0]
        print(f"  Location: {example_gap.location}")
        print(f"  Issue: {example_gap.description}")
        print(f"  Type: {example_gap.gap_type.value}")
        print()

        if example_gap.entity:
            print(f"  Current code:")
            if example_gap.entity.signature:
                print(f"    {example_gap.entity.signature}")
            if example_gap.entity.docstring:
                print(f"    Current doc: {example_gap.entity.docstring[:100]}...")
            else:
                print(f"    No documentation")
    print()

    # Summary
    print("=" * 70)
    print("Summary:")
    print(f"  Total entities: {len(entities)}")
    print(f"  Public entities: {len([e for e in entities if e.is_public])}")
    print(f"  Documented: {len([e for e in entities if e.docstring])}")
    print(f"  Undocumented: {len([e for e in entities if not e.docstring and e.is_public])}")
    print(f"  Documentation gaps: {len(gaps)}")
    print("=" * 70)
    print()
    print("✅ Example completed successfully!")
    print()
    print("Next steps:")
    print("  1. Set ANTHROPIC_API_KEY environment variable")
    print("  2. Use CLI: doc-improver analyze ./examples/test_project --type code")
    print("  3. Review and apply improvements")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
