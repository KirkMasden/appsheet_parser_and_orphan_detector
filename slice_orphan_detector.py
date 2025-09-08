#!/usr/bin/env python3
"""
AppSheet Slice Orphan Detector

Identifies slices that are not referenced anywhere in the application.
A slice is considered an orphan if it's not used as a data source for views,
not referenced in actions, and not referenced in column formulas.

Usage:
    python slice_orphan_detector.py "/path/to/parse/directory/"
"""

import csv
import sys
import os
import re
from pathlib import Path
from collections import defaultdict


class SliceOrphanDetector:
    def __init__(self, parse_directory):
        self.parse_dir = Path(parse_directory)
        self.slices = []
        self.slice_references = defaultdict(int)
        
        # Expected CSV files
        self.csv_files = {
            'slices': 'appsheet_slices.csv',
            'views': 'appsheet_views.csv',
            'actions': 'appsheet_actions.csv',
            'columns': 'appsheet_columns.csv',
            'format_rules': 'appsheet_format_rules.csv'
        }
    
    def validate_files(self):
        """Check that all required CSV files exist"""
        missing_files = []
        for file_type, filename in self.csv_files.items():
            file_path = self.parse_dir / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        if missing_files:
            print(f"  ❌ ERROR: Missing required files: {', '.join(missing_files)}")
            print(f"     Expected location: {self.parse_dir}")
            return False
        return True
    
    def load_slices(self):
        """Load all slices from appsheet_slices.csv"""
        slices_file = self.parse_dir / self.csv_files['slices']
        
        with open(slices_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Capture ALL fields from the CSV row
                slice_data = row.copy()
                self.slices.append(slice_data)
        
        print(f"  ✓ Found {len(self.slices)} slices")
    
    def is_always_false_condition(self, condition):
        """Check if a row filter condition is always false"""
        if not condition:
            return False
            
        condition_lower = condition.strip().lower()
        
        # Direct false conditions
        if condition_lower in ['false', 'false()', '=false', '=false()']:
            return True
        
        # Simple always-false comparisons
        always_false_patterns = [
            r'^\s*1\s*=\s*2\s*$',
            r'^\s*=\s*1\s*=\s*2\s*$',
            r'^\s*"a"\s*=\s*"b"\s*$',
            r'^\s*=\s*"a"\s*=\s*"b"\s*$',
            r'^\s*true\s*=\s*false\s*$',
            r'^\s*=\s*true\s*=\s*false\s*$'
        ]
        
        for pattern in always_false_patterns:
            if re.match(pattern, condition_lower):
                return True
                
        return False
    
    def check_view_references(self):
        """Check which slices are used as data sources in views"""
        views_file = self.parse_dir / self.csv_files['views']
        referenced_slices = set()
        
        with open(views_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                data_source = row.get('data_source', '')
                if data_source:
                    referenced_slices.add(data_source.lower())
        
        return referenced_slices
    
    def search_slice_references_in_formulas(self, text, slice_names):
        """Search for slice references in formula text"""
        references = set()
        
        if not text:
            return references
            
        # Look for patterns like SliceName[Column]
        for slice_name in slice_names:
            # Exact match with brackets
            if f"{slice_name}[" in text:
                references.add(slice_name.lower())
            
            # Check for slice name in SELECT, FILTER, etc.
            patterns = [
                rf'\bSELECT\s*\(\s*"{slice_name}"',
                rf'\bFILTER\s*\(\s*"{slice_name}"',
                rf'\bLOOKUP\s*\(\s*[^,]+,\s*"{slice_name}"',
                rf'\bIN\s*\([^,]+,\s*{slice_name}\[',
                rf'\bREF_ROWS\s*\(\s*"{slice_name}"'
            ]
            
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    references.add(slice_name.lower())
                    
        return references
    
    def check_action_references(self):
        """Check which slices are referenced in actions"""
        actions_file = self.parse_dir / self.csv_files['actions']
        referenced_slices = set()
        
        # Get all slice names for searching
        slice_names = [s['slice_name'] for s in self.slices]
        
        with open(actions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Check source table (might be a slice)
                source_table = row.get('source_table', '')
                if source_table in slice_names:
                    referenced_slices.add(source_table.lower())
                
                # Check referenced columns field for slice references
                ref_cols = row.get('referenced_columns', '')
                refs = self.search_slice_references_in_formulas(ref_cols, slice_names)
                referenced_slices.update(refs)
                
                # Check other formula fields
                for field in ['only_if_condition', 'to_this_value', 'with_these_properties']:
                    formula = row.get(field, '')
                    refs = self.search_slice_references_in_formulas(formula, slice_names)
                    referenced_slices.update(refs)
        
        return referenced_slices
    
    def check_column_references(self):
        """Check which slices are referenced in column formulas"""
        columns_file = self.parse_dir / self.csv_files['columns']
        referenced_slices = set()
        
        # Get all slice names for searching
        slice_names = [s['slice_name'] for s in self.slices]
        
        with open(columns_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Check app_formula
                app_formula = row.get('app_formula', '')
                refs = self.search_slice_references_in_formulas(app_formula, slice_names)
                referenced_slices.update(refs)
                
                # Check referenced_columns field
                ref_cols = row.get('referenced_columns', '')
                refs = self.search_slice_references_in_formulas(ref_cols, slice_names)
                referenced_slices.update(refs)
                
                # Check other formula fields
                for field in ['initial_value', 'valid_if', 'show_if', 'required_if', 
                             'editable_if', 'reset_if', 'suggested_values']:
                    formula = row.get(field, '')
                    refs = self.search_slice_references_in_formulas(formula, slice_names)
                    referenced_slices.update(refs)
        
        return referenced_slices
    
    def check_format_rule_references(self):
        """Check which slices are referenced in format rules"""
        format_rules_file = self.parse_dir / self.csv_files['format_rules']
        referenced_slices = set()
        
        # Get all slice names for searching
        slice_names = [s['slice_name'] for s in self.slices]
        
        with open(format_rules_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Check source table (might be a slice)
                source_table = row.get('source_table', '')
                if source_table in slice_names:
                    referenced_slices.add(source_table.lower())
                
                # Check condition
                condition = row.get('condition', '')
                refs = self.search_slice_references_in_formulas(condition, slice_names)
                referenced_slices.update(refs)
        
        return referenced_slices
    
    def find_orphan_candidates(self):
        """Find slices that are potential orphans"""
        orphan_candidates = []
        
        # Get all references
        view_refs = self.check_view_references()
        action_refs = self.check_action_references()
        column_refs = self.check_column_references()
        format_rule_refs = self.check_format_rule_references()
        
        # Combine all references
        all_refs = view_refs | action_refs | column_refs | format_rule_refs
        
        for slice_data in self.slices:
            slice_name = slice_data['slice_name']
            slice_name_lower = slice_name.lower()
                        
            # Check if slice is referenced anywhere
            is_referenced = slice_name_lower in all_refs
            
            if not is_referenced:
                
                # Create orphan candidate with all original data
                orphan_candidate = slice_data.copy()
                orphan_candidate['is_orphan'] = 'Yes'
                orphan_candidate['reference_count'] = 0
                orphan_candidates.append(orphan_candidate)
        
        return orphan_candidates
    
    def write_results_to_csv(self, orphan_candidates):
        """Write orphan candidates to CSV file with all fields"""
        output_file = self.parse_dir / 'potential_slice_orphans.csv'
        
        if not orphan_candidates:
            print("    No orphan candidates to write.")
            return None
        
        # Get all field names from the first orphan candidate
        fieldnames = list(orphan_candidates[0].keys())
        
        # Ensure our added fields are at the end
        for field in ['is_orphan', 'reference_count']:
            if field in fieldnames:
                fieldnames.remove(field)
        fieldnames.extend(['is_orphan', 'reference_count'])
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            for candidate in orphan_candidates:
                writer.writerow(candidate)
        
        print(f"    ✓ Results written to: potential_slice_orphans.csv")
        return output_file
    
    def generate_summary_report(self, orphan_candidates, output_file):
        """Generate a summary report of findings"""
        print(f"\n  📊 Slice Orphan Detection Summary:")
        print(f"    Total slices analyzed: {len(self.slices)}")
        
        print()
                
        if orphan_candidates:
            print(f"    ⚠️  Potential orphans found: {len(orphan_candidates)}")
            
            # Group by source table
            by_table = defaultdict(list)
            for orphan in orphan_candidates:
                by_table[orphan['source_table']].append(orphan['slice_name'])
            
            print("\n    Table breakdown of potential orphans:")
            for table, slices in sorted(by_table.items()):
                print(f"      - {table}: {len(slices)}")
                # Show first few slice names
                for i, slice_name in enumerate(slices[:3]):
                    print(f"        • {slice_name}")
                if len(slices) > 3:
                    print(f"        ... and {len(slices) - 3} more")
            
            if output_file:
                print(f"\n  ✅ Results saved to: potential_slice_orphans.csv")
        else:
            print(f"    ✅ No potential orphans detected")
    
    def run_analysis(self):
        """Main analysis workflow"""
        print("🔍 Starting Slice Orphan Detection...")
        print(f"  📂 Directory: {self.parse_dir}")
        
        # Validate files exist
        print("\n  ✓ Validating required files...")
        if not self.validate_files():
            return None
        
        # Load all slices
        print("\n  📊 Extracting slices...")
        self.load_slices()
        
        if not self.slices:
            print("\n    No slices found. Nothing to analyze.")
            return []
        
        # Find orphan candidates
        print("\n  🔍 Searching for potential orphans...")
        print("    Checking view data sources...")
        print("    Checking action references...")
        print("    Checking column formula references...")
        print("    Checking format rule references...")
        
        orphan_candidates = self.find_orphan_candidates()
        
        # Write results
        output_file = None
        if orphan_candidates:
            print("\n  💾 Writing results...")
            output_file = self.write_results_to_csv(orphan_candidates)
        
        # Generate summary
        self.generate_summary_report(orphan_candidates, output_file)
        
        return orphan_candidates


def main():
    if len(sys.argv) != 2:
        print("Usage: python slice_orphan_detector.py '/path/to/parse/directory/'")
        print("\nExample:")
        print("python slice_orphan_detector.py '/Users/kirkmasden/Desktop/20250621_125149_parse/'")
        sys.exit(1)
    
    parse_directory = sys.argv[1]
    
    if not os.path.exists(parse_directory):
        print(f"ERROR: Directory does not exist: {parse_directory}")
        sys.exit(1)
    
    detector = SliceOrphanDetector(parse_directory)
    orphan_candidates = detector.run_analysis()
    
    if orphan_candidates is not None:
        print(f"\nSlice orphan detection completed successfully!")
        if orphan_candidates:
            if len(orphan_candidates) == 1:
                print(f"Found 1 potential orphan slice.")
            else:
                print(f"Found {len(orphan_candidates)} potential orphan slices.")
        else:
            print("No orphan slices detected.")
    else:
        print("\nSlice orphan detection failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()