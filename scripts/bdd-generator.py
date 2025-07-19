#!/usr/bin/env python3
"""
BDD Generator
Converts YAML specifications to executable Gherkin scenarios and test files
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List

import yaml


class BDDGenerator:
    """Generates BDD test files from specification YAML files."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.features_dir = self.project_root / "features"
        self.tests_dir = self.project_root / "tests"

    def generate_feature_files(self, spec_file: str, feature_name: str) -> Dict:
        """Generate Gherkin feature files from specifications."""
        spec_path = Path(spec_file)

        if not spec_path.exists():
            raise FileNotFoundError(f"Specification file not found: {spec_file}")

        with open(spec_path, "r", encoding="utf-8") as f:
            specs = yaml.safe_load(f)

        # Extract BDD scenarios from specs
        bdd_scenarios = specs.get("bdd_scenarios", {})

        if not bdd_scenarios:
            raise ValueError("No BDD scenarios found in specification file")

        # Generate feature file content
        feature_content = self._generate_feature_content(bdd_scenarios, feature_name)

        # Generate step definitions
        step_definitions = self._generate_step_definitions(bdd_scenarios, feature_name)

        # Create output files
        feature_file = self.tests_dir / "features" / f"{feature_name.replace('-', '_')}.feature"
        steps_file = self.tests_dir / "steps" / f"{feature_name.replace('-', '_')}_steps.py"

        # Ensure directories exist
        feature_file.parent.mkdir(parents=True, exist_ok=True)
        steps_file.parent.mkdir(parents=True, exist_ok=True)

        # Write feature file
        with open(feature_file, "w", encoding="utf-8") as f:
            f.write(feature_content)

        # Write step definitions
        with open(steps_file, "w", encoding="utf-8") as f:
            f.write(step_definitions)

        return {
            "feature_file": str(feature_file),
            "steps_file": str(steps_file),
            "scenarios_generated": len(bdd_scenarios.get("scenarios", [])),
        }

    def _generate_feature_content(self, bdd_scenarios: Dict, feature_name: str) -> str:
        """Generate Gherkin feature file content."""
        feature_title = bdd_scenarios.get("feature", feature_name.replace("-", " ").title())
        background = bdd_scenarios.get("background", "")
        scenarios = bdd_scenarios.get("scenarios", [])

        content = f"""Feature: {feature_title}
  As a user of the system
  I want to use {feature_name.replace('-', ' ')} functionality
  So that I can achieve my business goals

"""

        if background:
            content += f"Background:\n{self._indent_gherkin(background)}\n\n"

        for scenario in scenarios:
            scenario_name = scenario.get("name", "Untitled Scenario")
            scenario_gherkin = scenario.get("gherkin", "")
            tags = scenario.get("tags", [])

            if tags:
                tag_line = "  @" + " @".join(tags) + "\n"
                content += tag_line

            content += f"  Scenario: {scenario_name}\n"
            content += self._indent_gherkin(scenario_gherkin, 2) + "\n\n"

        return content

    def _generate_step_definitions(self, bdd_scenarios: Dict, feature_name: str) -> str:
        """Generate Python step definitions for BDD scenarios."""
        scenarios = bdd_scenarios.get("scenarios", [])

        # Extract unique steps from all scenarios
        steps = set()
        for scenario in scenarios:
            gherkin = scenario.get("gherkin", "")
            scenario_steps = self._extract_steps_from_gherkin(gherkin)
            steps.update(scenario_steps)

        # Add background steps
        background = bdd_scenarios.get("background", "")
        if background:
            background_steps = self._extract_steps_from_gherkin(background)
            steps.update(background_steps)

        content = f'''"""
Step definitions for {feature_name.replace('-', ' ').title()} feature.
Generated from specifications - customize as needed.
"""

import pytest
from pytest_bdd import given, when, then, scenarios
from typing import Dict, Any


# Load all scenarios from the feature file
scenarios('../features/{feature_name.replace('-', '_')}.feature')


# Test fixtures and setup
@pytest.fixture
def context() -> Dict[str, Any]:
    """Test context for sharing data between steps."""
    return {{}}


@pytest.fixture
def system_under_test():
    """Initialize the system under test."""
    # TODO: Initialize your system/application here
    return None


'''

        # Generate step definitions
        for step in sorted(steps):
            step_def = self._generate_step_definition(step)
            content += step_def + "\n\n"

        return content

    def _extract_steps_from_gherkin(self, gherkin: str) -> List[str]:
        """Extract step definitions from Gherkin text."""
        steps = []
        lines = gherkin.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith(("Given ", "When ", "Then ", "And ", "But ")):
                steps.append(line)

        return steps

    def _generate_step_definition(self, step: str) -> str:
        """Generate Python step definition from Gherkin step."""
        step_type = step.split()[0].lower()
        step_text = " ".join(step.split()[1:])

        # Create a function name from the step text
        func_name = self._step_to_function_name(step_text)

        # Generate step definition based on type
        if step_type == "given":
            decorator = "@given"
        elif step_type == "when":
            decorator = "@when"
        elif step_type == "then":
            decorator = "@then"
        elif step_type in ["and", "but"]:
            # For And/But steps, we need to infer the type from context
            # For simplicity, we'll use @then
            decorator = "@then"
        else:
            decorator = "@given"

        # Create parameterized step pattern
        step_pattern = self._create_step_pattern(step_text)

        return f'''{decorator}('{step_pattern}')
def {func_name}(context, system_under_test):
    """Step: {step}"""
    # TODO: Implement this step
    assert False, "This step is not implemented yet"'''

    def _step_to_function_name(self, step_text: str) -> str:
        """Convert step text to valid Python function name."""
        # Remove special characters and convert to snake_case
        import re

        # Replace non-alphanumeric characters with spaces
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", step_text)

        # Convert to snake_case
        words = cleaned.lower().split()
        func_name = "_".join(words)

        # Ensure it starts with a letter
        if func_name and func_name[0].isdigit():
            func_name = "step_" + func_name

        return func_name or "unnamed_step"

    def _create_step_pattern(self, step_text: str) -> str:
        """Create a parameterized step pattern for pytest-bdd."""
        # Simple implementation - in reality, you'd want more sophisticated parameter detection
        import re

        # Replace quoted strings with parameters
        pattern = re.sub(r'"([^"]*)"', r"<\1>", step_text)

        # Replace numbers with parameters
        pattern = re.sub(r"\b\d+\b", r"<number>", pattern)

        return pattern

    def _indent_gherkin(self, gherkin: str, additional_indent: int = 0) -> str:
        """Indent Gherkin text properly."""
        lines = gherkin.strip().split("\n")
        base_indent = "  "
        additional = "  " * additional_indent

        indented_lines = []
        for line in lines:
            if line.strip():
                indented_lines.append(base_indent + additional + line.strip())
            else:
                indented_lines.append("")

        return "\n".join(indented_lines)

    def generate_test_runner(self, feature_name: str) -> str:
        """Generate a test runner script for the BDD tests."""
        runner_content = f'''#!/usr/bin/env python3
"""
BDD Test Runner for {feature_name.replace('-', ' ').title()}
Run BDD tests using pytest-bdd
"""

import subprocess
import sys
from pathlib import Path


def run_bdd_tests():
    """Run BDD tests for {feature_name}."""
    tests_dir = Path(__file__).parent
    feature_file = tests_dir / "features" / "{feature_name.replace('-', '_')}.feature"
    
    if not feature_file.exists():
        print(f"Feature file not found: {{feature_file}}")
        return 1
        
    # Run pytest with BDD support
    cmd = [
        "python", "-m", "pytest",
        "--tb=short",
        "-v",
        str(tests_dir / "steps" / "{feature_name.replace('-', '_')}_steps.py")
    ]
    
    print(f"Running BDD tests for {feature_name}...")
    print(f"Command: {{' '.join(cmd)}}")
    
    result = subprocess.run(cmd, cwd=tests_dir.parent)
    return result.returncode


if __name__ == "__main__":
    sys.exit(run_bdd_tests())
'''

        return runner_content


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="BDD Generator")
    parser.add_argument("--project-root", default=".", help="Project root directory")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate feature files command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate BDD feature files from specs"
    )
    generate_parser.add_argument("spec_file", help="Path to specification YAML file")
    generate_parser.add_argument("feature_name", help="Name of the feature")
    generate_parser.add_argument(
        "--with-runner", action="store_true", help="Generate test runner script"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    generator = BDDGenerator(args.project_root)

    try:
        if args.command == "generate":
            results = generator.generate_feature_files(args.spec_file, args.feature_name)

            print(f"Generated BDD files:")
            print(f"  Feature file: {results['feature_file']}")
            print(f"  Steps file: {results['steps_file']}")
            print(f"  Scenarios: {results['scenarios_generated']}")

            if args.with_runner:
                runner_content = generator.generate_test_runner(args.feature_name)
                runner_file = (
                    Path(args.project_root)
                    / "tests"
                    / f"run_{args.feature_name.replace('-', '_')}_tests.py"
                )

                with open(runner_file, "w", encoding="utf-8") as f:
                    f.write(runner_content)

                os.chmod(runner_file, 0o755)
                print(f"  Test runner: {runner_file}")

            print("\nNext steps:")
            print("1. Install pytest-bdd: pip install pytest-bdd")
            print("2. Implement the step definitions in the generated steps file")
            print("3. Run tests: pytest tests/steps/")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
