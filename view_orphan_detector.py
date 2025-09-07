#!/usr/bin/env python3
"""
AppSheet View Orphan Detector

Identifies user-created views that are not referenced anywhere in the application
and are not accessible through primary navigation, menus, or other views.

Usage:
    python view_orphan_detector.py "/path/to/parse/directory/"
"""

import csv
import sys
import os
import re
import json
import unicodedata
from pathlib import Path
from collections import defaultdict, deque

class ViewOrphanDetector:
    def __init__(self, parse_directory):
        self.parse_dir = Path(parse_directory)
        self.all_views = []
        self.user_views = []
        self.system_views = [] 
        self.unused_system_views = set()
        
        # For column validation
        self.columns_by_table = defaultdict(set)
        
        # For view name normalization
        self.view_name_by_lower = {}
        
        # Debug mode (set to True for troubleshooting)
        self.debug = False

    def dprint(self, *args, **kwargs):
        """Debug print: only emits when self.debug is True."""
        if self.debug:
            print(*args, **kwargs)

    def validate_files(self):
        """Check that all required CSV files exist"""
        missing_files = []
        
        # Add navigation_edges.csv to required files
        required_files = {
            'views': 'appsheet_views.csv',
            'actions': 'appsheet_actions.csv',
            'edges': 'navigation_edges.csv'
        }
        
        for file_type, filename in required_files.items():
            file_path = self.parse_dir / filename
            if not file_path.exists():
                missing_files.append(filename)
        
        # Check optional columns file
        columns_file = self.parse_dir / 'appsheet_columns.csv'
        if not columns_file.exists():
            print(f"  Note: No columns file found (appsheet_columns.csv) - this is optional")
        
        if missing_files:
            print(f"ERROR: Missing required files: {', '.join(missing_files)}")
            print(f"Expected location: {self.parse_dir}")
            return False
        return True
    
    def load_columns_data(self):
        """Load column data for validation of inline actions."""
        columns_file = self.parse_dir / 'appsheet_columns.csv'
        
        if not columns_file.exists():
            print(f"  Note: No columns file found (appsheet_columns.csv) - column validation will be limited")
            return False
            
        try:
            with open(columns_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    table_name = row.get('table_name', '')
                    column_name = row.get('column_name', '')
                    if table_name and column_name:
                        self.columns_by_table[table_name].add(column_name)
                    
            print(f"  Loaded column data for {len(self.columns_by_table)} tables")
            return True
            
        except Exception as e:
            print(f"  Warning: Could not load columns file: {e}")
            return False
    
    def is_always_false_condition(self, condition):
        """Check if a show_if condition always evaluates to false"""
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

    def resolve_view_name(self, name):
        """Normalize, trim, and case-fold a view name, then return the canonical casing if known."""
        if not name:
            return name
        raw = str(name)
        # Normalize Unicode (e.g., smart quotes), strip surrounding spaces, and case-fold
        norm = unicodedata.normalize('NFC', raw).strip()
        key = norm.lower()
        # Map back to canonical casing if we know it, otherwise return cleaned name
        return self.view_name_by_lower.get(key, norm)

    def build_navigation_graph_from_edges(self):
        """
        Build navigation graph from pre-parsed navigation_edges.csv.
        Returns dict of source -> set of targets for efficient traversal.
        """
        navigation_graph = defaultdict(set)
        edges_file = self.parse_dir / 'navigation_edges.csv'
        
        if not edges_file.exists():
            raise FileNotFoundError(f"Required file not found: navigation_edges.csv")
        
        print(f"  Loading navigation edges from navigation_edges.csv...")
        edge_count = 0
        
        try:
            with open(edges_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = row.get('source_view', '').strip()
                    target = row.get('target_view', '').strip()
                    
                    if source and target:
                        # Use the normalized versions for consistent matching
                        source_normalized = row.get('source_view_normalized', source).strip()
                        target_normalized = row.get('target_view_normalized', target).strip()
                        
                        # Store using canonical names from view_name_by_lower if available
                        source_canonical = self.view_name_by_lower.get(source_normalized.lower(), source)
                        target_canonical = self.view_name_by_lower.get(target_normalized.lower(), target)
                        
                        navigation_graph[source_canonical].add(target_canonical)
                        edge_count += 1
                        
                        if self.debug:
                            action = row.get('source_action', '')
                            availability = row.get('action_availability_type', '')
                            self.dprint(f"    Edge: {source} -> {target} via {action or availability}")
            
            print(f"    ✓ Loaded {edge_count} navigation edges")
            print(f"    ✓ Graph contains {len(navigation_graph)} source views")
            
        except Exception as e:
            print(f"ERROR: Failed to load navigation_edges.csv: {e}")
            raise
            
        return navigation_graph
    
    def load_views(self):
        """Load all views from appsheet_views.csv and separate user/system views"""
        views_file = self.parse_dir / 'appsheet_views.csv'
        
        with open(views_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                view = row.copy()
                self.all_views.append(view)
                
                # Separate user-created and system views
                flag = str(view.get('is_system_view', '')).strip().lower()
                if flag == 'yes':
                    self.system_views.append(view)
                else:
                    self.user_views.append(view)
        
        # Build canonical name map for case-insensitive resolution
        self.view_name_by_lower = {
            (r.get('view_name') or '').strip().lower(): r.get('view_name')
            for r in self.all_views if r.get('view_name')
        }
        
        print(f"  ✔ Found {len(self.all_views)} total views")
        print(f"    System-generated: {len(self.system_views)}")
        print(f"    User-created: {len(self.user_views)}")

    def find_all_reachable_views(self):
        """
        Find all views reachable from root views using BFS with pre-computed navigation edges.
        """
        # Build the navigation graph from edges
        navigation_graph = self.build_navigation_graph_from_edges()
        
        # Create view lookup for quick access
        view_lookup = {}
        for v in self.all_views:
            view_name = v.get('view_name', '')
            if view_name:
                view_lookup[view_name] = v
        
        # Identify root views (entry points)
        root_views = set()
        
        for view in self.all_views:
            view_name = view['view_name']
            category = view.get('category', '').lower()
            show_if = view.get('show_if', '')
            
            # Skip if show_if is always false
            if self.is_always_false_condition(show_if):
                continue
            
            if category == 'primary':
                position = view.get('position', '').lower()
                if position in ['first', 'next', 'middle', 'later', 'last']:
                    root_views.add(view_name)
            elif category == 'menu':
                root_views.add(view_name)
        
        print(f"    ✓ Identified {len(root_views)} root views (primary + menu)")
        
        # BFS to find all reachable views
        reachable = set()
        queue = deque(root_views)
        
        # Track how each view was reached for debugging
        self.reach_paths = {}
        for root in root_views:
            self.reach_paths[root] = (None, "ROOT")
        
        while queue:
            current_view_name = queue.popleft()
            
            if current_view_name in reachable:
                continue
            
            reachable.add(current_view_name)
            
            # Add all views this view can navigate to
            if current_view_name in navigation_graph:
                for target_view in navigation_graph[current_view_name]:
                    if target_view not in reachable:
                        queue.append(target_view)
                        if target_view not in self.reach_paths:
                            self.reach_paths[target_view] = (current_view_name, "navigation edge")
        
        print(f"    ✓ Found {len(reachable)} reachable views from {len(root_views)} roots")
        
        # Debug output for problem views if debug mode is on
        if self.debug:
            for problem_view in ["Finished", "Archive menu J"]:
                if problem_view in self.reach_paths:
                    print(f"\n    DEBUG: How '{problem_view}' was reached:")
                    self.print_reach_path(problem_view)
                elif problem_view in [v['view_name'] for v in self.all_views]:
                    print(f"\n    DEBUG: '{problem_view}' is NOT reachable")
        
        return reachable
    
    def print_reach_path(self, view_name, indent=0):
        """Recursively print how a view was reached (for debugging)."""
        if view_name not in self.reach_paths:
            print(" " * indent + f"  {view_name} (not in reach_paths)")
            return
        
        from_view, via = self.reach_paths[view_name]
        if from_view is None:
            print(" " * indent + f"  {view_name} <- {via}")
        else:
            print(" " * indent + f"  {view_name} <- {via}")
            print(" " * indent + f"  from:")
            self.print_reach_path(from_view, indent + 4)

    def find_orphan_candidates(self):
        """Find user views that are potential orphans using comprehensive path analysis."""
        orphan_candidates = []
        
        # Get all reachable views using path analysis
        reachable_views = self.find_all_reachable_views()
        
        for view in self.user_views:
            view_name = view['view_name']
            show_if = view.get('show_if', '')
            
            # Check if show_if is always false
            if self.is_always_false_condition(show_if):
                orphan_candidate = view.copy()
                orphan_candidate['is_orphan'] = 'Yes'
                orphan_candidate['orphan_reason'] = 'Always false show_if condition'
                orphan_candidates.append(orphan_candidate)
                continue
            
            # Check if view is reachable
            if view_name not in reachable_views:
                orphan_candidate = view.copy()
                orphan_candidate['is_orphan'] = 'Yes'
                
                # Determine specific reason
                if view['view_type'] == 'detail':
                    orphan_candidate['orphan_reason'] = 'Detail view not reachable from any root view'
                elif view.get('category', '').lower() == 'ref':
                    orphan_candidate['orphan_reason'] = 'Ref view not reachable from any root view'
                else:
                    orphan_candidate['orphan_reason'] = 'View not reachable from any root view'
                
                orphan_candidates.append(orphan_candidate)
        
        return orphan_candidates
        
    def find_unused_system_views(self):
        """Find system views that are not reachable using comprehensive path analysis."""
        unused_system_views = []
        
        # Get all reachable views using path analysis
        reachable_views = self.find_all_reachable_views()
        
        for view in self.system_views:
            view_name = view['view_name']
            show_if = view.get('show_if', '')
            
            # Check if show_if is always false
            if self.is_always_false_condition(show_if):
                unused_view = view.copy()
                unused_view['is_unused'] = 'Yes'
                unused_view['unused_reason'] = 'Always false show_if condition'
                unused_system_views.append(unused_view)
                continue
            
            # Check if view is reachable
            if view_name not in reachable_views:
                unused_view = view.copy()
                unused_view['is_unused'] = 'Yes'
                
                # Determine specific reason
                if view['view_type'] == 'detail':
                    unused_view['unused_reason'] = 'System detail view not reachable from any root view'
                elif view.get('category', '').lower() == 'ref':
                    unused_view['unused_reason'] = 'System ref view not reachable from any root view'
                else:
                    unused_view['unused_reason'] = 'System view not reachable from any root view'
                
                unused_system_views.append(unused_view)
        
        return unused_system_views
    
    def write_results_to_csv(self, orphan_candidates, unused_system_views):
        """Write results to two separate CSV files"""
        # Write user orphan views
        if orphan_candidates:
            output_file = self.parse_dir / 'potential_view_orphans.csv'
            
            # Get all field names from the first orphan candidate
            fieldnames = list(orphan_candidates[0].keys())
            
            # Ensure our added fields are at the end
            for field in ['is_orphan', 'orphan_reason']:
                if field in fieldnames:
                    fieldnames.remove(field)
            fieldnames.extend(['is_orphan', 'orphan_reason'])
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                
                for candidate in orphan_candidates:
                    writer.writerow(candidate)
            
            print(f"    ✔ Potential user orphan views written to: potential_view_orphans.csv")
        
        # Write unused system views
        if unused_system_views:
            output_file = self.parse_dir / 'unused_system_views.csv'
            
            # Get all field names from the first unused system view
            fieldnames = list(unused_system_views[0].keys())
            
            # Ensure our added fields are at the end
            for field in ['is_unused', 'unused_reason']:
                if field in fieldnames:
                    fieldnames.remove(field)
            fieldnames.extend(['is_unused', 'unused_reason'])
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_ALL)
                writer.writeheader()
                
                for view in unused_system_views:
                    writer.writerow(view)
            
            print(f"    ✔ Unused system views written to: unused_system_views.csv")
    
    def generate_summary_report(self, orphan_candidates, unused_system_views):
        """Generate a summary report of findings"""
        print(f"\n  📊 View Orphan Detection Summary:")
        
        print(f"    Total views analyzed: {len(self.all_views)}")
        system_text = "view" if len(self.system_views) == 1 else "views"
        print(f"    System-generated {system_text}: {len(self.system_views)}")
        user_text = "view" if len(self.user_views) == 1 else "views"
        print(f"    User-created {user_text}: {len(self.user_views)}")
        
        # User orphan views summary
        if orphan_candidates:
            orphan_text = "orphan" if len(orphan_candidates) == 1 else "orphans"
            print(f"\n    ⚠️  Potential user view {orphan_text} found: {len(orphan_candidates)}")
            
            # Group by reason
            by_reason = defaultdict(list)
            for orphan in orphan_candidates:
                reason = orphan.get('orphan_reason', 'Unknown')
                by_reason[reason].append(orphan)
            
            print("      Reason Breakdown:")
            for reason, views in sorted(by_reason.items()):
                view_text = "view" if len(views) == 1 else "views"
                print(f"        - {reason}: {len(views)} {view_text}")
        else:
            print(f"\n    ✅ No potential user view orphans found")
        
        # Unused system views summary
        if unused_system_views:
            unused_text = "view" if len(unused_system_views) == 1 else "views"
            print(f"\n    ℹ️  Unused system {unused_text} found: {len(unused_system_views)}")
            
            # Group by reason
            by_reason = defaultdict(list)
            for view in unused_system_views:
                reason = view.get('unused_reason', 'Unknown')
                by_reason[reason].append(view)
            
            print("      Reason Breakdown:")
            for reason, views in sorted(by_reason.items()):
                view_text = "view" if len(views) == 1 else "views"
                print(f"        - {reason}: {len(views)} {view_text}")
            
            print("\n      Note: System views cannot be deleted but are tracked")
            print("      for accurate orphan detection in actions and columns.")
        else:
            print(f"\n    ✅ All system views are accessible")

    def run_analysis(self):
        """Main analysis workflow"""
        print("🔍 Starting View Orphan Detection...")
        print(f"  📂 Directory: {self.parse_dir}")
        print("\n  ✔ Validating required files...")
        if not self.validate_files():
            return None, None
        
        # Load all views
        print("\n  📊 Extracting views...")
        self.load_views()
        
        # Load column data for validation (optional but helpful)
        print("\n  📊 Loading additional data:")
        self.load_columns_data()
        
        # Find user orphan candidates using path analysis
        print("\n  🔍 Searching for potential user view orphans...")
        orphan_candidates = self.find_orphan_candidates()

        # Find unused system views using path analysis
        print("  🔍 Searching for unused system views...")
        unused_system_views = self.find_unused_system_views()
        
        # Write results
        print("\n  💾 Writing results...")
        self.write_results_to_csv(orphan_candidates, unused_system_views)
        
        # Generate summary
        self.generate_summary_report(orphan_candidates, unused_system_views)
        
        return orphan_candidates, unused_system_views

def main():
    if len(sys.argv) != 2:
        print("Usage: python view_orphan_detector.py '/path/to/parse/directory/'")
        print("\nExample:")
        print("python view_orphan_detector.py '/Users/kirkmasden/Desktop/20250621_125149_parse/'")
        sys.exit(1)
    
    parse_directory = sys.argv[1]
    
    if not os.path.exists(parse_directory):
        print(f"ERROR: Directory does not exist: {parse_directory}")
        sys.exit(1)
    
    detector = ViewOrphanDetector(parse_directory)
    orphan_candidates, unused_system_views = detector.run_analysis()
    
    if orphan_candidates is not None or unused_system_views is not None:
        print(f"\n✅ View analysis completed successfully!")
        
        # Summary counts
        orphan_count = len(orphan_candidates) if orphan_candidates else 0
        unused_count = len(unused_system_views) if unused_system_views else 0
        
        if orphan_count > 0:
            orphan_text = "orphan view" if orphan_count == 1 else "orphan views"
            print(f"  Found {orphan_count} potential user {orphan_text}")
        
        if unused_count > 0:
            unused_text = "unused system view" if unused_count == 1 else "unused system views"
            print(f"  Found {unused_count} {unused_text}")
            
        if orphan_count == 0 and unused_count == 0:
            print("  No orphan or unused views detected.")
    else:
        print("\n❌ View analysis failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

