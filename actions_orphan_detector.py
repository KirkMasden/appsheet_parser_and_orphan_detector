#!/usr/bin/env python3
"""
AppSheet Action Orphan Detector

Identifies user-created actions that are not referenced by any other components
(other actions, views) and are not attached to columns.

Usage:
    python actions_orphan_detector.py "/path/to/parse/directory/"
"""

import csv
import sys
import os
from pathlib import Path
from collections import defaultdict


class ActionOrphanDetector:
    def __init__(self, parse_directory):
        self.parse_dir = Path(parse_directory)
        self.all_actions = []
        self.user_actions = []
        self.referenced_actions = set()
        self.event_actions = set()
        self.unreachable_in_groups = {}
        self.unused_system_views = set()
        self.bot_actions = set() 
        
        # Expected CSV files
        self.csv_files = {
            'actions': 'appsheet_actions.csv',
            'views': 'appsheet_views.csv'
        }
        
        # Load unused system views immediately
        self.load_unused_system_views()  
        self.load_bot_actions() 

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
        else:
            print("  ℹ️ No unused system views file found - all views will be considered")

    def load_bot_actions(self):
        """Load list of actions used by bots from bot_actions.txt"""
        self.bot_actions = set()
        bot_actions_file = None
        
        # Try multiple locations for bot_actions.txt
        possible_locations = [
            self.parse_dir / 'bot_actions.txt',  # In parse output directory
            self.parse_dir.parent / 'bot_actions.txt',  # In parent directory
        ]
        
        # If parse_dir ends with _parse, also check the source directory
        parse_dir_name = self.parse_dir.name
        if '_parse' in parse_dir_name:
            # Extract the original directory name (remove timestamp and _parse)
            # Format: YYYYMMDD_HHMMSS_originalname_parse
            parts = parse_dir_name.split('_')
            if len(parts) >= 3:
                # Reconstruct original name (everything after timestamp, minus _parse)
                original_name = '_'.join(parts[2:-1])
                source_dir = self.parse_dir.parent / original_name.replace('_', ' ')
                possible_locations.append(source_dir / 'bot_actions.txt')
        
        # Find the file in one of the possible locations
        for location in possible_locations:
            if location.exists():
                bot_actions_file = location
                break
        
        if bot_actions_file:
            with open(bot_actions_file, 'r', encoding='utf-8') as f:
                for line in f:
                    action_name = line.strip()
                    if action_name:  # Skip empty lines
                        self.bot_actions.add(action_name.lower())
            print(f"  ✓ Loaded {len(self.bot_actions)} bot-used actions to exclude")
            print(f"    (from: {bot_actions_file.name})")
        else:
            print("  ℹ️ No bot_actions.txt file found - bot detection disabled")
            
    def validate_files(self):
        """Check that all required CSV files exist"""
        missing_files = []
        for file_type, filename in self.csv_files.items():
            file_path = self.parse_dir / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        if missing_files:
            print(f"ERROR: Missing required files: {', '.join(missing_files)}")
            print(f"Expected location: {self.parse_dir}")
            return False
        return True
    
    def load_actions(self):
        """Load all actions from appsheet_actions.csv and separate user/system actions"""
        actions_file = self.parse_dir / self.csv_files['actions']
        
        with open(actions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Capture ALL fields from the CSV row
                action = row.copy()

                self.all_actions.append(action)
                
                # Separate user-created actions
                if action.get('is_system_generated', '') == 'No':
                    self.user_actions.append(action)
        
        print(f"  ✓ Found {len(self.all_actions)} total actions")
    
    def build_reference_set_from_actions(self):
        """Build set of all actions referenced by other actions"""
        for action in self.all_actions:
            if action.get('referenced_actions', ''):
                # Split comma-separated list and clean up
                refs = [ref.strip() for ref in action.get('referenced_actions', '').split('|||')]
                # Add to set with lowercase for case-insensitive matching
                for ref in refs:
                    if ref:  # Skip empty strings
                        self.referenced_actions.add(ref.lower())
    
    def build_reference_set_from_views(self):
        """Build set of all actions referenced by views"""
        views_file = self.parse_dir / self.csv_files['views']
        
        with open(views_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                referenced_actions = row.get('referenced_actions', '')
                if referenced_actions:
                    # Split comma-separated list and clean up
                    refs = [ref.strip() for ref in referenced_actions.split('|||')]
                    # Add to set with lowercase for case-insensitive matching
                    for ref in refs:
                        if ref:  # Skip empty strings
                            self.referenced_actions.add(ref.lower())

    def build_event_actions_set(self):
        """Build set of all actions referenced in view event_actions"""
        self.event_actions = set()
        views_file = self.parse_dir / self.csv_files['views']
        
        with open(views_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                event_actions = row.get('event_actions', '')
                if event_actions:
                    # Split by ||| and clean up
                    refs = [ref.strip() for ref in event_actions.split('|||') if ref.strip()]
                    for ref in refs:
                        if ref and ref != '**auto**':  # Skip empty and **auto**
                            self.event_actions.add(ref.lower())
    
    def load_view_data(self):
        """Load view data for visibility checking"""
        self.views = []
        views_file = self.parse_dir / self.csv_files['views']
        
        with open(views_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                view = {
                    'view_name': row.get('view_name', ''),
                    'view_type': row.get('view_type', ''),
                    'show_action_bar': row.get('show_action_bar', ''),
                    'action_display_mode': row.get('action_display_mode', ''),
                    'referenced_actions': row.get('referenced_actions', ''),
                    'event_actions': row.get('event_actions', ''),
                    'available_actions': row.get('available_actions', ''),
                    'view_columns': row.get('view_columns', ''),
                    'is_system_view': row.get('is_system_view', ''),
                    'position': row.get('position', ''),
                    'ref_parent': row.get('ref_parent', ''),
                    'show_if': row.get('show_if', '')
                }
                self.views.append(view)
        
        print(f"  ✓ Loaded {len(self.views)} views for visibility checking")
        
    def is_action_visible_in_views(self, action):
        """Check if action is visible in any view based on prominence and view type"""
        action_name = action.get('action_name', '')
        action_name_lower = action_name.lower()
        prominence = action.get('action_prominence', '').replace('_', ' ')
        attach_to_column = action.get('attach_to_column', '')
        source_table = action.get('source_table', '')  # Add this

        # If only_if_condition is explicitly false, action is never visible
        only_if = action.get('only_if_condition', '').strip().lower()
        if only_if == 'false':
            return False
        
        for view in self.views:
            # Skip unused system views
            if view['view_name'].lower() in self.unused_system_views:
                continue
                
            # Check if view is actually shown
            show_if = view.get('show_if', '').strip()
            if show_if.lower() == 'false':
                continue
            
            # Get available actions for this view
            available_actions = [a.strip().lower() for a in view['available_actions'].split('|||') if a.strip()]

            # Action must be in available_actions
            if action_name_lower not in available_actions:
                continue
            
            # NEW: Check if view's data source matches action's source table
            view_source = view.get('source_table', '') or view.get('data_source', '')
            if source_table and view_source and source_table != view_source:
                # Action is for a different table than this view
                continue
            
            view_type = view['view_type'].lower()
            
            # Check visibility based on view type and prominence
            if view_type == 'detail':
                if prominence in ['Display Prominently', 'Display Overlay']:
                    return True
                elif prominence == 'Display Inline' and attach_to_column:
                    # Check if column is visible in view
                    view_columns = [c.strip() for c in view['view_columns'].split('|||') if c.strip()]
                    
                    # NEW: Also verify the column actually exists in the table
                    if attach_to_column in view_columns:
                        # Should also check if column exists in appsheet_columns.csv
                        if self.column_exists(attach_to_column, source_table):
                            return True
                            
            elif view_type == 'table':
                if prominence == 'Display Inline' and attach_to_column:
                    # Check if column is visible in view
                    view_columns = [c.strip() for c in view['view_columns'].split('|||') if c.strip()]
                    if attach_to_column in view_columns:
                        # Should also check if column exists in appsheet_columns.csv
                        if self.column_exists(attach_to_column, source_table):
                            return True
                            
            elif view_type in ['deck', 'gallery']:
                if view.get('show_action_bar', '').lower() == 'true':
                    if prominence != 'Do not display':
                        if view.get('action_display_mode', '') == 'Manual':
                            # For Manual mode, must also be in referenced_actions
                            ref_actions = [a.strip().lower() for a in view['referenced_actions'].split('|||') if a.strip()]
                            if action_name_lower in ref_actions:
                                return True
                        else:  # Automatic mode
                            return True
        
        return False

    def column_exists(self, column_name, table_name):
        """Check if a column exists in the specified table"""
        if not hasattr(self, 'columns_checked'):
            self.columns_checked = {}
            # Load columns data once
            columns_file = self.parse_dir / 'appsheet_columns.csv'
            if columns_file.exists():
                with open(columns_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        key = f"{row.get('table_name', '')}|{row.get('column_name', '')}"
                        self.columns_checked[key] = True
        
        key = f"{table_name}|{column_name}"
        return self.columns_checked.get(key, False)

    def detect_unreachable_actions(self, actions_df):
        """
        Detect actions that are unreachable in grouped action sequences.
        Returns a dict mapping action names to lists of group actions where they're unreachable.
        """
        import json
        unreachable_in_groups = {}
        
        # Create lookup dict for quick access to action data
        action_lookup = {action['action_name']: action for action in self.all_actions}
        
        # Find all grouped actions
        grouped_actions = [a for a in self.all_actions if a.get('action_type_plain_english', '') == 'Execute a group of actions']
        
        for group_action in grouped_actions:
            group_name = group_action['action_name']
            
            # Parse the action sequence from with_these_properties
            try:
                properties = group_action.get('with_these_properties', '')
                if not properties:
                    continue
                    
                # Parse JSON to get action sequence
                props_data = json.loads(properties)
                
                # Look for action sequence (might be under different keys)
                action_sequence = None
                if isinstance(props_data, dict):
                    # Common keys where action sequences are stored
                    for key in ['Actions', 'actions', 'ActionSequence', 'action_sequence']:
                        if key in props_data:
                            action_sequence = props_data[key]
                            break
                
                if not action_sequence or not isinstance(action_sequence, list):
                    continue
                
                # Track if we've hit an unconditional navigation
                navigation_found = False
                navigation_action_name = None
                
                for i, action_ref in enumerate(action_sequence):
                    # Extract action name from reference
                    action_name = None
                    if isinstance(action_ref, str):
                        action_name = action_ref
                    elif isinstance(action_ref, dict):
                        # Try different possible keys
                        for key in ['action', 'ActionName', 'actionName', 'Name']:
                            if key in action_ref:
                                action_name = action_ref[key]
                                break
                    
                    if not action_name:
                        continue
                        
                    # Check if action exists in lookup
                    if action_name not in action_lookup:
                        continue
                    
                    action_data = action_lookup[action_name]
                    
                    # FIRST: Check if this action is unreachable (comes after navigation)
                    if navigation_found:
                        # This action is unreachable!
                        if action_name not in unreachable_in_groups:
                            unreachable_in_groups[action_name] = []
                        unreachable_in_groups[action_name].append(group_name)
                    
                    # THEN: Check if this is an unconditional navigation action
                    if action_data.get('action_type_plain_english') == 'Navigate':
                        condition = action_data.get('only_if_condition', '')
                        
                        # Check if navigation is unconditional or always-true
                        if self._is_unconditional_or_always_true(condition):
                            navigation_found = True
                            navigation_action_name = action_name
                            
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                # Log error but continue processing
                print(f"      Warning: Could not parse action sequence for {group_name}: {e}")
                continue
        
        return unreachable_in_groups

    def _is_unconditional_or_always_true(self, condition):
        """Check if a condition is empty or always evaluates to true."""
        if not condition:
            return True
            
        # Normalize condition string
        condition_str = str(condition).strip()
        
        # Check for simple always-true conditions first
        if condition_str.lower() in ['', 'true', '=true']:
            return True
        
        # Try to evaluate expressions that start with =
        if condition_str.startswith('='):
            try:
                # Remove the leading = for evaluation
                expr = condition_str[1:]
                
                # Replace some AppSheet-specific syntax with Python equivalents
                expr = expr.replace('TRUE', 'True')
                expr = expr.replace('FALSE', 'False')
                expr = expr.replace('true', 'True')
                expr = expr.replace('false', 'False')
                expr = expr.replace('<>', '!=')  # AppSheet not-equal
                
                # Try to evaluate the expression
                result = eval(expr, {"__builtins__": {}}, {})
                
                # If it evaluates to True, it's always true
                if result is True:
                    return True
                    
            except:
                # If evaluation fails, it's not a simple always-true expression
                pass
        
        return False

    def find_orphan_candidates(self):
        """Find user actions that are not referenced and not attached to columns"""
        # First detect unreachable actions
        self.unreachable_in_groups = self.detect_unreachable_actions(self.all_actions)
        
        orphan_candidates = []
        
        for action in self.user_actions:
            action_name = action.get('action_name', '')
            action_name_lower = action_name.lower()

            # Skip actions used by bots
            if action_name_lower in self.bot_actions:
                continue
            
            # Check if referenced (case-insensitive)
            is_referenced = action_name_lower in self.referenced_actions
            
            # If referenced, check if ALL references are from groups where it's unreachable
            has_reachable_reference = True
            if is_referenced and action_name in self.unreachable_in_groups:
                # Find all actions that reference this one
                referencing_actions = []
                for other_action in self.all_actions:
                    refs = [ref.strip() for ref in other_action.get('referenced_actions', '').split('|||') if ref.strip()]
                    if action_name in refs:
                        referencing_actions.append(other_action['action_name'])
                
                # Check if ALL references are from groups where this action is unreachable
                unreachable_groups = self.unreachable_in_groups[action_name]
                if set(referencing_actions).issubset(set(unreachable_groups)):
                    has_reachable_reference = False
                    
            elif not is_referenced:
                has_reachable_reference = False
            
            # Check if in event_actions
            is_event_action = action_name_lower in self.event_actions
            
            # Check if visible in any view
            is_visible_in_views = self.is_action_visible_in_views(action)

            # Include as orphan if not reachable anywhere
            if not has_reachable_reference and not is_event_action and not is_visible_in_views:
                # Create orphan candidate with all original data
                orphan_candidate = action.copy()
                orphan_candidate['is_orphan'] = 'Yes'
                orphan_candidate['reference_count'] = 0
                
                # Check if this is an unreachable action
                if action_name in self.unreachable_in_groups:
                    orphan_candidate['orphan_type'] = 'unreachable'
                    groups = self.unreachable_in_groups.get(action_name, [])
                    orphan_candidate['notes'] = f"UNREACHABLE - Remove from: {', '.join(groups)} before deleting"
                else:
                    orphan_candidate['orphan_type'] = 'standard'
                    orphan_candidate['notes'] = ''
                
                orphan_candidates.append(orphan_candidate)
        
        return orphan_candidates
    
    def write_results_to_csv(self, orphan_candidates):
        """Write orphan candidates to CSV file with all fields"""
        output_file = self.parse_dir / 'potential_action_orphans.csv'
        
        if not orphan_candidates:
            print("    No orphan candidates to write.")
            return None
        
        # Get all field names from the first orphan candidate
        fieldnames = list(orphan_candidates[0].keys())
        
        # Remove our special fields to control their order
        special_fields = ['is_orphan', 'reference_count', 'notes', 'orphan_type']
        for field in special_fields:
            if field in fieldnames:
                fieldnames.remove(field)
        
        # Reorder: action_name, source_table, notes, orphan_type, then rest
        ordered_fields = []
        
        # First two fields
        if 'action_name' in fieldnames:
            ordered_fields.append('action_name')
            fieldnames.remove('action_name')
        if 'source_table' in fieldnames:
            ordered_fields.append('source_table')
            fieldnames.remove('source_table')
            
        # Add notes and orphan_type
        ordered_fields.extend(['notes', 'orphan_type'])
        
        # Add remaining original fields
        ordered_fields.extend(fieldnames)
        
        # Add our tracking fields at the end
        ordered_fields.extend(['is_orphan', 'reference_count'])
        
        fieldnames = ordered_fields
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
            writer.writeheader()
            
            for candidate in orphan_candidates:
                writer.writerow(candidate)
        
        print(f"    ✓ Results written to: potential_action_orphans.csv")
        return output_file
    
    def generate_summary_report(self, orphan_candidates, output_file):
        """Generate a summary report of findings"""
        print(f"\n  📊 Action Orphan Detection Summary:")
        
        # Count actions by status
        system_count = sum(1 for action in self.all_actions if action.get('is_system_generated') == 'Yes')
        user_count = sum(1 for action in self.all_actions if action.get('is_system_generated') == 'No')
        unsure_count = sum(1 for action in self.all_actions if action.get('is_system_generated') == 'Unsure')
        unknown_count = sum(1 for action in self.all_actions if action.get('is_system_generated') == 'Unknown')

        print(f"    Total actions analyzed: {len(self.all_actions)}")
        print(f"    System-generated actions: {system_count} (excluded)")
        if unsure_count > 0:
            print(f"    Actions with status marked 'Unsure': {unsure_count} (excluded)")
        if unknown_count > 0:
            print(f"    Unknown actions: {unknown_count} (excluded)")
        print(f"    User-created actions: {user_count}")
        if self.bot_actions:
            print(f"    Actions used by bots: {len(self.bot_actions)} (excluded from orphan detection)")
        
        print()  # Add this blank line
        
        if len(orphan_candidates) > 0:
            print(f"    ⚠️  Potential orphans found: {len(orphan_candidates)}")
        else:
            print(f"    ✅ No potential orphans detected")
        
        if orphan_candidates:
            # Count by orphan type
            standard_count = sum(1 for o in orphan_candidates if o.get('orphan_type') == 'standard')
            unreachable_count = sum(1 for o in orphan_candidates if o.get('orphan_type') == 'unreachable')
            
            # Only show breakdown if we have both types
            if standard_count > 0 and unreachable_count > 0:
                print(f"\n    Orphan breakdown by type:")
                print(f"      Standard orphans (can be deleted): {standard_count}")
                print(f"      Unreachable in sequence (DO NOT delete directly): {unreachable_count}")
            
            # Group by table, keeping full orphan data
            by_table = defaultdict(list)
            for orphan in orphan_candidates:
                by_table[orphan.get('source_table', 'Unknown')].append(orphan)
            
            print("\n    Table breakdown of potential orphans:")
            for table, orphans in sorted(by_table.items()):
                print(f"     - {table}: {len(orphans)}")
                # Show action names with unreachable warnings
                for i, orphan in enumerate(orphans[:5]):  # Show up to 5
                    action_name = orphan.get('action_name', 'Unknown')
                    if orphan.get('orphan_type') == 'unreachable':
                        print(f"       • {action_name} ⚠️ UNREACHABLE")
                        # Show which groups contain this unreachable action
                        groups = self.unreachable_in_groups.get(action_name, [])
                        if groups:
                            print(f"         Listed but unreachable in:")
                            for group in groups:
                                print(f"           \"{group}\"")
                    else:
                        print(f"       • {action_name}")
                if len(orphans) > 5:
                    print(f"       ... and {len(orphans) - 5} more")
            
            if self.bot_actions:
                print("\n    📋 Bot exclusions: Used bot_actions.txt to exclude bot-referenced actions")
            else:
                print("\n    💡 Note: Actions used exclusively by bots could not be detected.")
                print("       To exclude bot-used actions, create a bot_actions.txt file")
                print("       listing one action name per line in the parse directory.")
            
        # Add warning about unreachable actions if any were found
        if orphan_candidates:
            unreachable_exists = any(o.get('orphan_type') == 'unreachable' for o in orphan_candidates)
            if unreachable_exists:
                print("\n  ⚠️ IMPORTANT: Unreachable actions require special handling!")
                print("    In order to avoid disconcerting error messages, unreachable actions")
                print("    should be removed from group actions that hold them (shown above)")
                print("    before deletion is attempted.")

    def run_analysis(self):
        """Main analysis workflow"""
        print("🔍 Starting Action Orphan Detection...")
        print(f"  📂 Directory: {self.parse_dir}")
        print("\n  ✓ Validating required files...")
        if not self.validate_files():
            return None
        
        # Load unused system views (already done in __init__, but refresh in case file was created)
        print("\n  📊 Loading unused system views...")
        self.load_unused_system_views()
        
        # Load all actions
        print("\n  📊 Extracting actions...")
        self.load_actions()
        
        if not self.user_actions:
            print("\nNo user-created actions found. Nothing to analyze.")
            return []
        
        # Build reference sets
        print("\n  🔍 Searching for potential orphans...")
        self.build_reference_set_from_actions()
        self.build_reference_set_from_views()
        self.build_event_actions_set()
        self.load_view_data()
        
        # Find orphan candidates
        orphan_candidates = self.find_orphan_candidates()
        
        # Write results
        output_file = None
        if orphan_candidates:
            print("\n  💾 Writing results...")
            output_file = self.write_results_to_csv(orphan_candidates)
        
        # Generate summary
        self.generate_summary_report(orphan_candidates, output_file if orphan_candidates else None)
        
        return orphan_candidates

def main():
    if len(sys.argv) != 2:
        print("Usage: python actions_orphan_detector.py '/path/to/parse/directory/'")
        print("\nExample:")
        print("python actions_orphan_detector.py '/Users/kirkmasden/Desktop/20250621_125149_parse/'")
        sys.exit(1)
    
    parse_directory = sys.argv[1]
    
    if not os.path.exists(parse_directory):
        print(f"ERROR: Directory does not exist: {parse_directory}")
        sys.exit(1)
    
    detector = ActionOrphanDetector(parse_directory)
    orphan_candidates = detector.run_analysis()
    
    if orphan_candidates is not None:
        print(f"\nOrphan detection completed successfully!")
        if orphan_candidates:
            action_text = "action" if len(orphan_candidates) == 1 else "actions"
            print(f"Found {len(orphan_candidates)} potential orphan {action_text}.")
        else:
            print("No orphan actions detected.")
    else:
        print("\nOrphan detection failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()