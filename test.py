# fix_csv.py
import csv

input_file = 'cameras.csv'
output_file = 'cameras_fixed.csv'

print(f"Reading: {input_file}")

with open(input_file, 'r', encoding='utf-8') as infile, \
     open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    
    reader = csv.DictReader(infile)
    
    # New fieldnames with 'critical' column
    fieldnames = ['name', 'ip', 'location', 'critical']
    
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    
    count = 0
    for row in reader:
        # Map old names to new names
        new_row = {
            'name': row.get('Name') or row.get('name') or f'Camera{count+1}',
            'ip': row.get('Ip') or row.get('ip') or '',
            'location': row.get('Location') or row.get('location') or '',
            'critical': 'YES'  # Default all to critical
        }
        
        writer.writerow(new_row)
        count += 1
    
    print(f"✅ Created {output_file} with {count} cameras")
    print(f"✅ Added 'critical' column with default value 'YES'")