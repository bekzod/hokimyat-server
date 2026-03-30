#!/usr/bin/env python3
"""
OCR Server CSV Converter

This script processes CSV files from OCR server output and extracts structured data
from JSON fields to create organized output files.

Input CSV columns expected:
- file_hash, status, error_message, content, total_page_count, meta, created_at,
  updated_at, processed_at, manual_input, employee_id, employment_id, doc_type

Output CSV columns:
- file_hash, content, meta, summary, selected_department_id,
  selected_department_reasoning, selected_category_id, selected_category_reasoning,
  corrected_department_id, corrected_department_reasoning, employee_id, employment_id

Author: Assistant
"""

import csv
import json
import sys
import argparse
from typing import Any, Dict, Optional
from pathlib import Path


class CSVConverter:
    """Main CSV converter class"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.processed_rows = 0
        self.errors = []

    def log(self, message: str) -> None:
        """Log message if verbose mode is enabled"""
        if self.verbose:
            print(f"[INFO] {message}")

    def safe_json_parse(self, json_str: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON string, return None if invalid"""
        if not json_str or json_str.strip() == '' or json_str.lower() == 'null':
            return None

        # Handle escaped quotes in the JSON string
        json_str = json_str.strip()
        if json_str.startswith('"') and json_str.endswith('"'):
            json_str = json_str[1:-1]  # Remove outer quotes
            json_str = json_str.replace('""', '"')  # Unescape double quotes

        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as e:
            self.log(f"JSON parsing error: {e}")
            return None

    def extract_from_json(self, json_obj: Optional[Dict[str, Any]], *keys: str) -> Any:
        """Extract nested value from JSON object using key path"""
        if json_obj is None:
            return None

        current = json_obj
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def detect_delimiter(self, file_path: str) -> str:
        """Detect CSV delimiter by examining the first line"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if '\t' in first_line:
                    return '\t'
                elif ',' in first_line:
                    return ','
                elif ';' in first_line:
                    return ';'
                else:
                    return ','  # Default to comma
        except Exception:
            return ','

    def validate_input_file(self, file_path: str) -> bool:
        """Validate input file exists and has required columns"""
        if not Path(file_path).exists():
            print(f"❌ Error: File '{file_path}' not found.")
            return False

        delimiter = self.detect_delimiter(file_path)
        required_columns = ['file_hash', 'status', 'content', 'meta', 'manual_input',
                          'employee_id', 'employment_id']

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                if not reader.fieldnames:
                    print("❌ Error: Could not read CSV headers.")
                    return False

                missing_columns = [col for col in required_columns
                                 if col not in reader.fieldnames]
                if missing_columns:
                    print(f"❌ Error: Missing required columns: {missing_columns}")
                    print(f"Available columns: {list(reader.fieldnames)}")
                    return False

                self.log(f"✅ Input file validation passed. Delimiter: '{delimiter}'")
                return True
        except Exception as e:
            print(f"❌ Error validating input file: {e}")
            return False

    def process_row(self, row: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Process a single row and extract required fields"""
        # Only process rows with status 'completed'
        if row.get('status', '').strip().lower() != 'completed':
            return None

        # Parse meta JSON
        meta_json = self.safe_json_parse(row.get('meta', ''))

        # Extract from meta JSON
        summary = self.extract_from_json(meta_json, 'summary')
        selected_dept_id = self.extract_from_json(meta_json, 'department', 'id')
        selected_dept_reasoning = self.extract_from_json(meta_json, 'department', 'reasoning')
        selected_cat_id = self.extract_from_json(meta_json, 'category', 'id')
        selected_cat_reasoning = self.extract_from_json(meta_json, 'category', 'reasoning')

        # Parse manual_input JSON
        manual_input_json = self.safe_json_parse(row.get('manual_input', ''))

        # Extract from manual_input using actual structure
        corrected_dept_id = None
        corrected_dept_reasoning = None
        corrected_cat_id = None
        corrected_cat_reasoning = None

        if manual_input_json is not None:
            # Extract corrected department data
            corrected_dept_id_raw = self.extract_from_json(manual_input_json, 'department', 'new')
            corrected_dept_reasoning_raw = self.extract_from_json(manual_input_json, 'department', 'description')

            # Only set corrected values if they differ from selected values
            if corrected_dept_id_raw and str(corrected_dept_id_raw) != str(selected_dept_id):
                corrected_dept_id = corrected_dept_id_raw
                corrected_dept_reasoning = corrected_dept_reasoning_raw

            # Extract corrected category data
            corrected_cat_id_raw = self.extract_from_json(manual_input_json, 'category', 'new')
            corrected_cat_reasoning_raw = self.extract_from_json(manual_input_json, 'category', 'description')

            # Only set corrected values if they differ from selected values
            if corrected_cat_id_raw and str(corrected_cat_id_raw) != str(selected_cat_id):
                corrected_cat_id = corrected_cat_id_raw
                corrected_cat_reasoning = corrected_cat_reasoning_raw

        # Create output row with proper handling of None values
        return {
            'file_hash': row.get('file_hash', ''),
            'content': row.get('content', ''),
            'meta': row.get('meta', ''),
            'summary': summary if summary is not None else '',
            'selected_department_id': selected_dept_id if selected_dept_id is not None else '',
            'selected_department_reasoning': selected_dept_reasoning if selected_dept_reasoning is not None else '',
            'selected_category_id': selected_cat_id if selected_cat_id is not None else '',
            'selected_category_reasoning': selected_cat_reasoning if selected_cat_reasoning is not None else '',
            'corrected_department_id': corrected_dept_id if corrected_dept_id is not None else '',
            'corrected_department_reasoning': corrected_dept_reasoning if corrected_dept_reasoning is not None else '',
            'corrected_category_id': corrected_cat_id if corrected_cat_id is not None else '',
            'corrected_category_reasoning': corrected_cat_reasoning if corrected_cat_reasoning is not None else '',
            'employee_id': row.get('employee_id', ''),
            'employment_id': row.get('employment_id', '')
        }

    def convert(self, input_file: str, output_file: str) -> bool:
        """Convert CSV file and return success status"""

        if not self.validate_input_file(input_file):
            return False

        delimiter = self.detect_delimiter(input_file)
        output_rows = []

        try:
            with open(input_file, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile, delimiter=delimiter)

                delimiter_name = 'TAB' if delimiter == '\t' else delimiter
                self.log(f"Processing {input_file} with delimiter: {delimiter_name}")

                # Process each row
                for row_num, row in enumerate(reader, 1):
                    try:
                        self.log(f"Processing row {row_num}...")
                        output_row = self.process_row(row)
                        if output_row is not None:  # Only add if status is 'completed'
                            output_rows.append(output_row)
                            self.processed_rows += 1
                        else:
                            self.log(f"Skipping row {row_num} - status not 'completed'")
                    except Exception as e:
                        error_msg = f"Error processing row {row_num}: {e}"
                        self.errors.append(error_msg)
                        self.log(error_msg)
                        continue

            # Write output CSV
            if output_rows:
                fieldnames = [
                    'file_hash', 'content', 'meta', 'summary', 'selected_department_id',
                    'selected_department_reasoning', 'selected_category_id', 'selected_category_reasoning',
                    'corrected_department_id', 'corrected_department_reasoning', 'corrected_category_id',
                    'corrected_category_reasoning', 'employee_id', 'employment_id'
                ]

                with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
                    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(output_rows)

                print(f"✅ Successfully created '{output_file}' with {len(output_rows)} rows.")

                # Show sample data if verbose
                if self.verbose and output_rows:
                    self.show_sample_data(output_rows[0])

                return True
            else:
                print("❌ No data to process.")
                return False

        except Exception as e:
            print(f"❌ Error processing CSV file: {e}")
            return False

    def show_sample_data(self, sample_row: Dict[str, Any]) -> None:
        """Display sample extracted data"""
        print("\n📋 Sample extracted data from first row:")
        print(f"  File Hash: {sample_row['file_hash'][:20]}...")

        summary = sample_row['summary']
        if len(summary) > 100:
            print(f"  Summary: {summary[:100]}...")
        else:
            print(f"  Summary: {summary}")

        print(f"  Department ID: {sample_row['selected_department_id']}")
        print(f"  Category ID: {sample_row['selected_category_id']}")
        print(f"  Corrected Dept ID: {sample_row['corrected_department_id'] or 'None'}")
        print(f"  Employee ID: {sample_row['employee_id']}")

    def show_summary(self) -> None:
        """Show processing summary"""
        print(f"\n📊 Processing Summary:")
        print(f"  Rows processed: {self.processed_rows}")
        print(f"  Errors encountered: {len(self.errors)}")

        if self.errors and self.verbose:
            print("\n⚠️  Errors:")
            for error in self.errors[:3]:  # Show first 3 errors
                print(f"    {error}")
            if len(self.errors) > 3:
                print(f"    ... and {len(self.errors) - 3} more errors")


def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Convert OCR server CSV files to structured format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python csv_converter.py test_case.csv output.csv
  python csv_converter.py -v test_case.csv output.csv
  python csv_converter.py --input data.csv --output result.csv --verbose

Input CSV must contain columns:
  file_hash, status, content, meta, manual_input, employee_id, employment_id

Output CSV will contain columns:
  file_hash, content, meta, summary, selected_department_id,
  selected_department_reasoning, selected_category_id, selected_category_reasoning,
  corrected_department_id, corrected_department_reasoning, corrected_category_id,
  corrected_category_reasoning, employee_id, employment_id
        """
    )

    parser.add_argument('input_file', nargs='?', default='test_case.csv',
                       help='Input CSV file path (default: test_case.csv)')
    parser.add_argument('output_file', nargs='?', default='processed_output.csv',
                       help='Output CSV file path (default: processed_output.csv)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--input', dest='input_alt',
                       help='Alternative way to specify input file')
    parser.add_argument('--output', dest='output_alt',
                       help='Alternative way to specify output file')

    args = parser.parse_args()

    # Use alternative names if provided
    input_file = args.input_alt or args.input_file
    output_file = args.output_alt or args.output_file

    print("🚀 OCR CSV Converter")
    print(f"📁 Input: {input_file}")
    print(f"📄 Output: {output_file}")
    print(f"🔧 Verbose: {'ON' if args.verbose else 'OFF'}")
    print("-" * 50)

    converter = CSVConverter(verbose=args.verbose)
    success = converter.convert(input_file, output_file)
    converter.show_summary()

    if success:
        print(f"\n🎉 Conversion completed successfully!")
        sys.exit(0)
    else:
        print(f"\n💥 Conversion failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
