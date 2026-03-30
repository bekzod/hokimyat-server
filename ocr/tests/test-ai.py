#!/usr/bin/env python3

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to Python path so we can import from lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.ai import select_department

async def test_select_department():
    """Test the select_department function with arbitrary text"""

    # Test cases with different types of complaints
    test_cases = [
        {
            "name": "Healthcare Complaint",
            "text": "I am filing a complaint about the poor medical service I received at the local hospital. The doctors were unprofessional and the treatment was inadequate. There were long waiting times and unsanitary conditions in the facility."
        },
        {
            "name": "Education Complaint",
            "text": "My child's school has been consistently providing substandard education. Teachers are often absent, textbooks are outdated, and the school infrastructure is in poor condition. The administration is unresponsive to parent concerns."
        },
        {
            "name": "Transportation Complaint",
            "text": "The public transportation system in our area is unreliable and dangerous. Buses are frequently late or don't show up at all. The vehicles are poorly maintained and pose safety risks to passengers."
        },
        {
            "name": "Environmental Complaint",
            "text": "There is illegal dumping of industrial waste near our residential area causing air and water pollution. The smell is unbearable and residents are experiencing health issues. No action has been taken despite multiple reports."
        },
        {
            "name": "General Administrative Complaint",
            "text": "Government officials in our district are corrupt and unresponsive to citizen needs. Permits and licenses are delayed without proper justification, and there seems to be favoritism in service delivery."
        }
    ]

    print("Testing select_department function")
    print("=" * 60)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['name']}")
        print("-" * 40)
        print(f"Input text: {test_case['text'][:100]}...")

        try:
            result = await select_department(test_case['text'])
            print(f"Result: {result}")

            if result and result.get('id'):
                print(f"Selected Department ID: {result.get('id')}")
                print(f"Confidence: {result.get('confidence', 'N/A')}")
                if 'reasoning' in result:
                    print(f"Reasoning: {result['reasoning']}")
            else:
                print("No department selected")

        except Exception as e:
            print(f"Error: {str(e)}")

        print()

if __name__ == "__main__":
    # Check if required environment variables are set
    required_env_vars = ["OPENAI_API_KEY", "OPENAI_API_BASE_URL"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file or environment")
        sys.exit(1)

    # Run the async test
    try:
        asyncio.run(test_select_department())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        sys.exit(1)
