#!/usr/bin/env python3

import asyncio
import csv
import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to Python path so we can import from library
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from library.ai import select_department

# Semaphore to limit concurrent tasks
MAX_CONCURRENT_TASKS = 4


async def process_single_test_case(semaphore, row, case_number):
    """Process a single test case with semaphore control"""
    async with semaphore:
        file_hash = row.get("file_hash", "unknown")
        content = row.get("content", "")
        summary = row.get("summary", "")

        print(f"\nTest Case {case_number}: {file_hash}")
        print("-" * 60)

        try:
            print(f"DEBUG: Processing row for {file_hash}")

            # Get the expected official order from corrected_department_id column
            expected_department_id = row.get("corrected_department_id", "").strip()
            print(f"DEBUG: expected_order: {expected_department_id}")

            if not expected_department_id or expected_department_id in [
                "17",
                "8",
                "24",
                "",
            ]:
                print(
                    f"Warning: No valid corrected official order found for {file_hash}"
                )
                return None

            # Call the select_department function
            result = await select_department(content)

            if result and result.get("id"):
                predicted_department_id = str(result.get("id"))
                reasoning = result.get("reasoning", "No reasoning provided")

                print(f"Predicted official order: {predicted_department_id}")
                print(f"Expected official order: {expected_department_id}")

                # Check if prediction matches expected result
                if predicted_department_id == str(expected_department_id):
                    print(
                        f"✅ PASS - Official order matches (Expected: {expected_department_id}, Predicted: {predicted_department_id})"
                    )
                    return {
                        "status": "pass",
                        "file_hash": file_hash,
                        "expected": expected_department_id,
                        "predicted": predicted_department_id,
                        "reasoning": reasoning,
                    }
                else:
                    print(
                        f"❌ FAIL - Official order mismatch (Expected: {expected_department_id}, Predicted: {predicted_department_id})"
                    )
                    print(f"   Reasoning: {reasoning}")
                    print(f"   Summary: {summary}")
                    return {
                        "status": "fail",
                        "file_hash": file_hash,
                        "expected": expected_department_id,
                        "predicted": predicted_department_id,
                        "reasoning": reasoning,
                        "summary": summary,
                    }
            else:
                print("❌ FAIL - No official selected by AI")
                print(f"   Summary: {summary}")
                return {
                    "status": "fail",
                    "file_hash": file_hash,
                    "expected": expected_department_id,
                    "predicted": "None",
                    "reasoning": "No official selected",
                    "summary": summary,
                }

        except KeyError as e:
            print(f"DEBUG: Missing column error for {file_hash}: {str(e)}")
            return {
                "status": "fail",
                "file_hash": file_hash,
                "expected": "Missing Column",
                "predicted": "Missing Column",
                "reasoning": "Missing required column",
            }

        except Exception as e:
            print(f"DEBUG: Exception caught for {file_hash}: {str(e)}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback

            print(f"DEBUG: Full traceback:")
            traceback.print_exc()
            return {
                "status": "fail",
                "file_hash": file_hash,
                "expected": "Error",
                "predicted": "Error",
                "reasoning": str(e),
            }


async def test_select_department_from_csv(csv_file_path):
    """Test the select_department function with test cases from CSV file using parallel processing"""

    if not os.path.exists(csv_file_path):
        print(f"Error: CSV file not found at {csv_file_path}")
        return

    print("Testing select_department function")
    print(f"Reading test cases from: {csv_file_path}")
    print(f"Running with {MAX_CONCURRENT_TASKS} concurrent tasks")
    print("=" * 80)

    # Create semaphore to limit concurrent tasks
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    tasks = []
    valid_rows = []

    try:
        with open(csv_file_path, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            print(f"DEBUG: CSV headers: {reader.fieldnames}")

            for item, row in enumerate(reader, start=1):
                # Skip rows where corrected_department_id is null or empty
                corrected_dept_id = row.get("corrected_department_id", "").strip()
                if not corrected_dept_id or corrected_dept_id in ["17", "8", "24"]:
                    continue

                valid_rows.append((row, len(valid_rows) + 1))

        # Create tasks for parallel processing
        for row, case_number in valid_rows:
            task = process_single_test_case(semaphore, row, case_number)
            tasks.append(task)

        print(f"Created {len(tasks)} test tasks")
        print("Starting parallel execution...")

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        passed_cases = []
        failed_cases = []
        total_cases = 0

        for result in results:
            if isinstance(result, Exception):
                print(f"Task failed with exception: {result}")
                failed_cases.append(
                    {
                        "file_hash": "Exception",
                        "expected": "Error",
                        "predicted": "Error",
                        "reasoning": str(result),
                    }
                )
                total_cases += 1
            elif result is not None:
                total_cases += 1
                if result["status"] == "pass":
                    passed_cases.append(
                        {
                            "file_hash": result["file_hash"],
                            "expected": result["expected"],
                            "predicted": result["predicted"],
                            "reasoning": result.get("reasoning"),
                        }
                    )
                else:
                    failed_cases.append(
                        {
                            "file_hash": result["file_hash"],
                            "expected": result["expected"],
                            "predicted": result["predicted"],
                            "reasoning": result.get("reasoning"),
                            "summary": result.get("summary"),
                        }
                    )

    except Exception as e:
        print(f"Error reading CSV file: {str(e)}")
        return

    # Write results to file
    results_file = "test-results.txt"
    with open(results_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("TEST SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total test cases: {total_cases}\n")

        if total_cases > 0:
            f.write(
                f"Passed: {len(passed_cases)} ({len(passed_cases) / total_cases * 100:.1f}%)\n"
            )
            f.write(
                f"Failed: {len(failed_cases)} ({len(failed_cases) / total_cases * 100:.1f}%)\n"
            )
        else:
            f.write("No valid test cases found in the CSV file.\n")
            f.write(
                "Make sure the CSV has rows with non-empty 'corrected_department_id' values.\n"
            )
            print(f"Results written to {results_file}")
            return

        # Write passed cases
        if passed_cases:
            f.write("\n✅ PASSED TEST CASES:\n")
            f.write("-" * 40 + "\n")
            for case in passed_cases:
                f.write(f"Hash: {case['file_hash']}\n")
                f.write(
                    f"  Expected: {case['expected']}, Predicted: {case['predicted']}\n"
                )
                if case.get("reasoning"):
                    f.write(f"  Reasoning: {case['reasoning']}\n")
                f.write("\n")

        # Write failed cases
        if failed_cases:
            f.write("\n❌ FAILED TEST CASES:\n")
            f.write("-" * 40 + "\n")
            for case in failed_cases:
                f.write(f"Hash: {case['file_hash']}\n")
                f.write(
                    f"  Expected: {case['expected']}, Predicted: {case['predicted']}\n"
                )
                if case.get("reasoning"):
                    f.write(f"  Reasoning: {case['reasoning']}\n")
                if case.get("summary"):
                    f.write(f"  Summary: {case['summary']}\n")
                f.write("\n")

        # Write file hashes for easy reference
        f.write("\nPASSED FILE HASHES:\n")
        f.write(", ".join([case["file_hash"] for case in passed_cases]) + "\n")

        f.write("\nFAILED FILE HASHES:\n")
        f.write(", ".join([case["file_hash"] for case in failed_cases]) + "\n")

    print(f"Results written to {results_file}")
    print(f"Total test cases: {total_cases}")
    if total_cases > 0:
        print(
            f"Passed: {len(passed_cases)} ({len(passed_cases) / total_cases * 100:.1f}%)"
        )
        print(
            f"Failed: {len(failed_cases)} ({len(failed_cases) / total_cases * 100:.1f}%)"
        )


def main():
    """Main function to run the test"""

    # Check if CSV file path is provided as command line argument
    if len(sys.argv) < 2:
        print("Usage: python test-ai-csv.py <path_to_csv_file>")
        print("Example: python test-ai-csv.py data/test_cases.csv")
        sys.exit(1)

    csv_file_path = sys.argv[1]

    # Check if required environment variables are set
    required_env_vars = ["OPENAI_API_KEY", "OPENAI_API_BASE_URL"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print(
            f"Error: Missing required environment variables: {', '.join(missing_vars)}"
        )
        print("Please set these in your .env file or environment")
        sys.exit(1)

    # Run the async test
    try:
        asyncio.run(test_select_department_from_csv(csv_file_path))
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
