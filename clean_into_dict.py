import json
import re

import re
import json

def clean_json_string(json_string):
    # Step 1: Strip leading and trailing whitespace characters
    cleaned_json_string = json_string.strip()

    # Step 2: Replace the newline characters (\n) and fix escaped unicode sequences
    cleaned_json_string = cleaned_json_string.replace("\\n", '').replace("\\u00b0", "°")

    # Step 3: Remove any backslashes that may escape quotes improperly
    cleaned_json_string = cleaned_json_string.replace("\\", '')

    # Step 4: Ensure there are no unnecessary leading/trailing quotes or malformed endings
    if cleaned_json_string.startswith('"') and cleaned_json_string.endswith('"'):
        cleaned_json_string = cleaned_json_string[1:-1].strip()

    # Step 5: Remove any leftover problematic sequences like triple backticks or "n}" patterns
    cleaned_json_string = re.sub(r'```json|```', '', cleaned_json_string)
    cleaned_json_string = cleaned_json_string.replace('n}', '}')  # Fix incorrect 'n}' at the end

    # Step 6: Replace any malformed 'n' occurrences at the beginning of JSON blocks
    cleaned_json_string = re.sub(r'\bn\b\s*', '', cleaned_json_string)

    return cleaned_json_string

def process_json_lines(file_path):
    result = []
    
    with open(file_path, 'r') as f:
        for line in f:
            try:
                # Clean up the line
                cleaned_line = clean_json_string(line)
                # Attempt to load the cleaned line as a dictionary
                json_data = json.loads(cleaned_line)
                result.append(json_data)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                print("Problematic line:", cleaned_line)  # For debugging purposes
    
    return result

# Example usage
file_path = 'generated_patients.jsonl' # Replace with your actual file path
data = process_json_lines(file_path)




output_file = 'agentclinic_HealthCareMagic.json'
with open(output_file, 'w') as f:
    json.dump(data, f, indent=4)