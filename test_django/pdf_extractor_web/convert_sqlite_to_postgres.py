import csv
import json

# Define the input and output file paths
input_file = "tim_and_gene_data.sql"
output_file = "tim_and_gene_data_postgres.sql"


def convert_sqlite_to_postgres(input_file, output_file):
    with open(input_file, "r") as infile, open(output_file, "w") as outfile:
        reader = csv.reader(infile, delimiter="|")
        for row in reader:
            # Properly format JSON fields
            custom_categories = json.dumps(json.loads(row[3]))
            industry_keywords = json.dumps(json.loads(row[4]))
            category_patterns = json.dumps(json.loads(row[5]))
            category_hierarchy = json.dumps(json.loads(row[7]))
            profile_data = json.dumps(json.loads(row[9]))

            # Construct the INSERT statement
            insert_statement = f"INSERT INTO business_profiles (client_id, business_type, business_description, custom_categories, industry_keywords, category_patterns, industry_insights, category_hierarchy, business_context, profile_data) VALUES ('{row[0]}', '{row[1]}', '{row[2]}', '{custom_categories}', '{industry_keywords}', '{category_patterns}', '{row[6]}', '{category_hierarchy}', '{row[8]}', '{profile_data}');\n"
            outfile.write(insert_statement)


# Run the conversion
convert_sqlite_to_postgres(input_file, output_file)

print(f"Conversion complete. Output written to {output_file}")
