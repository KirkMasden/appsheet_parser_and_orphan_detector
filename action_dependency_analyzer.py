#!/usr/bin/env python3
"""
Action Dependency Analyzer for AppSheet Parser Suite

Authors: Kirk Masden & Claude 4.1

"""

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


class ActionDependencyAnalyzer:
    def __init__(self, base_path=".", return_to_hub=False):
        """Initialize the analyzer with the base path containing CSV files."""
        self.base_path = Path(base_path)
        self.return_to_hub = return_to_hub
        self.actions_data = []
        self.action_lookup = {}  # For quick searching
        self.columns_data = []
        self.views_data = []
        self.slices_data = []
        self.format_rules_data = []
        self.unused_system_views = set()
        
    def load_actions_data(self):
        """Load the actions data from appsheet_actions.csv."""
        actions_file = self.base_path / "appsheet_actions.csv"
        
        if not actions_file.exists():
            print(f"Error: Could not find {actions_file}")
            print("Please ensure appsheet_actions.csv is in the specified directory.")
            return False
            
        try:
            with open(actions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.actions_data.append(row)
                    # Create searchable key
                    action_name = row.get('action_name', '')
                    if action_name:
                        self.action_lookup[action_name.lower()] = row
                    
            print(f"Loaded {len(self.actions_data)} actions from {actions_file.name}")
            return True
            
        except Exception as e:
            print(f"Error reading actions file: {e}")
            return False

    def _load_data(self, filename, data_attribute, name_plural):
        """Helper to load data from an optional CSV file."""
        file_path = self.base_path / filename
        if not file_path.exists():
            print(f"  Note: No {name_plural} file found ({filename})")
            return False
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                data = list(reader)
                setattr(self, data_attribute, data)
            print(f"  Loaded {len(data)} {name_plural}")
            return True
        except Exception as e:
            print(f"  Error reading {name_plural} file: {e}")
            return False
    
    def load_columns_data(self):
        """Load the columns data from appsheet_columns.csv."""
        return self._load_data("appsheet_columns.csv", "columns_data", "columns")
    
    def load_views_data(self):
        """Load the views data from appsheet_views.csv."""
        return self._load_data("appsheet_views.csv", "views_data", "views")
    
    def load_slices_data(self):
        """Load the slices data from appsheet_slices.csv."""
        return self._load_data("appsheet_slices.csv", "slices_data", "slices")
    
    def load_format_rules_data(self):
        """Load the format rules data from appsheet_format_rules.csv."""
        return self._load_data("appsheet_format_rules.csv", "format_rules_data", "format rules")
    
    def get_action_type_display(self, action):
        """Get the best available action type description."""
        # Prefer plain English, fall back to technical, then to generic type
        return (action.get('action_type_plain_english') or 
                action.get('action_type_technical_name') or 
                action.get('action_type') or 
                'Unknown type')
    
    def get_action_description(self, action):
        """Build a description string for an action."""
        action_name = action.get('action_name', 'Unnamed')
        source_table = action.get('source_table', 'Unknown table')
        action_type = self.get_action_type_display(action)
        is_system = action.get('is_system_generated') == 'Yes'
        
        desc = f"{action_name} ({source_table})"
        if is_system:
            desc += " [SYSTEM]"
        desc += f" - {action_type}"
        
        return desc
    
    def search_by_name(self):
        """Search for actions by name with partial matching."""
        while True:
            print("\n" + "="*70)
            search_term = input("Enter action name to search (or 'back' to return): ").strip()
            
            if search_term.lower() in ['back', 'b']:
                return None
                
            if not search_term:
                print("Please enter a search term.")
                continue
                
            # Find matches
            matches = self.find_action_matches(search_term)
            
            if not matches:
                print(f"\nNo actions found matching '{search_term}'")
                continue
                
            # Display matches
            selected = self.display_and_select_action(matches, f"Actions matching '{search_term}'")
            if selected:
                return selected
    
    def find_action_matches(self, search_term):
        """Find actions matching the search term."""
        search_term = search_term.lower().strip()
        matches = []
        
        for action in self.actions_data:
            action_name = action.get('action_name', '')
            
            # Check various matching patterns
            if (action_name.lower().startswith(search_term) or
                search_term in action_name.lower()):
                matches.append(action)
                
        return matches
    
    def browse_by_table(self):
        """Browse actions organized by table."""
        # Group actions by table
        by_table = defaultdict(list)
        for action in self.actions_data:
            table = action.get('source_table', 'Unknown')
            by_table[table].append(action)
        
        if not by_table:
            print("\nNo actions found.")
            return None
        
        while True:
            # Display tables
            print("\n" + "="*70)
            print("SELECT TABLE:")
            print("-" * 40)
            
            tables = sorted(by_table.keys())
            for i, table in enumerate(tables, 1):
                count = len(by_table[table])
                plural = "action" if count == 1 else "actions"
                print(f"{i:3}. {table} ({count} {plural})")
        
            print(f"{len(tables)+1:3}. Go back")
            
            # Get selection
            try:
                choice = input(f"\nSelect table (1-{len(tables)}) or {len(tables)+1} to go back: ").strip()
                
                if choice == str(len(tables)+1):
                    return None
                    
                idx = int(choice) - 1
                if 0 <= idx < len(tables):
                    selected_table = tables[idx]
                    selected = self.browse_table_actions(selected_table, by_table[selected_table])
                    if selected:
                        return selected
                else:
                    print("Invalid selection. Please try again.")
                    
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                return None
    
    def browse_table_actions(self, table_name, actions):
        """Browse actions for a specific table with type filtering."""
        while True:
            # Group by action type
            by_type = defaultdict(list)
            for action in actions:
                action_type = self.get_action_type_display(action)
                by_type[action_type].append(action)
            
            # Display type summary
            print("\n" + "="*70)
            print(f"{table_name.upper()} TABLE - ACTION TYPES:")
            print(f"Found {len(actions)} {'action' if len(actions) == 1 else 'actions'} with {len(by_type)} different {'type' if len(by_type) == 1 else 'types'}:")
            print("-" * 40)
            
            # Sort types by count (descending) then name
            type_counts = [(type_name, len(actions_list)) 
                          for type_name, actions_list in by_type.items()]
            type_counts.sort(key=lambda x: (-x[1], x[0]))
            
            for type_name, count in type_counts:
                plural = "action" if count == 1 else "actions"
                print(f"  {type_name} ({count} {plural})")
            
            # Display menu
            print("\nSELECT ACTION TYPE:")
            print("-" * 40)
            
            menu_options = []
            for i, (type_name, count) in enumerate(type_counts, 1):
                plural = "action" if count == 1 else "actions"
                print(f"{i:3}. {type_name} ({count} {plural})")
                menu_options.append((type_name, by_type[type_name]))
            
            show_all_num = len(menu_options) + 1
            go_back_num = show_all_num + 1
            
            print(f"{show_all_num:3}. Show all {len(actions)} {'action' if len(actions) == 1 else 'actions'}")
            print(f"{go_back_num:3}. Go back")
            
            # Get selection
            try:
                choice = input(f"\nSelect option (1-{go_back_num}): ").strip()
                
                if choice == str(go_back_num):
                    return None
                elif choice == str(show_all_num):
                    selected = self.display_and_select_action(actions, f"All actions in {table_name}")
                    if selected:
                        return selected
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(menu_options):
                        type_name, type_actions = menu_options[idx]
                        selected = self.display_and_select_action(type_actions, 
                                                                 f"{type_name} ({table_name} table)")
                        if selected:
                            return selected
                    else:
                        print("Invalid selection. Please try again.")
                        
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning...")
                return None
    
    def browse_by_type(self):
        """Browse actions organized by action type."""
        # Group actions by type
        by_type = defaultdict(list)
        for action in self.actions_data:
            action_type = self.get_action_type_display(action)
            by_type[action_type].append(action)
        
        if not by_type:
            print("\nNo actions found.")
            return None
        
        while True:
            # Display types
            print("\n" + "="*70)
            print("SELECT ACTION TYPE:")
            print("-" * 40)
            
            # Sort types by count (descending) then name
            type_list = sorted(by_type.items(), key=lambda x: (-len(x[1]), x[0]))
            
            for i, (action_type, actions) in enumerate(type_list, 1):
                count = len(actions)
                plural = "action" if count == 1 else "actions"
                print(f"{i:3}. {action_type} ({count} {plural})")
            
            print(f"{len(type_list)+1:3}. Go back")
            
            # Get selection
            try:
                choice = input(f"\nSelect type (1-{len(type_list)}) or {len(type_list)+1} to go back: ").strip()
                
                if choice == str(len(type_list)+1):
                    return None
                    
                idx = int(choice) - 1
                if 0 <= idx < len(type_list):
                    selected_type, type_actions = type_list[idx]
                    selected = self.browse_type_actions(selected_type, type_actions)
                    if selected:
                        return selected
                else:
                    print("Invalid selection. Please try again.")
                    
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                return None
    
    def browse_type_actions(self, type_name, actions):
        """Browse actions of a specific type with table filtering."""
        while True:
            # Group by table
            by_table = defaultdict(list)
            for action in actions:
                table = action.get('source_table', 'Unknown')
                by_table[table].append(action)
            
            # Display table summary
            print("\n" + "="*70)
            print(f"{type_name.upper()}:")
            print(f"Found {len(actions)} {'action' if len(actions) == 1 else 'actions'} across {len(by_table)} {'table' if len(by_table) == 1 else 'tables'}:")
            print("-" * 40)
            
            # Sort tables by count (descending) then name
            table_counts = [(table, len(actions_list)) 
                           for table, actions_list in by_table.items()]
            table_counts.sort(key=lambda x: (-x[1], x[0]))
            
            for table, count in table_counts:
                plural = "action" if count == 1 else "actions"
                print(f"  {table} ({count} {plural})")
            
            # Display menu
            print("\nSELECT TABLE:")
            print("-" * 40)
            
            menu_options = []
            for i, (table, count) in enumerate(table_counts, 1):
                plural = "action" if count == 1 else "actions"
                print(f"{i:3}. {table} ({count} {plural})")
                menu_options.append((table, by_table[table]))
            
            show_all_num = len(menu_options) + 1
            go_back_num = show_all_num + 1
            
            print(f"{show_all_num:3}. Show all {len(actions)} {'action' if len(actions) == 1 else 'actions'}")
            print(f"{go_back_num:3}. Go back")
            
            # Get selection
            try:
                choice = input(f"\nSelect option (1-{go_back_num}): ").strip()
                
                if choice == str(go_back_num):
                    return None
                elif choice == str(show_all_num):
                    selected = self.display_and_select_action(actions, f"All {type_name}")
                    if selected:
                        return selected
                else:
                    idx = int(choice) - 1
                    if 0 <= idx < len(menu_options):
                        table, table_actions = menu_options[idx]
                        selected = self.display_and_select_action(table_actions, 
                                                                 f"{type_name} ({table} table)")
                        if selected:
                            return selected
                    else:
                        print("Invalid selection. Please try again.")
                        
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning...")
                return None
    
    def browse_all(self):
        """Browse all actions with count warning."""
        total = len(self.actions_data)
        
        if total == 0:
            print("\nNo actions found.")
            return None
        
        # Show all actions
        selected = self.display_and_select_action(self.actions_data, 
                                                 f"All actions ({total} total)")
        return selected
    
    def display_and_select_action(self, actions, title):
        """Display a list of actions and get user selection."""
        if not actions:
            print("\nNo actions to display.")
            return None
        
        while True:
            print("\n" + "="*70)
            print(title.upper())
            print("-" * 40)
            
            # Sort actions by name for consistent display
            sorted_actions = sorted(actions, key=lambda x: x.get('action_name', ''))
            
            # Display actions
            for i, action in enumerate(sorted_actions, 1):
                action_name = action.get('action_name', 'Unnamed')
                source_table = action.get('source_table', 'Unknown table')
                action_type = self.get_action_type_display(action)
                is_system = action.get('is_system_generated') == 'Yes'
                
                # Build display string
                if is_system:
                    print(f"{i:3}. {action_name} [SYSTEM]")
                else:
                    print(f"{i:3}. {action_name}")
                
                # Add details on second line for clarity
                print(f"     Table: {source_table} | Type: {action_type}")
                
                # Add prominence if it's meaningful
                prominence = action.get('action_prominence', '').strip()
                if prominence and prominence != 'Do not display':
                    print(f"     Prominence: {prominence}")
            
            print("-" * 40)
            
            # Get selection
            try:
                choice = input(f"\nSelect action (1-{len(sorted_actions)}) or 'back' to go back: ").strip()
                
                if choice.lower() in ['back', 'b']:
                    return None
                    
                idx = int(choice) - 1
                if 0 <= idx < len(sorted_actions):
                    return sorted_actions[idx]
                else:
                    print(f"Please enter a number between 1 and {len(sorted_actions)}")
                    
            except ValueError:
                print("Please enter a valid number or 'back' to go back.")
            except KeyboardInterrupt:
                print("\nReturning...")
                return None
    
    def display_selected_action(self, action):
        """Display comprehensive dependency analysis for the selected action."""
        action_name = action.get('action_name', 'Unnamed')
        
        print("\n" + "="*70)
        print(f"ANALYZING DEPENDENCIES FOR {action_name}")
        print("="*70)
        
        source_table = action.get('source_table', 'Unknown table')
        action_type = self.get_action_type_display(action)
        is_system = action.get('is_system_generated') == 'Yes'
        
        print(f"\nAction: {action_name}")
        print(f"Table: {source_table}")
        print(f"Type: {action_type}")
        if is_system:
            print("Status: System-generated")
        
        # Show basic action details
        if action.get('action_prominence'):
            print(f"Prominence: {action.get('action_prominence')}")
        
        if action.get('only_if_condition'):
            condition = action.get('only_if_condition')
            if len(condition) > 100:
                print(f"Condition: {condition[:100]}...")
            else:
                print(f"Condition: {condition}")
        
        if action.get('attach_to_column'):
            prominence = action.get('action_prominence', '')
            if 'Inline' in prominence:
                print(f"Attached to column: {action.get('attach_to_column')}")
            elif action.get('action_type_plain_english') == 'Navigate' and '[' in action.get('navigate_target', ''):
                # Navigate actions often reference columns but aren't "attached" in the UI sense
                pass  # Don't display attachment for navigate actions
            else:
                print(f"References column: {action.get('attach_to_column')}")
        
        # Analyze all dependencies
        print("\n" + "="*70)
        print(f"DEPENDENCY ANALYSIS FOR {action_name}")
        print("="*70)
        
        # Collect all dependency data
        view_deps = self.analyze_view_dependencies(action)
        action_deps = self.analyze_action_dependencies(action)
        column_deps = self.analyze_column_dependencies(action)
        slice_deps = self.analyze_slice_dependencies(action)
        format_deps = self.analyze_format_rule_dependencies(action)
        
        # Display summary
        print("\nDEPENDENCY SUMMARY:")
        print("-" * 40)

        if view_deps:
            count = len(view_deps)
            print(f"Views: {count} {'view uses' if count == 1 else 'views use'} this action")
        
        if action_deps['used_by'] or action_deps['uses']:
            used_by_count = len(action_deps['used_by'])
            uses_count = len(action_deps['uses'])
            if used_by_count:
                print(f"Actions (used by): {used_by_count} {'action invokes' if used_by_count == 1 else 'actions invoke'} this action")
            if uses_count:
                print(f"Actions (uses): This action invokes {uses_count} other {'action' if uses_count == 1 else 'actions'}")
        
        if column_deps:
            count = len(column_deps)
            print(f"Columns: Attached to {count} {'column' if count == 1 else 'columns'}")
        
        if slice_deps:
            count = len(slice_deps)
            print(f"Slices: {count} {'slice includes' if count == 1 else 'slices include'} this action")
        
        if format_deps:
            count = len(format_deps)
            print(f"Format Rules: {count} {'rule affects' if count == 1 else 'rules affect'} this action")
        
        if not any([view_deps, action_deps['used_by'], action_deps['uses'], column_deps, slice_deps, format_deps]):
            print("No dependencies found - this action appears to be unused")
        
        # Store analysis for detailed viewing
        self.current_analysis = {
            'action': action,
            'view_deps': view_deps,
            'action_deps': action_deps,
            'column_deps': column_deps,
            'slice_deps': slice_deps,
            'format_deps': format_deps
        }
        
        # Show interactive menu for details
        self.show_dependency_details_menu()
    
    def analyze_column_dependencies(self, action):
        """Find columns that have this action attached."""
        action_name = action.get('action_name')
        column_deps = []
        
        for column in self.columns_data:
            # Check if this action is attached to the column
            attached_action = column.get('attached_action', '').strip()
            if attached_action == action_name:
                column_deps.append({
                    'table': column.get('table_name'),
                    'column': column.get('column_name'),
                    'column_type': column.get('type'),
                    'is_virtual': column.get('is_virtual') == 'Yes'
                })
        
        return column_deps

    def analyze_view_dependencies(self, action):
        """Find views that use this action."""
        action_name = action.get('action_name')
        view_deps = []
        
        for view in self.views_data:
            # Skip unused system views entirely
            if view.get('view_name') in self.unused_system_views:
                continue
                
            usage_types = []
            
            # Check if action is in available_actions first (required for visibility)
            available_actions = view.get('available_actions', '').split('|||') if view.get('available_actions') else []
            available_actions = [a.strip() for a in available_actions if a.strip()]
            
            # Check event_actions with more detail
            event_actions = view.get('event_actions', '').split('|||') if view.get('event_actions') else []
            for event_action in event_actions:
                if event_action.strip() == action_name:
                    # Try to determine the event type from view configuration
                    view_config = view.get('view_configuration', '')
                    event_type = self.get_event_type_from_config(view_config, view.get('view_type', ''))
                    
                    if event_type:
                        usage_types.append(f'Event action ({event_type})')
                    else:
                        usage_types.append('Event action')
                    break
            
            # Check if action is actually displayed (using sophisticated visibility logic)
            if action_name in available_actions:
                if self.is_action_visible_in_view(action, view):
                    usage_types.append('Displayed action')
            
            # If we found any usage, add to dependencies
            if usage_types:
                view_deps.append({
                    'view_name': view.get('view_name'),
                    'view_type': view.get('view_type'),
                    'source_table': view.get('source_table'),
                    'is_system': view.get('is_system_view') == 'Yes',
                    'usage_types': usage_types
                })
        
        return view_deps
    
    def get_event_type_from_config(self, view_config, view_type):
        """Extract event type from view configuration."""
        if not view_config:
            return None
            
        try:
            import json
            config = json.loads(view_config)
            
            # Look for Events array in configuration
            events = config.get('Events', [])
            if events and isinstance(events, list):
                # Map event types to user-friendly names
                event_map = {
                    'Form Saved': 'form saved',
                    'Row Selected': 'row selected',
                    'Add': 'add',
                    'Edit': 'edit',
                    'Delete': 'delete',
                    'Sync': 'sync',
                    'Custom': 'custom',
                    'Swipe Left': 'swipe left',
                    'Swipe Right': 'swipe right'
                }
                
                # Get the first event type (most views only have one)
                if events[0] and isinstance(events[0], dict):
                    event_type = events[0].get('EventType', '')
                    return event_map.get(event_type, event_type.lower())
            
            # Fallback based on view type
            if view_type == 'form':
                return 'form saved'
            elif view_type in ['table', 'deck', 'gallery']:
                return 'row selected'
                
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        
        return None
                    
    def is_action_visible_in_view(self, action, view):
        """Check if an action is actually visible in a specific view."""
        action_name = action.get('action_name', '')
        prominence = action.get('action_prominence', '').replace('_', ' ')
        attach_to_column = action.get('attach_to_column', '')
        
        # Check if view is actually shown
        show_if = view.get('show_if', '').strip()
        if show_if.lower() == 'false':
            return False
        
        view_type = view.get('view_type', '').lower()
        
        # Check visibility based on view type and prominence
        if view_type == 'detail':
            if prominence in ['Display Prominently', 'Display Overlay']:
                return True
            elif prominence == 'Display Inline' and attach_to_column:
                # Check if column is visible in view - EXACT MATCH
                view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
                view_columns = [col.strip() for col in view_columns]
                return attach_to_column in view_columns  # Exact match, not substring
                
        elif view_type == 'table':
            if prominence == 'Display Inline' and attach_to_column:
                # Check if column is visible in view - EXACT MATCH
                view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
                view_columns = [col.strip() for col in view_columns]
                return attach_to_column in view_columns  # Exact match, not substring
                
        elif view_type in ['deck', 'gallery']:
            if view.get('show_action_bar', '').lower() == 'true':
                if prominence != 'Do not display':
                    if view.get('action_display_mode', '') == 'Manual':
                        # For Manual mode, must also be in referenced_actions
                        ref_actions = view.get('referenced_actions', '').split('|||') if view.get('referenced_actions') else []
                        return action_name in [r.strip() for r in ref_actions]
                    else:  # Automatic mode
                        return True
        
        return False
    
    def analyze_action_dependencies(self, action):
        """Find actions that use this action and actions used by this action."""
        action_name = action.get('action_name')
        
        used_by = []  # Actions that invoke this action
        uses = []      # Actions that this action invokes
        
        # First, find actions that invoke this action
        for other_action in self.actions_data:
            if other_action.get('action_name') == action_name:
                continue  # Skip self
            
            # Check if this action is referenced by the other action
            ref_actions = other_action.get('referenced_actions', '').split('|||') if other_action.get('referenced_actions') else []
            for ref_action in ref_actions:
                if ref_action.strip() == action_name:
                    action_type = self.get_action_type_display(other_action)
                    used_by.append({
                        'action_name': other_action.get('action_name'),
                        'source_table': other_action.get('source_table'),
                        'action_type': action_type,
                        'is_system': other_action.get('is_system_generated') == 'Yes',
                        'relationship': 'Invokes this action'
                    })
                    break
        
        # Second, find actions that this action invokes
        ref_actions = action.get('referenced_actions', '').split('|||') if action.get('referenced_actions') else []
        for ref_action_name in ref_actions:
            ref_action_name = ref_action_name.strip()
            if ref_action_name:
                # Find the referenced action details
                ref_action_data = None
                for other_action in self.actions_data:
                    if other_action.get('action_name') == ref_action_name:
                        ref_action_data = other_action
                        break
                
                if ref_action_data:
                    action_type = self.get_action_type_display(ref_action_data)
                    uses.append({
                        'action_name': ref_action_name,
                        'source_table': ref_action_data.get('source_table'),
                        'action_type': action_type,
                        'is_system': ref_action_data.get('is_system_generated') == 'Yes',
                        'relationship': 'Invoked by this action'
                    })
                else:
                    # Action referenced but not found in data
                    uses.append({
                        'action_name': ref_action_name,
                        'source_table': 'Unknown',
                        'action_type': 'Unknown',
                        'is_system': False,
                        'relationship': 'Invoked by this action (not found)'
                    })
        
        return {'used_by': used_by, 'uses': uses}

    def get_action_step_position(self, parent_action, target_action_name):
        """Get the step position of target action within parent action."""
        ref_actions = parent_action.get('referenced_actions', '').split('|||') if parent_action.get('referenced_actions') else []
        
        for i, ref_action in enumerate(ref_actions, 1):
            if ref_action.strip() == target_action_name:
                return i
        return None   

    def find_action_ancestry(self, target_action_name):
        """Find all complete ancestry chains that lead to the target action."""
        all_chains = []
        
        # Find immediate parents first
        immediate_parents = []
        for action in self.actions_data:
            ref_actions = action.get('referenced_actions', '').split('|||') if action.get('referenced_actions') else []
            ref_actions = [r.strip() for r in ref_actions if r.strip()]
            
            if target_action_name in ref_actions:
                immediate_parents.append(action.get('action_name'))
        
        if not immediate_parents:
            return []  # No parents, this is a root
        
        # For each immediate parent, find its ancestry
        for parent in immediate_parents:
            # Get the ancestry of this parent
            parent_chains = self.find_action_ancestry(parent)
            
            if parent_chains:
                # Add target to each parent chain
                for chain in parent_chains:
                    all_chains.append(chain + [target_action_name])
            else:
                # Parent is a root
                all_chains.append([parent, target_action_name])
        
        return all_chains

    def build_action_hierarchy(self, action_name, processed=None, depth=0, max_depth=10):
        """Recursively build hierarchy of actions invoked by this action."""
        if processed is None:
            processed = set()
        
        # Avoid infinite loops
        if action_name in processed or depth > max_depth:
            return []
        
        processed.add(action_name)
        hierarchy = []
        
        # Find the action data
        action_data = None
        for action in self.actions_data:
            if action.get('action_name') == action_name:
                action_data = action
                break
        
        if not action_data:
            return []
        
        # Get referenced actions
        ref_actions = action_data.get('referenced_actions', '').split('|||') if action_data.get('referenced_actions') else []
        
        for ref_action_name in ref_actions:
            ref_action_name = ref_action_name.strip()
            if ref_action_name:
                # Find the referenced action's details
                ref_data = None
                for other_action in self.actions_data:
                    if other_action.get('action_name') == ref_action_name:
                        ref_data = other_action
                        break
                
                # Build entry for this action
                entry = {
                    'name': ref_action_name,
                    'table': ref_data.get('source_table') if ref_data else 'Unknown',
                    'type': self.get_action_type_display(ref_data) if ref_data else 'Unknown',
                    'is_system': ref_data.get('is_system_generated') == 'Yes' if ref_data else False,
                    'depth': depth,
                    'children': []
                }
                
                # Recursively get children
                if ref_action_name not in processed:
                    entry['children'] = self.build_action_hierarchy(ref_action_name, processed, depth + 1, max_depth)
                elif depth < max_depth:
                    # Circular reference detected
                    entry['circular'] = True
                
                hierarchy.append(entry)
        
        return hierarchy

    def display_action_hierarchy(self, hierarchy, indent=0, number_prefix=""):
        """Display action hierarchy in tree format."""
        for i, entry in enumerate(hierarchy, 1):
            # Build the tree characters
            if indent == 0:
                prefix = f"{i}. "
                tree_char = ""
            else:
                prefix = number_prefix
                tree_char = "  " * (indent - 1) + "   └─ "
            
            # Build the display string
            system = " [SYSTEM]" if entry.get('is_system') else ""
            circular = " [CIRCULAR REF]" if entry.get('circular') else ""
            
            print(f"{tree_char}{prefix}{entry['name']}{system}{circular}")
            
            # Calculate proper indentation for details
            if indent == 0:
                detail_indent = "   "
            else:
                detail_indent = "  " * indent + "     "
            
            print(f"{detail_indent}Table: {entry['table']}")
            print(f"{detail_indent}Type: {entry['type']}")
            
            # Display children
            if entry.get('children'):
                for j, child in enumerate(entry['children'], 1):
                    child_prefix = f"{prefix}{j}."
                    self.display_action_hierarchy([child], indent + 1, child_prefix)

    def analyze_all_action_chains(self):
        """Analyze all actions to find chain depths."""
        chains_by_depth = {}
        
        for action in self.actions_data:
            action_name = action.get('action_name')
            
            # Build hierarchy for this action
            hierarchy = self.build_action_hierarchy(action_name)
            
            if hierarchy:
                # Calculate max depth
                max_depth = self.get_max_depth(hierarchy)
                
                if max_depth > 0:
                    if max_depth not in chains_by_depth:
                        chains_by_depth[max_depth] = []
                    
                    chains_by_depth[max_depth].append({
                        'action': action,
                        'hierarchy': hierarchy,
                        'total_actions': self.count_total_actions(hierarchy)
                    })
        
        return chains_by_depth
    
    def get_max_depth(self, hierarchy):
        """Get the maximum depth of an action hierarchy."""
        if not hierarchy:
            return 1  # Changed from 0 to 1 - the parent action itself is level 1
        
        max_depth = 2  # Changed from 1 to 2 - parent + immediate children
        for entry in hierarchy:
            if entry.get('children'):
                child_depth = 1 + self.get_max_depth(entry['children'])
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def count_total_actions(self, hierarchy):
        """Count total number of actions in hierarchy."""
        count = len(hierarchy)
        for entry in hierarchy:
            if entry.get('children'):
                count += self.count_total_actions(entry['children'])
        return count
    
    def show_chain_analysis_menu(self):
        """Show menu for analyzing action chains by depth."""
        print("\nAnalyzing all action chains...")
        chains_by_depth = self.analyze_all_action_chains()
        
        if not chains_by_depth:
            print("No action chains found in this app.")
            input("\nPress Enter to continue...")
            return
        
        while True:
            print("\n" + "="*70)
            print("ACTION CHAIN ANALYSIS")
            print("="*70)
            print("Found action chains of the following depths:\n")
            
            # Sort depths and create menu options
            sorted_depths = sorted(chains_by_depth.keys())
            menu_options = {}
            option_num = 1
            
            for depth in sorted_depths:
                chains = chains_by_depth[depth]
                count = len(chains)
                print(f"  {option_num}. {depth} levels ({count} {'chain' if count == 1 else 'chains'})")
                menu_options[option_num] = depth
                option_num += 1
            
           # Add show all option
            print(f"  {option_num}. Show all chains")
            show_all_num = option_num
            option_num += 1
            
            # Add return option
            print(f"  {option_num}. Return to main menu")
            return_num = option_num
            
            try:
                choice = input(f"\nSelect option (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                elif choice == str(show_all_num):
                    self.show_all_chains(chains_by_depth)
                else:
                    choice_num = int(choice)
                    if choice_num in menu_options:
                        depth = menu_options[choice_num]
                        self.show_chains_at_depth(chains_by_depth[depth], depth)
                    else:
                        print("Invalid choice. Please try again.")
                        
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break

    def show_chains_at_depth(self, chains, depth):
        """Show all action chains at a specific depth."""
        print("\n" + "="*70)
        print(f"ACTIONS WITH {depth}-LEVEL CHAINS ({len(chains)} total):")
        print("="*70)
        
        # Sort by action name
        sorted_chains = sorted(chains, key=lambda x: x['action'].get('action_name', ''))
        
        for i, chain_data in enumerate(sorted_chains, 1):
            action = chain_data['action']
            hierarchy = chain_data['hierarchy']
            total = chain_data['total_actions']
            
            print(f"\n{i}. {action.get('action_name')}")
            print(f"   Table: {action.get('source_table')}")
            print(f"   Type: {self.get_action_type_display(action)}")
            print(f"   Total actions in chain: {total}")
            print("   Chain structure:")
            
            # Show the hierarchy with indentation
            for entry in hierarchy:
                self.show_chain_tree(entry, indent=1)
        
        input("\nPress Enter to continue...")
    
    def show_chain_tree(self, entry, indent=1):
        """Display a single chain tree with proper indentation."""
        tree_char = "   " * (indent - 1) + "   └─ "
        print(f"{tree_char}{entry['name']}")
        
        if entry.get('children'):
            for child in entry['children']:
                self.show_chain_tree(child, indent + 1)

    def show_all_chains(self, chains_by_depth):
        """Show all chains grouped by depth."""
        print("\n" + "="*70)
        print("ALL ACTION CHAINS BY DEPTH:")
        print("="*70)
        
        for depth in sorted(chains_by_depth.keys()):
            chains = chains_by_depth[depth]
            print(f"\n{depth}-LEVEL CHAINS ({len(chains)} actions):")
            print("-" * 40)
            
            for chain_data in sorted(chains, key=lambda x: x['action'].get('action_name', '')):
                action = chain_data['action']
                total = chain_data['total_actions']
                print(f"  • {action.get('action_name')} ({total} total actions)")
        
        input("\nPress Enter to continue...")

    def analyze_slice_dependencies(self, action):
        """Find slices that include this action."""
        action_name = action.get('action_name')
        slice_deps = []
        
        for slice_data in self.slices_data:
            # Check if this action is in the slice's actions
            # Slices might have an 'actions' or 'slice_actions' field
            slice_actions = slice_data.get('actions', '').split('|||') if slice_data.get('actions') else []
            if not slice_actions:
                # Try alternative field name
                slice_actions = slice_data.get('slice_actions', '').split('|||') if slice_data.get('slice_actions') else []
            
            for slice_action in slice_actions:
                if slice_action.strip() == action_name:
                    slice_deps.append({
                        'slice_name': slice_data.get('slice_name'),
                        'source_table': slice_data.get('source_table'),
                        'row_filter': slice_data.get('row_filter_condition', '')[:100] + '...' if len(slice_data.get('row_filter_condition', '')) > 100 else slice_data.get('row_filter_condition', '')
                    })
                    break
        
        return slice_deps
    
    def analyze_format_rule_dependencies(self, action):
        """Find format rules that affect this action."""
        action_name = action.get('action_name')
        format_deps = []
        
        for rule in self.format_rules_data:
            # Check if this action is affected by the format rule
            # Format rules might reference actions in their formatted_actions field
            formatted_actions = rule.get('formatted_actions', '').split('|||') if rule.get('formatted_actions') else []
            
            for formatted_action in formatted_actions:
                if formatted_action.strip() == action_name:
                    format_deps.append({
                        'rule_name': rule.get('rule_name'),
                        'source_table': rule.get('source_table'),
                        'condition': rule.get('condition', '')[:100] + '...' if len(rule.get('condition', '')) > 100 else rule.get('condition', ''),
                        'is_disabled': rule.get('is_disabled') == 'Yes'
                    })
                    break
        
        return format_deps
    
    def show_dependency_details_menu(self):
        """Show interactive menu for viewing dependency details."""
        while True:
            print("\n" + "-"*70)
            print("VIEW DEPENDENCY DETAILS:")
            
            menu_options = {}
            option_num = 1
            
            # View dependencies
            if self.current_analysis['view_deps']:
                count = len(self.current_analysis['view_deps'])
                print(f"  {option_num}. View dependencies ({count} {'view' if count == 1 else 'views'})")
                menu_options[option_num] = 'views'
                option_num += 1
            
            # Action dependencies - used by
            if self.current_analysis['action_deps']['used_by']:
                count = len(self.current_analysis['action_deps']['used_by'])
                print(f"  {option_num}. Actions that invoke this ({count} {'action' if count == 1 else 'actions'})")
                menu_options[option_num] = 'used_by'
                option_num += 1
            
            # Action dependencies - uses
            if self.current_analysis['action_deps']['uses']:
                count = len(self.current_analysis['action_deps']['uses'])
                print(f"  {option_num}. Actions invoked by this ({count} {'action' if count == 1 else 'actions'})")
                menu_options[option_num] = 'uses'
                option_num += 1
            
            # Column dependencies
            if self.current_analysis['column_deps']:
                count = len(self.current_analysis['column_deps'])
                print(f"  {option_num}. Column attachments ({count} {'column' if count == 1 else 'columns'})")
                menu_options[option_num] = 'columns'
                option_num += 1
            
            # Slice dependencies
            if self.current_analysis['slice_deps']:
                count = len(self.current_analysis['slice_deps'])
                print(f"  {option_num}. Slice dependencies ({count} {'slice' if count == 1 else 'slices'})")
                menu_options[option_num] = 'slices'
                option_num += 1
            
            # Format rule dependencies
            if self.current_analysis['format_deps']:
                count = len(self.current_analysis['format_deps'])
                print(f"  {option_num}. Format rule dependencies ({count} {'rule' if count == 1 else 'rules'})")
                menu_options[option_num] = 'format_rules'
                option_num += 1
            
            # Return option
            print(f"  {option_num}. Return to search")
            return_num = option_num
            
            try:
                choice = input(f"\nEnter your choice (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                
                choice_num = int(choice)
                
                if choice_num in menu_options:
                    dep_type = menu_options[choice_num]
                    
                    if dep_type == 'views':
                        self.show_view_dependencies_detail()
                    elif dep_type == 'used_by':
                        self.show_action_used_by_detail()
                    elif dep_type == 'uses':
                        self.show_action_uses_detail()
                    elif dep_type == 'columns':
                        self.show_column_dependencies_detail()
                    elif dep_type == 'slices':
                        self.show_slice_dependencies_detail()
                    elif dep_type == 'format_rules':
                        self.show_format_dependencies_detail()
                else:
                    print("Invalid choice. Please try again.")
                    
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning to search...")
                break

    def show_view_dependencies_detail(self):
        """Show detailed view dependencies."""
        view_deps = self.current_analysis['view_deps']
        action = self.current_analysis['action']
        action_name = action.get('action_name')
        
        print("\n" + "="*70)
        print(f"VIEWS USING {action_name}:")
        print("="*70)
        
        for dep in view_deps:
            system = " [SYSTEM]" if dep['is_system'] else ""
            print(f"\n{dep['view_name']}{system}")
            print(f"  View type: {dep.get('view_type', 'unknown')}")
            print(f"  Table: {dep['source_table']}")
            for usage in dep['usage_types']:
                print(f"  • {usage}")
        
        input("\nPress Enter to continue...")
    
    def show_action_used_by_detail(self):
        """Show actions that invoke this action with full ancestry context."""
        action = self.current_analysis['action']
        action_name = action.get('action_name')
        
        print("\n" + "="*70)
        print(f"ACTIONS THAT INVOKE {action_name} (FULL ANCESTRY):")
        print("="*70)
        
        # Find all ancestry chains
        ancestry_chains = self.find_action_ancestry(action_name)
        
        if not ancestry_chains:
            # Fallback to immediate parents if ancestry search fails
            used_by = self.current_analysis['action_deps']['used_by']
            if used_by:
                print("\nShowing immediate parents only:")
                for i, dep in enumerate(used_by, 1):
                    print(f"\n{i}. {dep['action_name']}")
                    print(f"   Table: {dep['source_table']}")
                    print(f"   Type: {dep['action_type']}")
                    print(f"   └─ {action_name} [THIS ACTION]")
                    
                    # Show descendants
                    hierarchy = self.build_action_hierarchy(action_name)
                    if hierarchy:
                        self.display_sub_hierarchy(hierarchy, indent=2)
            else:
                print("\nNo parent actions found - this is a root action.")
                print(f"\n{action_name} [THIS ACTION - ROOT]")
                print(f"   Table: {action.get('source_table')}")
                print(f"   Type: {self.get_action_type_display(action)}")
                # Show descendants for root action
                hierarchy = self.build_action_hierarchy(action_name)
                if hierarchy:
                    self.display_sub_hierarchy(hierarchy, indent=1)
        else:
            for i, chain in enumerate(ancestry_chains, 1):
                if len(ancestry_chains) > 1:
                    print(f"\nChain {i}:")
                else:
                    print()
                
                # Display complete vertical chain with proper indentation
                for level, action_in_chain in enumerate(chain):
                    # Get action details
                    action_data = None
                    for act in self.actions_data:
                        if act.get('action_name') == action_in_chain:
                            action_data = act
                            break
                    
                    # Build indentation
                    if level == 0:
                        print(f"{action_in_chain}")
                        if action_data:
                            print(f"   Table: {action_data.get('source_table')}")
                            print(f"   Type: {self.get_action_type_display(action_data)}")
                    else:
                        indent = "   " * level
                        if action_in_chain == action_name:
                            print(f"{indent}└─ {action_in_chain} [THIS ACTION]")
                            # Show descendants with proper indentation continuing from here
                            hierarchy = self.build_action_hierarchy(action_name)
                            if hierarchy:
                                self.display_sub_hierarchy(hierarchy, indent=level+1)
                        else:
                            print(f"{indent}└─ {action_in_chain}")
        
        input("\nPress Enter to continue...")

    def show_action_uses_detail(self):
        """Show actions that this action invokes with full hierarchy."""
        uses = self.current_analysis['action_deps']['uses']
        action = self.current_analysis['action']
        action_name = action.get('action_name')
        
        print("\n" + "="*70)
        print(f"ACTIONS INVOKED BY {action_name}:")
        print("="*70)
        
        if not uses:
            print("\nThis action does not invoke any other actions.")
        else:
            # Build and display the hierarchy for this action
            hierarchy = self.build_action_hierarchy(action.get('action_name'))
            
            if hierarchy:
                print(f"\n{action.get('action_name')} [THIS ACTION]")
                print(f"  Table: {action.get('source_table')}")
                print(f"  Type: {self.get_action_type_display(action)}")
                print("  Invokes the following actions:")
                
                # Display the hierarchy tree
                self.display_action_hierarchy(hierarchy, indent=1)
            else:
                # Fallback to simple list if hierarchy building fails
                for i, dep in enumerate(uses, 1):
                    system = " [SYSTEM]" if dep['is_system'] else ""
                    print(f"\n{i}. {dep['action_name']}{system}")
                    print(f"   Table: {dep['source_table']}")
                    print(f"   Type: {dep['action_type']}")
                    print(f"   Status: {dep['relationship']}")
        
        input("\nPress Enter to continue...")
    
    def display_sub_hierarchy(self, hierarchy, indent=1):
        """Display sub-hierarchy with proper indentation."""
        for entry in hierarchy:
            tree_char = "   " * indent + "└─ "
            print(f"{tree_char}{entry['name']}")
            
            # Recursively display all children (grandchildren, great-grandchildren, etc.)
            if entry.get('children'):
                self.display_sub_hierarchy(entry['children'], indent + 1)
    
    def show_column_dependencies_detail(self):
        """Show detailed column dependencies."""
        column_deps = self.current_analysis['column_deps']
        action = self.current_analysis['action']
        action_name = action.get('action_name')
        
        print("\n" + "="*70)
        print(f"COLUMNS WITH {action_name} ATTACHED:")
        print("="*70)
        
        for dep in column_deps:
            virtual = " [VIRTUAL]" if dep['is_virtual'] else ""
            print(f"\n{dep['table']}[{dep['column']}]{virtual}")
            print(f"  Type: {dep['column_type']}")
        
        input("\nPress Enter to continue...")
    
    def show_slice_dependencies_detail(self):
        """Show detailed slice dependencies."""
        slice_deps = self.current_analysis['slice_deps']
        action = self.current_analysis['action']
        action_name = action.get('action_name')
        
        print("\n" + "="*70)
        print(f"SLICES INCLUDING {action_name}:")
        print("="*70)
        
        for dep in slice_deps:
            print(f"\n{dep['slice_name']}")
            print(f"  Table: {dep['source_table']}")
            if dep['row_filter']:
                print(f"  Filter: {dep['row_filter']}")
        
        input("\nPress Enter to continue...")
    
    def show_format_dependencies_detail(self):
        """Show detailed format rule dependencies."""
        format_deps = self.current_analysis['format_deps']
        action = self.current_analysis['action']
        action_name = action.get('action_name')
        
        print("\n" + "="*70)
        print(f"FORMAT RULES AFFECTING {action_name}:")
        print("="*70)
        
        for dep in format_deps:
            disabled = " [DISABLED]" if dep['is_disabled'] else ""
            print(f"\n{dep['rule_name']}{disabled}")
            print(f"  Table: {dep['source_table']}")
            if dep['condition']:
                print(f"  Condition: {dep['condition']}")
        
        input("\nPress Enter to continue...")

    def show_main_menu(self):
        """Display the main menu and handle user selection."""
        while True:
            total_actions = len(self.actions_data)
            
            print("\n" + "="*70)
            print("ACTION SEARCH MENU")
            print("="*70)
            print("How would you like to find an action?")
            print()
            print("  1. Search by name (partial match)")
            print("  2. Browse by table")
            print("  3. Browse by action type")
            print(f"  4. Browse all actions ({total_actions} total)")
            print("  5. Analyze action chains")
            print("  6. Quit")
            print()
            
            try:
                choice = input("Enter your choice (1-6): ").strip()
                
                if choice == '1':
                    selected = self.search_by_name()
                    if selected:
                        self.display_selected_action(selected)
                        
                elif choice == '2':
                    selected = self.browse_by_table()
                    if selected:
                        self.display_selected_action(selected)
                        
                elif choice == '3':
                    selected = self.browse_by_type()
                    if selected:
                        self.display_selected_action(selected)
                        
                elif choice == '4':
                    selected = self.browse_all()
                    if selected:
                        self.display_selected_action(selected)
                        
                elif choice == '5':
                    self.show_chain_analysis_menu()
                    
                elif choice == '6':
                    if self.return_to_hub:
                        print("\nReturning to dependency analysis menu...")
                    else:
                        print("\nGoodbye!")
                    break
                    
                else:
                    print("Invalid choice. Please enter a number between 1 and 6.")
                    
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}")
                print("Please try again.")
    
    def run(self, return_to_hub=False):
        """Main execution method."""
        if return_to_hub:
            self.return_to_hub = return_to_hub
        
        print("AppSheet Action Dependency Analyzer")
        print("Phase 1: Action Selection Interface")
        print("===================================")
        
        # Load actions data (required)
        if not self.load_actions_data():
            return
        
        # Load other component data (optional but enhances analysis)
        print("\nLoading additional component data:")
        self.load_columns_data()
        self.load_views_data()
        self.load_slices_data()
        self.load_format_rules_data()

        # Load unused system views to exclude from analysis
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
        
        # Show main menu
        self.show_main_menu()

def main():
    """Main entry point."""
    # Check if a path was provided
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Create and run analyzer
    analyzer = ActionDependencyAnalyzer(base_path)
    analyzer.run()


if __name__ == "__main__":
    main()
