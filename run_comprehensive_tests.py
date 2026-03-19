#!/usr/bin/env python3
import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import django
    from django.conf import settings
    from django.core.management import execute_from_command_line

    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medguard_project.settings')
    django.setup()

    from medguard_app.orchestrator.decision_pipeline import DecisionPipeline
except ImportError as e:
    print(f"Error importing Django/MedGuard modules: {e}")
    print("Make sure you're running from the project root directory.")
    sys.exit(1)

class MedGuardTestRunner:
    def __init__(self):
        self.pipeline = DecisionPipeline()
        self.test_results = []
        self.start_time = None

    def load_test_cases(self, level: str = "all") -> List[Dict]:
        """Load test cases based on specified level."""
        test_files = {
            "basic": "test_cases_basic.json",
            "moderate": "test_cases_moderate.json",
            "complex": "test_cases_complex.json",
            "edge": "test_cases_edge.json"
        }

        all_test_cases = []

        if level == "all":
            files_to_load = test_files.values()
        else:
            files_to_load = [test_files.get(level)]
            if not files_to_load[0]:
                raise ValueError(f"Unknown test level: {level}")

        for filename in files_to_load:
            filepath = project_root / filename
            if filepath.exists():
                try:
                    with open(filepath, 'r') as f:
                        test_cases = json.load(f)
                        all_test_cases.extend(test_cases)
                        print(f"Loaded {len(test_cases)} test cases from {filename}")
                except json.JSONDecodeError as e:
                    print(f"Error loading {filename}: {e}")
            else:
                print(f"Warning: {filename} not found")

        return all_test_cases

    def run_single_test(self, test_case: Dict, verbose: bool = False) -> Dict:
        """Run a single test case and return detailed results."""
        test_id = test_case.get("test_id", "unknown")
        test_name = test_case.get("name", "Unknown Test")

        if verbose:
            print(f"\\n--- Running Test: {test_id} ---")
            print(f"Name: {test_name}")
            print(f"Input: {test_case['input']}")

        start_time = time.time()

        try:
            # Extract input parameters
            symptoms = test_case["input"]["symptoms"]
            proposed_drug = test_case["input"]["proposed_drug"]
            existing_drugs = test_case["input"]["existing_drugs"]

            # Run the pipeline
            result = self.pipeline.evaluate(symptoms, proposed_drug, existing_drugs)

            execution_time = time.time() - start_time

            # Analyze results against expectations
            test_result = {
                "test_id": test_id,
                "name": test_name,
                "level": test_case.get("level", "unknown"),
                "status": "PASS",
                "execution_time": execution_time,
                "input": test_case["input"],
                "output": result,
                "expected": test_case.get("expected", {}),
                "validation_results": self._validate_expectations(result, test_case.get("expected", {})),
                "timestamp": datetime.now().isoformat()
            }

            if verbose:
                print(f"Risk Level: {result.get('risk_level', 'N/A')}")
                print(f"Risk Score: {result.get('risk_score', 'N/A')}")
                print(f"Execution Time: {execution_time:.3f}s")
                if result.get('alternatives'):
                    print(f"Alternatives Found: {len(result['alternatives'])}")

        except Exception as e:
            execution_time = time.time() - start_time
            test_result = {
                "test_id": test_id,
                "name": test_name,
                "level": test_case.get("level", "unknown"),
                "status": "FAIL",
                "execution_time": execution_time,
                "input": test_case["input"],
                "error": str(e),
                "error_type": type(e).__name__,
                "expected": test_case.get("expected", {}),
                "timestamp": datetime.now().isoformat()
            }

            if verbose:
                print(f"ERROR: {e}")

        return test_result

    def _validate_expectations(self, result: Dict, expected: Dict) -> Dict:
        """Validate the result against expected outcomes."""
        validation = {
            "matches": [],
            "mismatches": [],
            "warnings": []
        }

        for key, expected_value in expected.items():
            if key == "risk_level":
                actual = result.get("risk_level")
                if actual == expected_value:
                    validation["matches"].append(f"risk_level: {actual}")
                else:
                    validation["mismatches"].append(f"risk_level: expected {expected_value}, got {actual}")

            elif key == "treats_symptom":
                actual = result.get("findings", {}).get("treats_symptom")
                if actual == expected_value:
                    validation["matches"].append(f"treats_symptom: {actual}")
                else:
                    validation["mismatches"].append(f"treats_symptom: expected {expected_value}, got {actual}")

            elif key == "interactions_found":
                actual = result.get("findings", {}).get("interactions_found", 0)
                if actual == expected_value:
                    validation["matches"].append(f"interactions_found: {actual}")
                elif actual > expected_value:
                    validation["warnings"].append(f"interactions_found: expected {expected_value}, got {actual} (more than expected)")
                else:
                    validation["mismatches"].append(f"interactions_found: expected {expected_value}, got {actual}")

            elif key == "has_alternatives":
                actual = len(result.get("alternatives", [])) > 0
                if actual == expected_value:
                    validation["matches"].append(f"has_alternatives: {actual}")
                else:
                    validation["mismatches"].append(f"has_alternatives: expected {expected_value}, got {actual}")

        return validation

    def run_all_tests(self, test_cases: List[Dict], verbose: bool = False) -> Dict:
        """Run all test cases and return comprehensive results."""
        self.start_time = time.time()
        print(f"\\nStarting test run with {len(test_cases)} test cases...")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        results = {
            "summary": {
                "total_tests": len(test_cases),
                "passed": 0,
                "failed": 0,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "total_duration": None
            },
            "test_results": [],
            "performance_stats": {
                "average_execution_time": 0,
                "min_execution_time": float('inf'),
                "max_execution_time": 0,
                "slow_tests": []  # Tests taking > 5 seconds
            },
            "level_summary": {},
            "validation_summary": {
                "total_matches": 0,
                "total_mismatches": 0,
                "total_warnings": 0
            }
        }

        for i, test_case in enumerate(test_cases, 1):
            print(f"\\rProgress: {i}/{len(test_cases)} ({i/len(test_cases)*100:.1f}%)", end="")

            test_result = self.run_single_test(test_case, verbose)
            results["test_results"].append(test_result)

            # Update summary stats
            if test_result["status"] == "PASS":
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1

            # Update performance stats
            exec_time = test_result["execution_time"]
            results["performance_stats"]["min_execution_time"] = min(
                results["performance_stats"]["min_execution_time"], exec_time
            )
            results["performance_stats"]["max_execution_time"] = max(
                results["performance_stats"]["max_execution_time"], exec_time
            )

            if exec_time > 5.0:
                results["performance_stats"]["slow_tests"].append({
                    "test_id": test_result["test_id"],
                    "execution_time": exec_time
                })

            # Update level summary
            level = test_result["level"]
            if level not in results["level_summary"]:
                results["level_summary"][level] = {"passed": 0, "failed": 0, "total": 0}

            results["level_summary"][level]["total"] += 1
            if test_result["status"] == "PASS":
                results["level_summary"][level]["passed"] += 1
            else:
                results["level_summary"][level]["failed"] += 1

            # Update validation summary
            if "validation_results" in test_result:
                validation = test_result["validation_results"]
                results["validation_summary"]["total_matches"] += len(validation.get("matches", []))
                results["validation_summary"]["total_mismatches"] += len(validation.get("mismatches", []))
                results["validation_summary"]["total_warnings"] += len(validation.get("warnings", []))

        # Finalize results
        total_duration = time.time() - self.start_time
        results["summary"]["end_time"] = datetime.now().isoformat()
        results["summary"]["total_duration"] = total_duration

        # Calculate average execution time
        if test_cases:
            total_exec_time = sum(r["execution_time"] for r in results["test_results"])
            results["performance_stats"]["average_execution_time"] = total_exec_time / len(test_cases)

        print()  # New line after progress indicator
        return results

    def print_summary(self, results: Dict):
        """Print a formatted summary of test results."""
        summary = results["summary"]
        perf = results["performance_stats"]

        print("\\n" + "="*60)
        print("           MEDGUARD TEST RESULTS SUMMARY")
        print("="*60)

        print(f"Total Tests:     {summary['total_tests']}")
        print(f"Passed:          {summary['passed']} ({summary['passed']/summary['total_tests']*100:.1f}%)")
        print(f"Failed:          {summary['failed']} ({summary['failed']/summary['total_tests']*100:.1f}%)")
        print(f"Total Duration:  {summary['total_duration']:.2f} seconds")

        print("\\n--- Performance Stats ---")
        print(f"Average execution time: {perf['average_execution_time']:.3f}s")
        print(f"Min execution time:     {perf['min_execution_time']:.3f}s")
        print(f"Max execution time:     {perf['max_execution_time']:.3f}s")

        if perf['slow_tests']:
            print(f"\\nSlow tests (>5s): {len(perf['slow_tests'])}")
            for slow_test in perf['slow_tests'][:5]:  # Show first 5
                print(f"  {slow_test['test_id']}: {slow_test['execution_time']:.2f}s")

        print("\\n--- Results by Level ---")
        for level, stats in results["level_summary"].items():
            pass_rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"{level.upper():<12} {stats['passed']}/{stats['total']} ({pass_rate:.1f}%)")

        validation = results["validation_summary"]
        if validation['total_matches'] + validation['total_mismatches'] > 0:
            print("\\n--- Validation Summary ---")
            print(f"Expected outcomes matched:    {validation['total_matches']}")
            print(f"Expected outcomes mismatched: {validation['total_mismatches']}")
            print(f"Warnings:                     {validation['total_warnings']}")

        print("\\n--- Failed Tests ---")
        failed_tests = [r for r in results["test_results"] if r["status"] == "FAIL"]
        if failed_tests:
            for test in failed_tests[:10]:  # Show first 10 failures
                print(f"  {test['test_id']}: {test.get('error', 'Unknown error')}")
        else:
            print("  None! All tests passed.")

        print("="*60)

def main():
    parser = argparse.ArgumentParser(description="Run comprehensive MedGuard tests")
    parser.add_argument("--level", choices=["basic", "moderate", "complex", "edge", "all"],
                       default="all", help="Test level to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", type=str, help="Output results to JSON file")

    args = parser.parse_args()

    try:
        runner = MedGuardTestRunner()
        test_cases = runner.load_test_cases(args.level)

        if not test_cases:
            print("No test cases found!")
            return 1

        results = runner.run_all_tests(test_cases, args.verbose)
        runner.print_summary(results)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\\nDetailed results saved to: {args.output}")

        # Return exit code based on test results
        return 0 if results["summary"]["failed"] == 0 else 1

    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())