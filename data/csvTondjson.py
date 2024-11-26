import csv
import json

def csv_to_ndjson_thai(csv_file_path, ndjson_file_path):
    # Open the CSV file with proper encoding for Thai
    with open(csv_file_path, mode='r', encoding='utf-8-sig') as csv_file:
        reader = csv.DictReader(csv_file)  # Read CSV rows as dictionaries
        
        # Open the NDJSON file for writing
        with open(ndjson_file_path, mode='w', encoding='utf-8') as ndjson_file:
            for row in reader:
                # Convert each row dictionary to a JSON object and write to NDJSON
                ndjson_file.write(json.dumps(row, ensure_ascii=False) + '\n')

# Example usage
csv_to_ndjson_thai('C:\Elasticsearch\Thai_Temples_Search\data\Final_Temple.csv', 'C:\Elasticsearch\Thai_Temples_Search\data\output.ndjson')
