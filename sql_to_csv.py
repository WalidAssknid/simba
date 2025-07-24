#!/usr/bin/env python3
"""
Script to convert PostgreSQL COPY data to CSV files
Removes ID columns so Django ORM can generate them automatically
"""

import re
import csv
import os

def extract_table_data(input_file):
    """Extracts data from all tables in the SQL file"""
    tables_data = {}
    
    with open(input_file, 'r', encoding='utf-8') as f:
        current_table = None
        current_columns = None
        in_data_section = False
        
        for line in f:
            # Detect start of COPY section
            match = re.match(r'COPY public\.(\w+) \(([^)]+)\) FROM stdin;', line)
            if match:
                current_table = match.group(1)
                current_columns = [col.strip().strip('"') for col in match.group(2).split(',')]
                in_data_section = True
                tables_data[current_table] = {
                    'columns': current_columns,
                    'data': []
                }
                print(f"Processing table: {current_table}")
                continue
                
            # Detect end of data section
            if line.strip() == '\\.':
                in_data_section = False
                current_table = None
                current_columns = None
                continue
                
            # Process data line
            if in_data_section and current_table and current_columns:
                if line.strip():  # Ignore empty lines
                    # Split by tabs and clean line breaks
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) == len(current_columns):
                        tables_data[current_table]['data'].append(fields)
                        
    return tables_data

def save_to_csv(tables_data, output_dir='csv_data'):
    """Saves table data to CSV files, removing ID fields"""
    
    # Create directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Map which columns to remove (IDs that Django will generate automatically)
    id_columns_to_remove = {
        'simbaapp_user': ['id'],
        'simbaapp_course': ['id'],
        'simbaapp_activity': ['id'], 
        'simbaapp_courseenrollment': ['id'],
        'simbaapp_thread': ['id'],
        'simbaapp_message': ['id'],
        'simbaapp_analytics': ['id'],
        'simbaapp_event': ['id'],
        'simbaapp_chainlitsession': ['id'],
        'simbaapp_emailverificationtoken': ['id'],
        'simbaapp_passwordresettoken': ['id'],
        'simbaapp_invitetoken': ['id'],
        'simbaapp_activitytoken': ['id']
    }
    
    for table_name, table_info in tables_data.items():
        columns = table_info['columns']
        data = table_info['data']
        
        # Remove ID columns that Django will generate
        columns_to_remove = id_columns_to_remove.get(table_name, [])
        
        # Find indexes of columns to remove
        indexes_to_remove = []
        for col_to_remove in columns_to_remove:
            if col_to_remove in columns:
                indexes_to_remove.append(columns.index(col_to_remove))
        
        # Remove columns from headers
        filtered_columns = [col for i, col in enumerate(columns) if i not in indexes_to_remove]
        
        # Remove columns from data
        filtered_data = []
        for row in data:
            filtered_row = [field for i, field in enumerate(row) if i not in indexes_to_remove]
            filtered_data.append(filtered_row)
        
        # Save CSV
        csv_file = os.path.join(output_dir, f'{table_name}.csv')
        with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(filtered_columns)  # Header
            writer.writerows(filtered_data)    # Data
            
        print(f"Saved: {csv_file} ({len(filtered_data)} records, {len(filtered_columns)} columns)")

def main():
    input_file = 'simbaapp.sql'
    
    if not os.path.exists(input_file):
        print(f"File {input_file} not found!")
        return
        
    print("Extracting data from SQL file...")
    tables_data = extract_table_data(input_file)
    
    print(f"\nFound {len(tables_data)} tables:")
    for table_name, info in tables_data.items():
        print(f"  {table_name}: {len(info['data'])} records")
    
    print("\nSaving CSV files...")
    save_to_csv(tables_data)
    
    print("\nCompleted! CSV files saved in 'csv_data/' directory")

if __name__ == "__main__":
    main() 