#!/usr/bin/env python3
"""
View Dependency Analyzer for AppSheet Parser Suite

Shows navigation paths TO a selected view and immediate destinations FROM it.
Helps developers understand how users can reach specific views in their apps.

Authors: Kirk Masden & Claude

"""

import csv
import json
import os
import sys
import unicodedata
from collections import defaultdict, deque
from pathlib import Path


class ViewDependencyAnalyzer:
    def __init__(self, base_path=".", return_to_hub=False):
        """Initialize the analyzer with the base path containing CSV files."""
        self.base_path = Path(base_path)
        self.return_to_hub = return_to_hub
        
        # Data storage
        self.views_data = []
        self.view_lookup = {}  # For quick searching
        self.unused_system_views = set()
        
        # Navigation graph
        self.navigation_graph = defaultdict(set)  # view -> set of (target_view, via_info)
        self.reverse_graph = defaultdict(set)  # view -> set of (source_view, via_info)

        # Debug logging (default off)
        self.debug = False

    def dprint(self, *args, **kwargs):
        """Debug print: only emits when self.debug is True."""
        if self.debug:
            print(*args, **kwargs)

    def load_views_data(self):
        """Load the views data from appsheet_views.csv."""
        views_file = self.base_path / "appsheet_views.csv"
        
        if not views_file.exists():
            print(f"Error: Could not find {views_file}")
            print("Please ensure appsheet_views.csv is in the specified directory.")
            return False
            
        try:
            with open(views_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.views_data.append(row)
                    # Create searchable key
                    view_name = row.get('view_name', '')
                    if view_name:
                        self.view_lookup[view_name.lower()] = row

            # Build canonical name map for case-insensitive resolution
            self.view_name_by_lower = {
                (r.get('view_name') or '').strip().lower(): r.get('view_name')
                for r in self.views_data if r.get('view_name')
            }

            print(f"Loaded {len(self.views_data)} views from {views_file.name}")
            return True
            
        except Exception as e:
            print(f"Error reading views file: {e}")
            return False
    
    def load_unused_system_views(self):
        """Load list of unused system views to exclude from analysis."""
        unused_file = self.base_path / "unused_system_views.csv"
        if unused_file.exists():
            try:
                with open(unused_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('is_unused') == 'Yes':
                            self.unused_system_views.add(row.get('view_name'))
                if self.unused_system_views:
                    print(f"  Loaded {len(self.unused_system_views)} unused system views to exclude")
            except Exception as e:
                print(f"  Warning: Could not load unused system views: {e}")

    def resolve_view_name(self, name):
        """Normalize, trim, and case-fold a view name, then return the canonical casing if known."""
        if not name:
            return name
        raw = str(name)
        # Normalize Unicode (e.g., smart quotes), strip surrounding spaces, and case-fold
        norm = unicodedata.normalize('NFC', raw).strip()
        key = norm.lower()
        # Map back to canonical casing if we know it, otherwise return cleaned name
        return (getattr(self, 'view_name_by_lower', {}) or {}).get(key, norm)
    
    def format_via_info(self, edge_row):
        """Format the via_info string from an edge row."""
        availability_type = edge_row.get('action_availability_type', '')
        
        if availability_type == 'dashboard':
            return "Dashboard contains"
        elif availability_type == 'auto':
            event_type = edge_row.get('event_type', '')
            target = edge_row.get('target_view', '')
            return f"Row Selected event → {target} (auto)"
        elif availability_type == 'event':
            action_name = edge_row.get('source_action', '')
            event_type = edge_row.get('event_type', '')
            return f'"{action_name}" (event: {event_type})'
        elif availability_type == 'via_group':
            parent_action = edge_row.get('parent_action', '')
            child_action = edge_row.get('source_action', '')
            parent_prominence = edge_row.get('parent_prominence', '')
            
            via_info = f'"{parent_action}" (grouped action)\n       Contains: "{child_action}"'
            if parent_prominence and parent_prominence != 'Do not display':
                via_info += f'\n       Display: {parent_prominence}'
            return via_info
        else:  # direct action
            action_name = edge_row.get('source_action', '')
            prominence = edge_row.get('parent_prominence', '')
            
            via_info = f'"{action_name}" action'
            if prominence and prominence != 'Do not display':
                via_info += f'\n       Display: {prominence}'
            return via_info
    
    def build_navigation_graph(self):
        """Build the navigation graph from pre-parsed navigation_edges.csv."""
        print("\n  Building navigation graph from navigation_edges.csv...")
        
        edges_file = self.base_path / "navigation_edges.csv"
        
        if not edges_file.exists():
            print(f"Error: Could not find {edges_file}")
            print("Please ensure navigation_edges.csv is in the specified directory.")
            return False
        
        try:
            edge_count = 0
            with open(edges_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source_view = row.get('source_view', '')
                    target_view = row.get('target_view', '')
                    
                    if not source_view or not target_view:
                        continue
                    
                    # Skip if source view is in unused system views
                    if source_view in self.unused_system_views:
                        continue
                    
                    # Resolve view names to canonical casing
                    source_view = self.resolve_view_name(source_view)
                    target_view = self.resolve_view_name(target_view)
                    
                    # Build the via_info string
                    via_info = self.format_via_info(row)
                    
                    # Add to both graphs
                    self.navigation_graph[source_view].add((target_view, via_info))
                    self.reverse_graph[target_view].add((source_view, via_info))
                    edge_count += 1
            
            print(f"  Loaded {edge_count} navigation edges")
            return True
            
        except Exception as e:
            print(f"Error reading navigation edges file: {e}")
            return False
    
    def identify_entry_points(self):
        """Identify all root views (Primary, Menu, Reference views reached by actions)."""
        entry_points = {
            'primary': [],
            'menu': [],
            'reference': []
        }
        
        # Primary and Menu views
        for view in self.views_data:
            if view['view_name'] in self.unused_system_views:
                continue
                
            category = view.get('category', '').lower()
            position = view.get('position', '').lower()
            show_if = view.get('show_if', '')
            
            # Skip if always false
            if self.is_always_false(show_if):
                continue
            
            if category == 'primary' and position in ['first', 'next', 'middle', 'later', 'last']:
                entry_points['primary'].append(view)
            elif category == 'menu':
                entry_points['menu'].append(view)
        
        # Reference views (views that can be reached but aren't primary/menu)
        # We can determine these from the navigation graph
        all_reachable = set()
        for source, targets in self.navigation_graph.items():
            for target, _ in targets:
                all_reachable.add(target)
        
        for view_name in all_reachable:
            view = self.view_lookup.get(view_name.lower())
            if view:
                category = view.get('category', '').lower()
                if category not in ['primary', 'menu']:
                    entry_points['reference'].append(view)
        
        return entry_points
    
    def is_always_false(self, condition):
        """Check if a condition is always false."""
        if not condition:
            return False
        
        condition_lower = condition.strip().lower()
        return condition_lower in ['false', 'false()', '=false', '=false()']
    
    def find_paths_to_view(self, target_view_name, max_paths=5):
        """Find up to max_paths direct paths from entry points to the target view."""
        paths = []
        entry_points = self.identify_entry_points()
        
        # BFS from each entry point category (PRIMARY AND MENU ONLY)
        for category in ('primary', 'menu'):
            views = entry_points.get(category, [])
            for entry_view in views:
                if len(paths) >= max_paths:
                    break
                    
                entry_name = entry_view['view_name']
                
                # Handle case where entry point IS the target
                if entry_name == target_view_name:
                    if category == 'primary':
                        position = entry_view.get('position', '')
                        paths.append([f"Primary Navigation (position: {position})\n    [{target_view_name} is the target view itself]"])
                    elif category == 'menu':
                        paths.append([f"Menu Navigation\n    [{target_view_name} is the target view itself]"])
                    continue
                
                # Find paths from this entry point
                found_paths = self.bfs_find_paths(entry_name, target_view_name, category, entry_view)
                
                for path in found_paths:
                    if len(paths) >= max_paths:
                        break
                    paths.append(path)
        
        return paths[:max_paths]
    
    def bfs_find_paths(self, start_view, target_view, entry_category, entry_view_data):
        """Use BFS to find direct paths from start to target."""
        if start_view == target_view:
            # Special case: entry point IS the target
            full_path = []
            if entry_category == 'primary':
                position = entry_view_data.get('position', '')
                full_path.append(f"Primary Navigation (position: {position})")
            elif entry_category == 'menu':
                full_path.append(f"Menu Navigation")
            elif entry_category == 'reference':
                full_path.append(f"Reference View: {entry_view_data['view_name']}")
            full_path.append(f"[{target_view} is the target view itself]")
            return [full_path]
        
        paths = []
        queue = deque([(start_view, [], 0)])
        visited = set()  # Simple visited set - once we've explored a view, don't do it again
        
        max_depth = 5  # Reduced max depth
        target_found = False
        
        while queue and not target_found:
            current_view, path, depth = queue.popleft()
            
            # Skip if already visited
            if current_view in visited:
                continue
            visited.add(current_view)
            
            # Check for cycles in current path
            path_views = [v for v, _ in path]
            if current_view in path_views:
                continue
            
            # Don't go too deep
            if depth > max_depth:
                continue
            
            # Check neighbors
            for next_view, via_info in self.navigation_graph.get(current_view, set()):
                if next_view == target_view:
                    # Found it! Build the path and stop
                    full_path = []
                    
                    # Add entry point
                    if entry_category == 'primary':
                        position = entry_view_data.get('position', '')
                        full_path.append(f"Primary Navigation (position: {position})")
                    elif entry_category == 'menu':
                        full_path.append(f"Menu Navigation")
                    elif entry_category == 'reference':
                        full_path.append(f"Reference View: {entry_view_data['view_name']}")
                    
                    # Add path steps
                    full_path.extend(path)
                    
                    # Add final step
                    if path:
                        full_path.append((current_view, via_info))
                    else:
                        full_path.append((start_view, via_info))
                    full_path.append(target_view)
                    
                    paths.append(full_path)
                    target_found = True  # Stop searching after finding first path
                    break
                
                elif next_view not in visited and next_view not in path_views:
                    # Continue exploring
                    new_path = path + [(current_view, via_info)]
                    queue.append((next_view, new_path, depth + 1))
        
        return paths
    
    def find_destinations_from_view(self, view_name):
        """Find immediate destinations (depth-1) from the given view."""
        destinations = []
        
        for target_view, via_info in self.navigation_graph.get(view_name, set()):
            # Get target view details
            target_data = self.view_lookup.get(target_view.lower(), {})
            destinations.append({
                'target_view': target_view,
                'via_info': via_info,
                'view_type': target_data.get('view_type', 'unknown'),
                'source_table': target_data.get('source_table', target_data.get('data_source', 'unknown'))
            })
        
        return destinations
    
    def search_views(self, search_term):
        """Search for views matching the search term."""
        search_term = search_term.lower().strip()
        matches = []
        excluded = []
        
        for view in self.views_data:
            view_name = view['view_name']
            
            # Check various matching patterns
            if (view_name.lower().startswith(search_term) or
                search_term in view_name.lower()):
                
                # Check if it's an unused system view
                if view_name in self.unused_system_views:
                    excluded.append(view_name)
                else:
                    matches.append(view)
        
        return matches, excluded
    
    def display_matches(self, matches, excluded):
        """Display matching views in a numbered list."""
        if not matches and not excluded:
            print("\nNo views found matching your search term.")
            return None
        
        if matches:
            count = len(matches)
            print(f"\nFound {count} matching {'view' if count == 1 else 'views'}:")
            print("-" * 70)
            
            for i, view in enumerate(matches, 1):
                view_name = view['view_name']
                view_type = view.get('view_type', 'unknown')
                category = view.get('category', '')
                source_table = view.get('source_table') or view.get('data_source', 'unknown')
                is_system = " [SYSTEM]" if view.get('is_system_view') == 'Yes' else ""
                
                print(f"{i:3}. {view_name}{is_system}")
                print(f"     Type: {view_type} | Table: {source_table} | Category: {category}")
            
            print("-" * 70)
        else:
            print("\nNo accessible views found matching your search term.")
            print("-" * 70)
        
        # Show excluded views if any
        if excluded:
            print("Note: The following views have been excluded because they have been")
            print("classified as 'unused system views':")
            for view_name in excluded:
                print(f"   {view_name}")
            print("-" * 70)
        
        return matches
    
    def get_user_selection(self, matches):
        """Get user's selection from the list of matches."""
        while True:
            try:
                selection = input("\nEnter the number of the view to analyze (or 'q' to quit): ").strip()
                
                if selection.lower() == 'q':
                    return None
                
                index = int(selection) - 1
                if 0 <= index < len(matches):
                    return matches[index]
                else:
                    print(f"Please enter a number between 1 and {len(matches)}")
                    
            except ValueError:
                print("Please enter a valid number or 'q' to quit")
    
    def display_view_analysis(self, view):
        """Display comprehensive path analysis for the selected view."""
        view_name = view['view_name']
        view_type = view.get('view_type', 'unknown')
        source_table = view.get('source_table') or view.get('data_source', 'unknown')
        category = view.get('category', '')
        position = view.get('position', '')
        
        print("\n" + "="*70)
        print(f"VIEW DEPENDENCY ANALYSIS FOR {view_name}")
        print("="*70)
        
        print(f"\nView: {view_name}")
        print(f"Type: {view_type}")
        print(f"Table/Slice: {source_table}")
        print(f"Category: {category}")
        if position:
            print(f"Position: {position}")
        
        # Find and display paths TO this view
        print("\n" + "="*70)
        print(f"NAVIGATION PATHS TO {view_name}")
        print("="*70)
        
        paths = self.find_paths_to_view(view_name, max_paths=5)

        # DEBUG: show raw path elements as produced by BFS
        if self.debug:
            for idx, p in enumerate(paths, 1):
                print(f"\n[DEBUG] RAW PATH {idx}:")
                for elem in p:
                    print("   ", repr(elem))
        
        if not paths:
            print(f"\n{view_name} [NO PATHS FOUND]")
            print("    This view appears to be unreachable")
        else:
            for i, path in enumerate(paths, 1):
                print(f"\nPATH {i}:")
                
                for j, step in enumerate(path):
                    if isinstance(step, tuple):
                        # This is a (view_name, via_info) tuple
                        current_view, via_info = step
                        print(current_view)
                        print(f"    └─ via {via_info}")
                        print("       ↓")
                    else:
                        # This is just a string (entry point or final view)
                        print(step)
        
        # Find and display immediate destinations FROM this view
        print("\n" + "="*70)
        print(f"NAVIGATION FROM {view_name}")
        print("="*70)
        
        destinations = self.find_destinations_from_view(view_name)
        
        if not destinations:
            print(f"\n{view_name} has no navigation to other views")
        else:
            # Group destinations by via_info to handle actions with multiple targets
            grouped_destinations = {}
            for dest in destinations:
                via = dest['via_info']
                if via not in grouped_destinations:
                    grouped_destinations[via] = []
                grouped_destinations[via].append(dest)
            
            print(f"\n{view_name} [THIS VIEW] navigates to:\n")
            
            for via_info, dests in grouped_destinations.items():
                if len(dests) > 3:  # Many destinations through same action
                    print(f"    └─ via {via_info}")
                    print(f"       Routes to {len(dests)} different views:")
                    # Show first 3 as examples
                    for i, dest in enumerate(dests[:3]):
                        print(f"       → {dest['target_view']} ({dest['view_type']})")
                    print(f"       → ... and {len(dests) - 3} more views")
                    print()
                else:  # Few destinations - show all
                    for dest in dests:
                        print(f"    └─ via {via_info}")
                        print("       ↓")
                        print(f"    {dest['target_view']}")
                        print(f"    View type: {dest['view_type']}")
                        print(f"    Table: {dest['source_table']}")
                        print()
    
    def run(self, return_to_hub=False):
        """Main execution loop."""
        if return_to_hub:
            self.return_to_hub = return_to_hub
        
        print("AppSheet View Dependency Analyzer")
        print("=================================")
        
        # Load views data (required)
        if not self.load_views_data():
            return
        
        # Load unused system views
        print("\nLoading additional data:")
        self.load_unused_system_views()
        
        # Build navigation graph from edges CSV
        if not self.build_navigation_graph():
            return
        
        # Main interaction loop
        while True:
            print("\n" + "="*70)
            search_term = input("Enter view name or partial name to search (or 'quit' to exit): ").strip()
            
            if search_term.lower() in ['quit', 'exit', 'q']:
                if self.return_to_hub:
                    print("\nReturning to dependency analysis menu...")
                else:
                    print("\nGoodbye!")
                break
            
            if not search_term:
                print("Please enter a search term.")
                continue
            
            # Search for matches
            matches, excluded = self.search_views(search_term)
            
            # Display matches
            displayed_matches = self.display_matches(matches, excluded)
            
            if displayed_matches:
                # Get user selection
                selected = self.get_user_selection(displayed_matches)
                
                if selected:
                    # Analyze dependencies
                    self.display_view_analysis(selected)
                    
                    input("\nPress Enter to continue...")


def main():
    """Main entry point."""
    # Check if a path was provided
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Create and run analyzer
    analyzer = ViewDependencyAnalyzer(base_path)
    analyzer.run()


if __name__ == "__main__":
    main()