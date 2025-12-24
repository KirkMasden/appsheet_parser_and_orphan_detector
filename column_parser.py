#!/usr/bin/env python3
"""
Column Parser for AppSheet HTML Documentation - Enhanced Version
Extracts column information with proper table associations and reference tracking.
Loads slice mappings from appsheet_slices.csv to resolve slice references.
Includes type_qualifier_formulas extraction for human readability.
"""

import os
import csv
import re
import json
from collections import defaultdict
from base_parser import BaseParser


class ColumnParser(BaseParser):
    """Parser for extracting column information from AppSheet HTML."""
    
    def __init__(self, html_path=None, html_string=None, soup=None, debug_mode=False):
        """Initialize the column parser with optional debug mode."""
        super().__init__(html_path, html_string, soup, debug_mode=debug_mode)
        
        # Column-specific data structures
        self.columns_data = []
        self.table_column_counts = defaultdict(int)
        self.column_to_table_map = defaultdict(list)  # Track columns appearing in multiple tables
 
        # Track system-generated tables
        self.system_generated_tables = []
        self.total_tables_found = 0

        # Load slice mapping if available
        self.load_slice_mapping() 

    def identify_system_generated_tables(self):
        """Pre-scan HTML to identify all tables with native data source.
        
        Exception: _Per User Settings is kept (not filtered) because it contains
        user-configured columns that may be referenced by USERSETTINGS() expressions.
        """
        print("  🔍 Scanning for system-generated tables...")
        
        # Find all table sections (not schema sections)
        tables = self.soup.find_all('h5', id=lambda x: x and x.startswith('table_') and not x.endswith('_Schema'))
        
        for table_header in tables:
            table_name = None
            # Extract table name from the h5 text content
            text_content = table_header.get_text(strip=True)
            if text_content.startswith('Table name'):
                table_name = text_content.replace('Table name', '').strip()
            else:
                # Try to extract from id
                table_id = table_header.get('id', '')
                if table_id.startswith('table_'):
                    table_name = table_id[6:]  # Remove 'table_' prefix
            
            if table_name:
                # Find the adjacent table with data
                data_table = table_header.find_next_sibling('table', class_='react-bridge-group')
                if data_table:
                    # Look for Data Source row
                    for row in data_table.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            label_text = cells[0].get_text(strip=True)
                            value_text = cells[1].get_text(strip=True)
                            
                            if 'Data Source' in label_text and value_text.lower() == 'native':
                                # Keep _Per User Settings - it contains user-configured columns
                                # that may be referenced by USERSETTINGS() expressions
                                if table_name != '_Per User Settings':
                                    self.system_generated_tables.append(table_name)
                                break
        
        print(f"  ✅ Found {len(self.system_generated_tables)} system-generated tables to filter")
        if self.system_generated_tables:
            for table in sorted(self.system_generated_tables):
                print(f"      - {table}")

    def load_slice_mapping(self, csv_path='appsheet_slices.csv'):
        """Load slice-to-table mapping from the slices CSV."""
        if os.path.exists(csv_path):
            print(f"  📂 Loading slice mapping from {csv_path}")
            slice_count = 0
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    slice_name = row.get('slice_name', '')
                    source_table = row.get('source_table', '')
                    if slice_name and source_table:
                        self.slice_to_table_map[slice_name] = source_table
                        slice_count += 1
                        
            if slice_count == 0:
                print(f"  ℹ️  No slice mappings found (app has no slices)")
            else:
                print(f"  ✅ Loaded {slice_count} slice mappings")
            
            # Debug: Check if System language is loaded
            if self.debug_mode and slice_count > 0:
                if 'System language' in self.slice_to_table_map:
                    print(f"  DEBUG: 'System language' mapping loaded: {self.slice_to_table_map['System language']}")
                else:
                    print("  DEBUG: 'System language' NOT found in loaded mappings")
                    # Show what we have that's similar
                    for slice_name in self.slice_to_table_map:
                        if 'system' in slice_name.lower() or 'language' in slice_name.lower():
                            print(f"    Similar slice: '{slice_name}' -> '{self.slice_to_table_map[slice_name]}'")
        else:
            print(f"  ⚠️  Slice mapping file not found: {csv_path}")
            print(f"     Creating empty mapping (assuming no slices in app)")
 
    def extract_table_name_from_schema(self, schema_header):
        """Extract clean table name from schema header element."""
        # Method 1: Extract from ID (most reliable)
        schema_id = schema_header.get('id', '')
        if schema_id.startswith('table_') and schema_id.endswith('_Schema'):
            # Extract everything between 'table_' and '_Schema'
            table_name = schema_id[6:-7]
            return table_name
            
        # Method 2: Extract from text content
        # Get just the text nodes, not the label
        text_nodes = [t for t in schema_header.stripped_strings]
        for text in text_nodes:
            if text.endswith('_Schema'):
                # Remove the '_Schema' suffix
                table_name = text[:-7]
                # Remove any "Schema Name" prefix if it exists
                if table_name.startswith('Schema Name'):
                    table_name = table_name[11:].strip()
                return table_name
                
        return None
        
    def extract_formulas_from_type_qualifier(self, type_qualifier_json):
        """
        Extract AppSheet formulas from type_qualifier JSON.
        Returns a formatted string of formulas for human readability.
        """
        if not type_qualifier_json:
            return ''
            
        try:
            type_data = json.loads(type_qualifier_json)
            
            # Known formula fields in type_qualifier with their display names
            formula_fields = {
                'Valid_If': 'Valid_If',
                'Show_If': 'Show_If',
                'Required_If': 'Required_If',
                'Editable_If': 'Editable_If',
                'Reset_If': 'Reset_If',
                'Error_Message_If_Invalid': 'Error_Message',
                'Suggested_Values': 'Suggested_Values',
                'YesLabel': 'YesLabel',
                'NoLabel': 'NoLabel'
            }
            
            extracted_formulas = []
            
            for json_field, display_name in formula_fields.items():
                if json_field in type_data and type_data[json_field]:
                    formula_value = type_data[json_field]
                    # Only include if it looks like a formula (contains brackets, functions, etc.)
                    if isinstance(formula_value, str) and any(char in formula_value for char in ['[', ']', '(', ')']):
                        # Clean up the formula for display
                        formula_value = formula_value.strip()
                        extracted_formulas.append(f"{display_name}: {formula_value}")
            
            # Join with separator
            return ' | '.join(extracted_formulas) if extracted_formulas else ''
            
        except (json.JSONDecodeError, TypeError):
            # If JSON parsing fails, return empty
            return ''
        
    def parse_column(self, column_header, column_table, table_name, column_number):
        """Parse an individual column and its references."""
        header_text = column_header.get_text(strip=True)
        
        # Extract column name from header
        column_name = None
        if ':' in header_text:
            column_name = header_text.split(':', 1)[1].strip()
            
        if not column_name:
            return None
            
        # Debug mode for columns with slice references
        if self.debug_mode:
            # Check if this column might have slice references by looking at its data
            column_debug = False
            
        # Extract column data with reference tracking
        column_info = self.extract_component_data(
            column_table, 
            'column',
            {'_context_table': table_name}
        )
        
        if self.debug_mode and column_info.get('type') == 'Ref':
            if column_name == "Show WD stats" and table_name == "Kankaku":
                raw_tq = column_info.get('type_qualifier')
                print(f"  DEBUG: Raw type_qualifier for {table_name}[{column_name}] = {str(raw_tq)[:500]}")

        # Set essential fields
        column_info['table_name'] = table_name
        column_info['column_number'] = column_number
        column_info['column_name'] = column_name
        
        # Create unique identifier
        unique_id = f"{table_name}[{column_name}]"
        column_info['unique_identifier'] = unique_id
        
        # Track column-to-table mapping for ambiguity detection
        self.column_to_table_map[column_name].append(table_name)
        
        # Check if virtual
        virtual_value = column_info.get('virtual', column_info.get('is_a_virtual_column', ''))
        column_info['is_virtual'] = 'Yes' if virtual_value.lower() == 'yes' else 'No'
        
        # Extract formulas from type_qualifier for human readability
        if 'type_qualifier' in column_info and column_info['type_qualifier']:
            column_info['type_qualifier_formulas'] = self.extract_formulas_from_type_qualifier(
                column_info['type_qualifier']
            )
        else:
            column_info['type_qualifier_formulas'] = ''
        
        # Which table this Ref‑column points at
        if column_info.get('type') == 'Ref':
            try:
                tq = json.loads(column_info.get('type_qualifier', '{}'))
                ref_table_name = tq.get('ReferencedTableName', '')
                column_info['ref_table'] = ref_table_name.strip()
            except (json.JSONDecodeError, TypeError):
                column_info['ref_table'] = ''
        else:
            column_info['ref_table'] = ''


        # Extract references from formula fields
        formula_fields = ['app_formula', 'initial_value', 'valid_if', 'show_if', 
                         'required_if', 'editable_if', 'reset_if', 'display_name']
        
        all_refs = []
        
        # Check top-level formula fields
        for field in formula_fields:
            if field in column_info and column_info[field]:
                refs = self.extract_references_from_text(column_info[field], table_name)
                all_refs.extend(refs)
        
        # Also check type_qualifier which contains JSON with formula fields
        if 'type_qualifier' in column_info and column_info['type_qualifier']:
            if self.debug_mode and column_name == "Definition and example":
                print(f"  DEBUG: type_qualifier content: {column_info['type_qualifier'][:200]}...")
                
            try:
                type_data = json.loads(column_info['type_qualifier'])
                
                # Check formula fields within type_qualifier
                # These fields use different capitalization
                # Updated to include YesLabel and NoLabel
                type_formula_fields = {
                    'Valid_If': 'valid_if',
                    'Show_If': 'show_if',
                    'Required_If': 'required_if',
                    'Editable_If': 'editable_if',
                    'Reset_If': 'reset_if',
                    'Error_Message_If_Invalid': 'error_message',
                    'Suggested_Values': 'suggested_values',
                    'YesLabel': 'yes_label',
                    'NoLabel': 'no_label'
                }
                
                for json_field, display_field in type_formula_fields.items():
                    if json_field in type_data and type_data[json_field]:
                        if self.debug_mode and 'language' in str(type_data[json_field]).lower():
                            print(f"  DEBUG: Found potential slice reference in {json_field}: {type_data[json_field][:100]}...")
                            
                        refs = self.extract_references_from_text(type_data[json_field], table_name)
                        all_refs.extend(refs)
                        
            except (json.JSONDecodeError, TypeError) as e:
                if self.debug_mode:
                    print(f"  DEBUG: JSON parse error: {e}")
                # If JSON parsing fails, try to extract references from the raw string
                refs = self.extract_references_from_text(column_info['type_qualifier'], table_name)
                all_refs.extend(refs)
                
        # Build absolute references (resolving any slice references)
        if all_refs:
            if self.debug_mode:
                # Check if any references might be slices
                potential_slices = [ref for ref in all_refs if ref.get('is_slice_ref')]
                if potential_slices:
                    print(f"  DEBUG: Column {table_name}[{column_name}] has {len(potential_slices)} slice references")
                    for ref in potential_slices[:3]:  # Show first 3
                        print(f"    - {ref.get('original_table')}[{ref.get('column')}] -> {ref.get('table')}[{ref.get('column')}]")
                    
            absolute_refs = self.build_absolute_references(all_refs)
            column_info['referenced_columns'] = '|||'.join(absolute_refs)
            
        # Store formula context table
        column_info['formula_context_table'] = table_name
        
        # Check if Show_If makes this column always hidden
        if column_info.get('hidden', '').lower() != 'yes':
            # Extract Show_If from type_qualifier
            show_if = None
            if 'type_qualifier' in column_info and column_info['type_qualifier']:
                try:
                    type_data = json.loads(column_info['type_qualifier'])
                    show_if = type_data.get('Show_If', '')
                except:
                    pass
            
            # Check for always-false conditions
            if show_if:
                show_if_normalized = show_if.strip().upper()
                always_false_conditions = ['FALSE', '=FALSE', '=1=2', '=0=1', '=""=""']
                
                if show_if_normalized in always_false_conditions:
                    column_info['hidden'] = 'Yes'
                    # Add a comment to track why it's hidden
                    if self.debug_mode:
                        print(f"  DEBUG: Setting hidden=Yes for {table_name}[{column_name}] due to Show_If: {show_if}")
        
        # Mark this element as processed
        self.mark_element_processed(column_header.get('id', ''))
        
        return column_info
        
    def parse(self):
        """Parse all columns from the HTML."""
        print("  📊 Extracting columns...")
            
        # First, identify system-generated tables
        self.identify_system_generated_tables()

        # Find the schema section
        schema_section = self.soup.find('section', class_='schemaSection')
        
        if not schema_section:
            print("  ⚠️  No schema section found")
            return self.columns_data
            
        # Find all schema blocks (one per table)
        schema_blocks = schema_section.find_all('section', recursive=False)
        
        for schema_block in schema_blocks:
            # Find the schema header
            schema_header = schema_block.find('h5', id=lambda x: x and x.endswith('_Schema'))
            if not schema_header:
                continue
                
            # Extract table name
            table_name = self.extract_table_name_from_schema(schema_header)
            if not table_name:
                print(f"    ⚠️  Could not extract table name from schema header: {schema_header.get('id', 'no-id')}")
                continue
              
            self.total_tables_found += 1
            
            # Check if this is a system-generated table
            if table_name in self.system_generated_tables:
                continue  # Skip this table entirely

            # Find columns container
            schema_table = schema_header.find_next_sibling('table')
            if schema_table:
                columns_container = schema_table.find_next_sibling('div')
            else:
                columns_container = schema_header.find_next_sibling('div')
                
            if not columns_container:
                columns_container = schema_block
                
            # Find all column headers
            column_headers = columns_container.find_all('h3', 
                id=lambda x: x and x.startswith(f'table_{table_name}_Schema_col'))
            
            column_number = 0
            for column_header in column_headers:
                column_table = column_header.find_next_sibling('table')
                if column_table:
                    column_info = self.parse_column(
                        column_header, column_table, table_name, column_number + 1
                    )
                    
                    if column_info:
                        self.columns_data.append(column_info)
                        self.table_column_counts[table_name] += 1
                        column_number += 1
                                                
        # Print summary with system-generated table info
        if self.system_generated_tables:
            print(f"  ⚠️  System-generated tables filtered from results:")
            for table_name in sorted(self.system_generated_tables):
                print(f"      - {table_name}")
        
        # Calculate the actual number of user tables (excluding system-generated ones)
        user_table_count = len([t for t in self.table_column_counts if t not in self.system_generated_tables])
        print(f"    Total: {len(self.columns_data)} columns across {user_table_count} tables ({len(self.system_generated_tables)} system-generated tables filtered)")
        
        return self.columns_data
        
    def save_to_csv(self, output_path='appsheet_columns.csv'):
        """Save parsed columns to CSV file."""
        if not self.columns_data:
            print("  ⚠️  No column data to save")
            return
            
        # Define field order for columns - updated with type_qualifier_formulas
        # Placed right after initial_value as requested
        priority_fields = [
            'table_name', 
            'column_number', 
            'column_name', 
            'unique_identifier',
            'is_virtual', 
            'type',
            'description', 
            'referenced_columns',
            'app_formula', 
            'display_name',
            'initial_value',
            'type_qualifier_formulas',  # NEW: Human-readable formulas from type_qualifier
            'type_qualifier',           # Original JSON right after
            'show_if', 
            'required_if', 
            'editable_if', 
            'valid_if', 
            'reset_if',
            'suggested_values',
            'formula_context_table',
            'key',
            'label',
            'hidden',
            'read-only',
            'searchable',
            'ref_table'
        ]
        
        # Get all fields from the data
        all_fields = set()
        for col in self.columns_data:
            all_fields.update(col.keys())
            
        # Build final field list
        # Exclude redundant and meaningless fields
        excluded_fields = {'virtual', 'visible', 'is_ambiguous', 'formula_version'}
        other_fields = sorted([f for f in all_fields 
                              if f not in priority_fields 
                              and not f.startswith('_')
                              and f not in excluded_fields])        
        field_list = priority_fields + other_fields
        
        # Write CSV with proper quoting
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=field_list, extrasaction='ignore',
                                   quoting=csv.QUOTE_ALL)  # Add this!
            writer.writeheader()
            writer.writerows(self.columns_data)
            
        print(f"  ✅ Columns saved to: {output_path}")
        
def main():
    """Main function to run the column parser."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python column_parser.py <html_file_path> [--debug]")
        sys.exit(1)
        
    html_path = sys.argv[1]
    debug_mode = '--debug' in sys.argv
    
    if not os.path.exists(html_path):
        print(f"❌ Error: File not found: {html_path}")
        sys.exit(1)
        
    print("🔍 AppSheet Column Parser")
    if debug_mode:
        print("   🐛 DEBUG MODE ENABLED")
    print("=" * 50)
    
    parser = ColumnParser(html_path, debug_mode=debug_mode)
    
    try:
        parser.parse()
        parser.save_to_csv()
        
        print("\n✅ Column parsing complete!")
        
    except Exception as e:
        print(f"\n❌ Error during parsing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()