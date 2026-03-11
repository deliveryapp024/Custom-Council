"""Terminal approval gate."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Approved:
    plan_file: Path
    plan_hash: str


@dataclass
class Rejected:
    pass


@dataclass
class EditRequested:
    feedback: str


ApprovalResult = Approved | Rejected | EditRequested


def request_approval(final_plan: str, run_dir: Path) -> ApprovalResult:
    print("\n" + "=" * 60)
    print("  CHAIRMAN'S FINAL IMPLEMENTATION PLAN")
    print("=" * 60)
    print(final_plan)
    print("=" * 60)

    while True:
        choice = input("\nDo you approve? (Y/N/Edit): ").strip().upper()
        if choice == "Y":
            run_dir.mkdir(parents=True, exist_ok=True)
            plan_hash = hashlib.sha256(final_plan.encode("utf-8")).hexdigest()[:12]
            plan_file = run_dir / f"approved_plan_{plan_hash}.md"
            plan_file.write_text(final_plan, encoding="utf-8")
            print(f"Plan approved and saved to {plan_file}")
            return Approved(plan_file=plan_file, plan_hash=plan_hash)
        if choice == "N":
            print("Plan rejected. Aborting.")
            return Rejected()
        if choice == "EDIT":
            feedback = input("Enter your feedback: ").strip()
            return EditRequested(feedback=feedback)
        print("Please enter Y, N, or Edit.")
