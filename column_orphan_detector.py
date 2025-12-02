#!/usr/bin/env python3
"""
AppSheet Virtual Column Orphan Detector

Identifies virtual columns that are not referenced by any other components
(views, actions, format rules, slices, or other columns).

Usage:
    python orphan_detector.py "/path/to/parse/directory/"
    
Example:
    python orphan_detector.py "/Users/kirkmasden/Desktop/250608 2132 Orphan columns/250610 1836 parse test/20250621_125149_parse/"
"""

import csv
import sys
import os
from pathlib import Path
from collections import defaultdict
import re


class VirtualColumnOrphanDetector:
    def __init__(self, parse_directory):
        self.parse_dir = Path(parse_directory)
        self.virtual_columns = []
        self.reference_counts = defaultdict(int)
        self.unused_system_views = set()  # Add this line
        
        # Expected CSV files
        self.csv_files = {
            'columns': 'appsheet_columns.csv',
            'views': 'appsheet_views.csv', 
            'actions': 'appsheet_actions.csv',
            'format_rules': 'appsheet_format_rules.csv',
            'slices': 'appsheet_slices.csv'
        }
        
        # Load unused system views immediately
        self.load_unused_system_views()  # Add this line

    def load_unused_system_views(self):
        """Load list of unused system views from view orphan detector output"""
        unused_views_file = self.parse_dir / 'unused_system_views.csv'
        self.unused_system_views = set()
        
        if unused_views_file.exists():
            with open(unused_views_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.unused_system_views.add(row['view_name'].lower())
            print(f"  ✓ Loaded {len(self.unused_system_views)} unused system views to exclude")
            print(f"    Note: Columns appearing only on unreachable views will be flagged as potential orphans")
        else:
            print("  ℹ️ No unused system views file found - all views will be considered")
    
    def validate_files(self):
        """Check that all required CSV files exist"""
        missing_files = []
        for file_type, filename in self.csv_files.items():
            file_path = self.parse_dir / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        if missing_files:
            print(f"\n  ❌ ERROR: Missing required files: {', '.join(missing_files)}")
            print(f"     Expected location: {self.parse_dir}")
            return False
        return True

    def extract_virtual_columns(self):
        """Extract all virtual columns from appsheet_columns.csv"""
        columns_file = self.parse_dir / self.csv_files['columns']
        
        with open(columns_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                if row.get('is_virtual', '') == 'Yes':  # is_virtual = Yes
                    # Keep the entire row instead of just selected fields
                    virtual_column = row.copy()
                    self.virtual_columns.append(virtual_column)
        
    def load_all_ref_columns(self):
        """Load ALL Ref columns, not just virtual ones"""
        columns_file = self.parse_dir / self.csv_files['columns']
        self.all_ref_columns = []
        
        with open(columns_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                if row.get('type', '') == 'Ref':  # type = Ref
                    ref_column = {
                        'table_name': row.get('table_name', ''),
                        'unique_identifier': row.get('unique_identifier', ''),
                        'ref_table': row.get('ref_table', '').strip()
                    }
                    self.all_ref_columns.append(ref_column)

    def search_references_in_file(self, file_type, target_column):
        """Search for references to target_column in specified file type"""
        file_path = self.parse_dir / self.csv_files[file_type]
        count = 0
        
        # Convert target to lowercase for case-insensitive comparison
        target_lower = target_column.lower()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Skip unused system views when searching views file
                if file_type == 'views':
                    view_name = row.get('view_name', '').lower()
                    if view_name in self.unused_system_views:
                        continue
                
                # Get referenced_columns field, default to empty string if missing
                referenced_columns = row.get('referenced_columns', '')
                if referenced_columns:
                    # Split comma-separated references and check each one
                    references = [ref.strip() for ref in referenced_columns.split('|||')]
                    # Case-insensitive check
                    if any(ref.lower() == target_lower for ref in references):
                        count += 1
        
        return count
    
    def find_potential_orphans(self):
        """Find virtual columns with zero references across all files"""

        # Load view usage and view type info from appsheet_views.csv
        views_file    = self.parse_dir / self.csv_files['views']
        view_usage_map = {}
        view_type_map  = {}

        if views_file.exists():
            with open(views_file, newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    view_name      = row.get("view_name", "").strip()
                    
                    # Skip unused system views
                    if view_name.lower() in self.unused_system_views:
                        continue
                    
                    view_type      = row.get("view_type", "").strip()
                    referenced_cols = row.get("referenced_columns", "")
                    view_type_map[view_name] = view_type
                    usage_set = {c.strip() for c in referenced_cols.split("|||") if c.strip()}
                    view_usage_map[view_name] = usage_set

        # Build map: target_table → set of Ref column identifiers
        ref_by_table = defaultdict(set)
        for ref_col in self.all_ref_columns:  # Changed from self.virtual_columns
            target_table = ref_col.get('ref_table', '')
            if target_table:
                ref_by_table[target_table].add(ref_col['unique_identifier'])

        potential_orphans       = []
        system_generated_count  = 0
        label_count             = 0

        for i, virtual_col in enumerate(self.virtual_columns):
            if (i + 1) % 100 == 0:
                print(f"    Processing: {i + 1}/{len(self.virtual_columns)} virtual columns...")
            target       = virtual_col['unique_identifier']
            column_name  = virtual_col['column_name']
            app_formula  = virtual_col.get('app_formula', '')

            # Skip system-generated reverse-Refs
            if column_name.startswith('Related ') and 'REF_ROWS(' in app_formula:
                system_generated_count += 1
                continue

            # If this is a label column, only skip it if
            # at least one Ref → this table is shown in a non-inline view
            is_label = virtual_col.get('label', '')
            if is_label == 'Yes':
                table       = virtual_col['table_name']
                refs_for_table = ref_by_table.get(table, set())                
                label_used = False
                for ref_col in refs_for_table:
                    for view, usage in view_usage_map.items():
                        if ref_col in usage and view_type_map.get(view, '') != 'inline':
                            label_used = True
                            break
                    if label_used:
                        break

                if label_used:
                    label_count += 1
                    continue

            # Otherwise, count all other references
            total_references = 0
            file_ref_counts  = {}
            for file_type in self.csv_files:
                if file_type != 'columns':
                    count = self.search_references_in_file(file_type, target)
                    file_ref_counts[file_type] = count
                    total_references += count

            # Also search inside other columns
            columns_refs = self.search_references_in_file('columns', target)
            file_ref_counts['columns'] = columns_refs
            total_references += columns_refs

            if total_references == 0:
                potential_orphan = virtual_col.copy()
                potential_orphan.update(file_ref_counts)
                potential_orphan['total_references'] = total_references
                potential_orphans.append(potential_orphan)

        return potential_orphans, system_generated_count, label_count
    
    def write_results_to_csv(self, potential_orphans):
        """Write orphan candidates to CSV file in the parse directory"""
        output_file = self.parse_dir / 'potential_virtual_column_orphans.csv'
        
        # Include all original fields from appsheet_columns.csv plus our reference counts
        fieldnames = [
            'table_name', 'column_number', 'column_name', 'unique_identifier', 
            'is_virtual', 'type', 'description', 'referenced_columns', 'app_formula', 
            'display_name', 'initial_value', 'type_qualifier_formulas', 'type_qualifier', 
            'show_if', 'required_if', 'editable_if', 'valid_if', 'reset_if', 
            'suggested_values', 'formula_context_table', 'key', 'label', 'hidden', 
            'read-only', 'searchable', 'ref_table', 'component_type', 
            'editable_initial_value', 'fixed_definition', 'localename', 
            'nfc_scannable', 'part_of_key', 'raw_references', 'reset_on_edit', 
            'scannable', 'sensitive_data', 'spreadsheet_formula', 'system_defined',
            # Add our analysis fields at the end
            'total_references', 'columns_refs', 'views_refs', 'actions_refs', 
            'format_rules_refs', 'slices_refs'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            for candidate in potential_orphans:
                # Start with all the original fields from the candidate
                row = candidate.copy()
                # Remove the short field names that were added during analysis
                for field in ['columns', 'views', 'actions', 'format_rules', 'slices', 'total_references']:
                    row.pop(field, None)
                # Add our reference count fields with the correct names
                row.update({
                    'total_references': candidate.get('total_references', 0),
                    'columns_refs': candidate.get('columns', 0),
                    'views_refs': candidate.get('views', 0),
                    'actions_refs': candidate.get('actions', 0), 
                    'format_rules_refs': candidate.get('format_rules', 0),
                    'slices_refs': candidate.get('slices', 0)
                })
                writer.writerow(row)
        
        print(f"    ✓ Results written to: potential_virtual_column_orphans.csv")
        return output_file
    
    def run_analysis(self):
        """Main analysis workflow"""
        print("🔍 Starting Virtual Column Orphan Detection...")
        print(f"  📂 Directory: {self.parse_dir}")
        
        # Validate files exist
        print("\n  ✓ Validating required files...")
        if not self.validate_files():
            return None
        
        # Load unused system views (refresh in case file was created)
        print("\n  📊 Loading unused system views...")
        self.load_unused_system_views()
            
        # Extract virtual columns
        print("\n  📊 Extracting virtual columns...")
        self.extract_virtual_columns()
        self.load_all_ref_columns() 
        column_text = "virtual column" if len(self.virtual_columns) == 1 else "virtual columns"
        print(f"  ✓ Found {len(self.virtual_columns)} {column_text}")

        # Find orphan candidates  
        print("\n  🔍 Searching for potential orphans...")
        potential_orphans, system_generated_count, label_count = self.find_potential_orphans()
        
        # Write results only if orphans found
        output_file = None
        if potential_orphans:
            print("\n  💾 Writing results...")
            output_file = self.write_results_to_csv(potential_orphans)
        
        # Summary
        print(f"\n  📊 Orphan Detection Summary:")
        total_text = "virtual column" if len(self.virtual_columns) == 1 else "virtual columns"
        print(f"    Total {total_text} analyzed: {len(self.virtual_columns)}")
        ref_text = "column" if system_generated_count == 1 else "columns"
        print(f"    System-generated REF_ROWS {ref_text}: {system_generated_count}")
        label_text = "column" if label_count == 1 else "columns"
        print(f"    Label {label_text} (UI display): {label_count}")
        user_count = len(self.virtual_columns) - system_generated_count - label_count
        user_text = "column" if user_count == 1 else "columns"
        print(f"    User-created virtual {user_text}: {user_count}")

        print()  
        
        if potential_orphans:
            print(f"    ⚠️  Potential orphans found: {len(potential_orphans)}")
            print(f"\n  ✅ Results saved to: potential_virtual_column_orphans.csv")
        else:
            print(f"    ✅ No potential orphans detected")
        
        return potential_orphans

def main():
    if len(sys.argv) != 2:
        print("Usage: python orphan_detector.py '/path/to/parse/directory/'")
        print("\nExample:")
        print("python orphan_detector.py '/Users/kirkmasden/Desktop/250608 2132 Orphan columns/250610 1836 parse test/20250621_125149_parse/'")
        sys.exit(1)
    
    parse_directory = sys.argv[1]
    
    if not os.path.exists(parse_directory):
        print(f"ERROR: Directory does not exist: {parse_directory}")
        sys.exit(1)
    
    detector = VirtualColumnOrphanDetector(parse_directory)
    potential_orphans = detector.run_analysis()
    
    if potential_orphans is not None:
        print(f"\n✅ Column orphan detection complete!")
    else:
        print("\n❌ Column orphan detection failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()