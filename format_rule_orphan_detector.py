#!/usr/bin/env python3
"""
Format Rule Orphan Detector for AppSheet
Identifies format rules that may be orphaned/unused.
"""

import csv
import os
import re
from collections import defaultdict

class FormatRuleOrphanDetector:
    """Detects orphaned format rules in AppSheet applications."""
    
    def __init__(self, parse_directory):
        """Initialize with the directory containing parsed CSV files."""
        self.parse_directory = parse_directory
        self.format_rules = []
        self.columns_by_table = defaultdict(set)
        self.actions_by_table = defaultdict(set)
        self.views = []
        self.view_columns_by_table = defaultdict(set)
        self.view_actions_by_table = defaultdict(set)
        self.slices = {}
        self.potential_view_orphans = set()
        self.unused_system_views = set()
        
    def validate_files(self):
        """Ensure all required CSV files exist."""
        required_files = [
            'appsheet_format_rules.csv',
            'appsheet_columns.csv',
            'appsheet_actions.csv',
            'appsheet_views.csv',
            'appsheet_slices.csv'
        ]
        
        print("  ✓ Validating required files...")
        
        for file in required_files:
            filepath = os.path.join(self.parse_directory, file)
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Required file not found: {file}")
                
        # Check for optional view orphans file
        view_orphans_file = os.path.join(self.parse_directory, 'potential_view_orphans.csv')
        if os.path.exists(view_orphans_file):
            self.load_view_orphans(view_orphans_file)

        # Check for optional unused system views file
        unused_system_views_file = os.path.join(self.parse_directory, 'unused_system_views.csv')
        if os.path.exists(unused_system_views_file):
            self.load_unused_system_views(unused_system_views_file)
            
    def load_view_orphans(self, filepath):
        """Load potential view orphans from Phase 8."""
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.potential_view_orphans.add(row['view_name'])

    def load_unused_system_views(self, filepath):
        """Load unused system views from Phase 8."""
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.unused_system_views.add(row['view_name'])
                
    def load_format_rules(self):
        """Load format rules from CSV."""
        filepath = os.path.join(self.parse_directory, 'appsheet_format_rules.csv')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.format_rules = list(reader)
            
        print(f"  ✓ Found {len(self.format_rules)} format rules")
        
    def load_slices_data(self):
        """Load slice mappings."""
        filepath = os.path.join(self.parse_directory, 'appsheet_slices.csv')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.slices[row['slice_name']] = row['source_table']
                
    def load_columns_data(self):
        """Load column data and organize by table."""
        filepath = os.path.join(self.parse_directory, 'appsheet_columns.csv')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                table = row['table_name']
                column = row['column_name']
                self.columns_by_table[table].add(column)
                
    def load_actions_data(self):
        """Load actions data and organize by table."""
        filepath = os.path.join(self.parse_directory, 'appsheet_actions.csv')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                table = row['source_table']
                action = row['action_name']
                # Include ALL actions (both system and user) for format rule checking
                self.actions_by_table[table].add(action)
                    
    def load_views_data(self):
        """Load views data and extract columns/actions used in views."""
        filepath = os.path.join(self.parse_directory, 'appsheet_views.csv')
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.views = list(reader)
            
        # Extract columns and actions visible in views
        for view in self.views:
            table = view['source_table']
            # Skip unused system views
            if view['view_name'] in self.unused_system_views:
                continue
            
            # Get columns shown in this view
            view_cols = view.get('view_columns', '')
            if view_cols:
                for col in view_cols.split('|||'):
                    col = col.strip()
                    if col:
                        self.view_columns_by_table[table].add(col)
                        
            # Get actions shown in this view
            ref_actions = view.get('referenced_actions', '')
            if ref_actions:
                for action in ref_actions.split('|||'):
                    action = action.strip()
                    if action:
                        self.view_actions_by_table[table].add(action)
                        
            # Also check available_actions
            avail_actions = view.get('available_actions', '')
            if avail_actions:
                for action in avail_actions.split('|||'):
                    action = action.strip()
                    if action:
                        self.view_actions_by_table[table].add(action)
                        
    def check_column_exists(self, table, column):
        """Check if a column exists in the specified table."""
        # First check the direct table
        if column in self.columns_by_table.get(table, set()):
            return True
            
        # If table is a slice, check the source table
        if table in self.slices:
            source_table = self.slices[table]
            if column in self.columns_by_table.get(source_table, set()):
                return True
                
        return False
        
    def check_action_exists(self, table, action):
        """Check if an action exists for the specified table."""
        # First check the direct table
        if action in self.actions_by_table.get(table, set()):
            return True
            
        # If table is a slice, check the source table
        if table in self.slices:
            source_table = self.slices[table]
            if action in self.actions_by_table.get(source_table, set()):
                return True
                
        return False
        
    def check_column_visibility(self, table, column):
        """Check if a column is visible in any view."""
        # Check direct table
        if column in self.view_columns_by_table.get(table, set()):
            return True
            
        # If table is a slice, also check source table views
        if table in self.slices:
            source_table = self.slices[table]
            if column in self.view_columns_by_table.get(source_table, set()):
                return True
                
        return False
        
    def check_action_visibility(self, table, action):
        """Check if an action is visible in any view."""
        # Check direct table
        if action in self.view_actions_by_table.get(table, set()):
            return True
            
        # If table is a slice, also check source table views
        if table in self.slices:
            source_table = self.slices[table]
            if action in self.view_actions_by_table.get(source_table, set()):
                return True
                
        return False
        
    def is_always_false_condition(self, condition):
        """Check if a condition is always false."""
        if not condition:
            return False
            
        condition_lower = condition.lower().strip()
        
        # Common always-false patterns
        always_false_patterns = [
            r'^false$',
            r'^false\(\)$',
            r'^"false"$',
            r"^'false'$",
            r'^0\s*=\s*1$',
            r'^1\s*=\s*0$',
            r'^1\s*=\s*2$',
            r'^true\s*=\s*false$',
            r'^false\s*=\s*true$',
        ]
        
        for pattern in always_false_patterns:
            if re.match(pattern, condition_lower):
                return True
                
        return False
        
    def find_orphan_candidates(self):
        """Identify format rules that are likely orphaned."""
        orphan_candidates = []
        
        for rule in self.format_rules:
            rule_name = rule['rule_name']
            source_table = rule['source_table']
            is_disabled = rule.get('is_disabled', 'No') == 'Yes'
            reasons = []
            
            # For disabled rules, add that as a reason
            if is_disabled:
                reasons.append("Already disabled")
            
            # Check for always-false condition
            condition = rule.get('condition', '')
            if self.is_always_false_condition(condition):
                reasons.append("Has always-false condition")
                
            # Check formatted columns
            formatted_columns = rule.get('formatted_columns', '')
            if formatted_columns:
                missing_columns = []
                never_shown_columns = []
                visible_columns = []
                
                for col in formatted_columns.split('|||'):
                    col = col.strip()
                    if col:
                        # Check if column exists
                        if not self.check_column_exists(source_table, col):
                            missing_columns.append(col)
                        # Check if column is ever shown
                        elif not self.check_column_visibility(source_table, col):
                            never_shown_columns.append(col)
                        else:
                            visible_columns.append(col)
                            
                # Only flag as orphan if ALL columns are missing
                if missing_columns and not visible_columns:
                    reasons.append(f"Formats only non-existent columns: {', '.join(missing_columns)}")
                # Only flag as orphan if ALL columns are never shown
                elif never_shown_columns and not visible_columns and not missing_columns:
                    reasons.append(f"Formats only never-displayed columns: {', '.join(never_shown_columns)}")
                    
            # Check formatted actions
            formatted_actions = rule.get('formatted_actions', '')
            if formatted_actions:
                missing_actions = []
                never_shown_actions = []
                
                for action in formatted_actions.split('|||'):
                    action = action.strip()
                    if action:
                        # Check if action exists
                        if not self.check_action_exists(source_table, action):
                            missing_actions.append(action)
                        # Check if action is ever shown
                        elif not self.check_action_visibility(source_table, action):
                            never_shown_actions.append(action)
                            
                if missing_actions:
                    reasons.append(f"Formats non-existent actions: {', '.join(missing_actions)}")
                if never_shown_actions:
                    reasons.append(f"Formats never-displayed actions: {', '.join(never_shown_actions)}")
                    
            # If we found any reasons, it's an orphan candidate
            if reasons:
                # Create orphan candidate with all original data
                orphan_candidate = rule.copy()
                orphan_candidate['is_orphan'] = 'Yes'
                orphan_candidate['formatted_items_count'] = int(rule.get('formatted_columns_count', 0)) + int(rule.get('formatted_actions_count', 0))
                orphan_candidates.append(orphan_candidate)
                
        return orphan_candidates
        
    def write_results_to_csv(self, orphan_candidates):
        """Write orphan detection results to CSV with all fields."""
        output_file = os.path.join(self.parse_directory, 'potential_format_rule_orphans.csv')
        
        if not orphan_candidates:
            print("    No orphan candidates to write.")
            return
        
        # Get all field names from the first orphan candidate
        fieldnames = list(orphan_candidates[0].keys())
        
        # Ensure our added fields are at the end
        for field in ['is_orphan', 'formatted_items_count']:
            if field in fieldnames:
                fieldnames.remove(field)
        fieldnames.extend(['is_orphan', 'formatted_items_count'])
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
            
            writer.writeheader()
            writer.writerows(orphan_candidates)
            
        print(f"    ✓ Results written to: potential_format_rule_orphans.csv")
        
    def run_analysis(self):
        """Run the complete orphan detection analysis."""
        print("🔍 Starting Format Rule Orphan Detection...")
        # Clean up directory path for display
        clean_dir = str(self.parse_directory).lstrip('./')
        print(f"  📂 Directory: {clean_dir}")
        print()
        
        # Validate files exist
        self.validate_files()
        print()
        
        # Load all data
        print("  📊 Loading data...")
        self.load_slices_data()
        self.load_format_rules()
        self.load_columns_data()
        self.load_actions_data()
        self.load_views_data()
        print()
        
        # Find orphan candidates
        print("  🔍 Searching for potential orphans...")
        orphan_candidates = self.find_orphan_candidates()
        
        # Count disabled rules
        disabled_count = sum(1 for rule in self.format_rules if rule.get('is_disabled', 'No') == 'Yes')
        
        if orphan_candidates:
            print()
            print("  💾 Writing results...")
            self.write_results_to_csv(orphan_candidates)
        
        # Print summary
        print()
        print("  📊 Format Rule Orphan Detection Summary:")
        print(f"    Total format rules analyzed: {len(self.format_rules)}")
        print(f"    Disabled rules (excluded): {disabled_count}")
        print(f"    Active rules checked: {len(self.format_rules) - disabled_count}")
        
        print()  # Add this blank line

        if orphan_candidates:
            print(f"    ⚠️  Potential orphans found: {len(orphan_candidates)}")
            
            print()
            print("  Table breakdown of potential orphans:")
            table_counts = defaultdict(list)
            for candidate in orphan_candidates:
                table_counts[candidate['source_table']].append(candidate['rule_name'])
                
            for table, rules in sorted(table_counts.items()):
                print(f"     - {table}: {len(rules)}")
                for rule in sorted(rules):
                    print(f"       • {rule}")
            
            print()
            print(f"  ✅ Results saved to: potential_format_rule_orphans.csv")
        else:
            print(f"    ✅ No potential orphans detected")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python format_rule_orphan_detector.py <parse_directory>")
        sys.exit(1)
        
    parse_dir = sys.argv[1]
    
    if not os.path.exists(parse_dir):
        print(f"Error: Directory not found: {parse_dir}")
        sys.exit(1)
        
    detector = FormatRuleOrphanDetector(parse_dir)
    detector.run_analysis()