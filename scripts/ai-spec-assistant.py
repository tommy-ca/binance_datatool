#!/usr/bin/env python3
"""
AI Specification Assistant
Provides AI-powered assistance for specification generation and validation
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class SpecificationAnalyzer:
    """Analyzes and validates specifications using AI-assisted methods."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.templates_dir = self.project_root / "docs" / "specs-driven-flow" / "templates"

    def analyze_legacy_code(self, code_path: str) -> Dict:
        """Analyze legacy code and suggest specifications."""
        code_file = Path(code_path)

        if not code_file.exists():
            raise FileNotFoundError(f"Code file not found: {code_path}")

        # Read and analyze the code
        with open(code_file, "r", encoding="utf-8") as f:
            code_content = f.read()

        analysis = {
            "file_path": str(code_file),
            "file_type": code_file.suffix,
            "analysis_date": "2024-01-15",  # In real implementation, use datetime.now()
            "suggested_requirements": self._extract_requirements_from_code(code_content),
            "suggested_functions": self._extract_functions_from_code(code_content),
            "dependencies": self._extract_dependencies_from_code(code_content),
            "complexity_analysis": self._analyze_complexity(code_content),
        }

        return analysis

    def _extract_requirements_from_code(self, code_content: str) -> List[Dict]:
        """Extract potential requirements from code analysis."""
        requirements = []

        # Look for function definitions and docstrings
        function_pattern = r'def\s+(\w+)\s*\([^)]*\):\s*(?:"""([^"]+)"""|\'\'\'([^\']+)\'\'\')?'
        functions = re.findall(function_pattern, code_content, re.MULTILINE | re.DOTALL)

        for i, (func_name, docstring1, docstring2) in enumerate(functions, 1):
            docstring = docstring1 or docstring2 or ""

            # Generate EARS-style requirements from function analysis
            if "download" in func_name.lower():
                req = {
                    "id": f"FR{i:03d}",
                    "type": "event_driven",
                    "requirement": f"When a user requests data download, the system shall execute {func_name} and return the downloaded data",
                    "function_source": func_name,
                    "rationale": f"Derived from function: {func_name}",
                    "priority": "must_have",
                }
                requirements.append(req)

            elif "parse" in func_name.lower():
                req = {
                    "id": f"FR{i:03d}",
                    "type": "event_driven",
                    "requirement": f"When data parsing is requested, the system shall execute {func_name} and return structured data",
                    "function_source": func_name,
                    "rationale": f"Derived from function: {func_name}",
                    "priority": "must_have",
                }
                requirements.append(req)

            elif "validate" in func_name.lower() or "verify" in func_name.lower():
                req = {
                    "id": f"FR{i:03d}",
                    "type": "ubiquitous",
                    "requirement": f"The system shall validate data integrity using {func_name}",
                    "function_source": func_name,
                    "rationale": f"Derived from function: {func_name}",
                    "priority": "must_have",
                }
                requirements.append(req)

        return requirements

    def _extract_functions_from_code(self, code_content: str) -> List[Dict]:
        """Extract function signatures and documentation."""
        functions = []

        function_pattern = r'def\s+(\w+)\s*\(([^)]*)\):\s*(?:"""([^"]+)"""|\'\'\'([^\']+)\'\'\')?'
        matches = re.findall(function_pattern, code_content, re.MULTILINE | re.DOTALL)

        for func_name, params, docstring1, docstring2 in matches:
            docstring = (docstring1 or docstring2 or "").strip()

            functions.append(
                {
                    "name": func_name,
                    "parameters": params.strip(),
                    "docstring": docstring,
                    "complexity": self._estimate_function_complexity(func_name, docstring),
                }
            )

        return functions

    def _extract_dependencies_from_code(self, code_content: str) -> List[str]:
        """Extract import dependencies from code."""
        dependencies = []

        # Find import statements
        import_patterns = [r"import\s+(\w+)", r"from\s+(\w+)\s+import", r"import\s+(\w+\.\w+)"]

        for pattern in import_patterns:
            matches = re.findall(pattern, code_content)
            dependencies.extend(matches)

        return list(set(dependencies))  # Remove duplicates

    def _analyze_complexity(self, code_content: str) -> Dict:
        """Analyze code complexity indicators."""
        lines = code_content.split("\n")

        return {
            "total_lines": len(lines),
            "code_lines": len(
                [line for line in lines if line.strip() and not line.strip().startswith("#")]
            ),
            "function_count": len(re.findall(r"def\s+\w+", code_content)),
            "class_count": len(re.findall(r"class\s+\w+", code_content)),
            "complexity_estimate": self._estimate_overall_complexity(code_content),
        }

    def _estimate_function_complexity(self, func_name: str, docstring: str) -> str:
        """Estimate function complexity based on name and documentation."""
        if any(keyword in func_name.lower() for keyword in ["download", "upload", "process"]):
            return "high"
        elif any(keyword in func_name.lower() for keyword in ["parse", "validate", "format"]):
            return "medium"
        else:
            return "low"

    def _estimate_overall_complexity(self, code_content: str) -> str:
        """Estimate overall code complexity."""
        lines = len(code_content.split("\n"))
        functions = len(re.findall(r"def\s+\w+", code_content))
        classes = len(re.findall(r"class\s+\w+", code_content))

        complexity_score = lines / 10 + functions * 2 + classes * 3

        if complexity_score > 100:
            return "very_high"
        elif complexity_score > 50:
            return "high"
        elif complexity_score > 20:
            return "medium"
        else:
            return "low"

    def generate_specs_from_prompt(self, prompt: str, feature_name: str) -> Dict:
        """Generate specifications from natural language prompt."""
        # This is a simplified implementation
        # In a real AI system, this would use LLM APIs

        specs = {
            "feature_name": feature_name,
            "prompt": prompt,
            "generated_requirements": self._parse_prompt_to_requirements(prompt),
            "suggested_scenarios": self._generate_bdd_scenarios(prompt),
            "quality_attributes": self._extract_quality_attributes(prompt),
        }

        return specs

    def _parse_prompt_to_requirements(self, prompt: str) -> List[Dict]:
        """Parse natural language prompt into EARS requirements."""
        requirements = []

        # Simple keyword-based parsing (in reality, would use NLP/LLM)
        if "authenticate" in prompt.lower() or "login" in prompt.lower():
            requirements.append(
                {
                    "id": "FR001",
                    "type": "event_driven",
                    "requirement": "When a user submits valid credentials, the system shall authenticate the user and return a JWT token",
                    "priority": "must_have",
                    "source": "AI-generated from prompt",
                }
            )

        if "security" in prompt.lower() or "secure" in prompt.lower():
            requirements.append(
                {
                    "id": "FR002",
                    "type": "ubiquitous",
                    "requirement": "The system shall encrypt all sensitive data using industry-standard encryption",
                    "priority": "must_have",
                    "source": "AI-generated from prompt",
                }
            )

        if "performance" in prompt.lower() or "fast" in prompt.lower():
            requirements.append(
                {
                    "id": "FR003",
                    "type": "event_driven",
                    "requirement": "When a user request is processed, the system shall respond within 100ms",
                    "priority": "should_have",
                    "source": "AI-generated from prompt",
                }
            )

        return requirements

    def _generate_bdd_scenarios(self, prompt: str) -> List[Dict]:
        """Generate BDD scenarios from prompt."""
        scenarios = []

        if "authenticate" in prompt.lower() or "login" in prompt.lower():
            scenarios.append(
                {
                    "name": "Successful user authentication",
                    "gherkin": """
Scenario: User logs in with valid credentials
  Given a user with valid email and password
  When the user submits the login form
  Then the system should authenticate the user
  And the system should return a valid token
  And the user should be redirected to dashboard
                """.strip(),
                }
            )

        return scenarios

    def _extract_quality_attributes(self, prompt: str) -> Dict:
        """Extract quality attributes from prompt."""
        attributes = {}

        if "performance" in prompt.lower():
            attributes["performance"] = {"response_time": "< 100ms", "throughput": "> 1000 req/s"}

        if "security" in prompt.lower():
            attributes["security"] = {"encryption": "AES-256", "authentication": "JWT tokens"}

        if "reliability" in prompt.lower():
            attributes["reliability"] = {
                "availability": "99.9%",
                "fault_tolerance": "Graceful degradation",
            }

        return attributes

    def validate_ears_patterns(self, requirements_file: str) -> Dict:
        """Validate EARS patterns in requirements file."""
        with open(requirements_file, "r", encoding="utf-8") as f:
            if requirements_file.endswith(".yml") or requirements_file.endswith(".yaml"):
                content = yaml.safe_load(f)
            else:
                content = f.read()

        validation_results = {
            "file": requirements_file,
            "valid_patterns": [],
            "invalid_patterns": [],
            "suggestions": [],
        }

        # Validate EARS patterns (simplified implementation)
        ears_keywords = {
            "ubiquitous": ["shall", "must"],
            "event_driven": ["when", "shall"],
            "state_driven": ["while", "shall"],
            "optional_feature": ["where", "shall"],
            "unwanted_behavior": ["if", "then"],
        }

        # In a real implementation, this would parse YAML and validate each requirement
        validation_results["suggestions"].append(
            "Consider using standard EARS patterns for all requirements"
        )
        validation_results["suggestions"].append(
            "Ensure all event-driven requirements have clear triggers"
        )

        return validation_results


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="AI Specification Assistant")
    parser.add_argument("--project-root", default=".", help="Project root directory")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze legacy code command
    analyze_parser = subparsers.add_parser(
        "analyze-legacy", help="Analyze legacy code and suggest specs"
    )
    analyze_parser.add_argument("code_path", help="Path to legacy code file")
    analyze_parser.add_argument("--output", help="Output file for analysis results")

    # Generate specs from prompt command
    generate_parser = subparsers.add_parser(
        "generate-specs", help="Generate specs from natural language prompt"
    )
    generate_parser.add_argument("prompt", help="Natural language description of requirements")
    generate_parser.add_argument("feature_name", help="Name of the feature")
    generate_parser.add_argument("--output", help="Output file for generated specs")

    # Validate EARS patterns command
    validate_parser = subparsers.add_parser(
        "validate-ears", help="Validate EARS patterns in requirements"
    )
    validate_parser.add_argument("requirements_file", help="Requirements file to validate")
    validate_parser.add_argument("--output", help="Output file for validation results")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    analyzer = SpecificationAnalyzer(args.project_root)

    try:
        if args.command == "analyze-legacy":
            results = analyzer.analyze_legacy_code(args.code_path)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
                print(f"Analysis results written to {args.output}")
            else:
                print(json.dumps(results, indent=2))

        elif args.command == "generate-specs":
            results = analyzer.generate_specs_from_prompt(args.prompt, args.feature_name)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
                print(f"Generated specs written to {args.output}")
            else:
                print(json.dumps(results, indent=2))

        elif args.command == "validate-ears":
            results = analyzer.validate_ears_patterns(args.requirements_file)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
                print(f"Validation results written to {args.output}")
            else:
                print(json.dumps(results, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
