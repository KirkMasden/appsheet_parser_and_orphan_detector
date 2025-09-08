#!/usr/bin/env python3
"""
Column Dependency Analyzer for AppSheet Parser Suite

This script analyzes dependencies for a selected column, showing all components
that reference or depend on it (columns, slices, actions, format rules, views).

Author: Kirk Masden & Claude
Version: 2.0 - Fixed false positives in view matching, added json import, refactored data loading
"""

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

class ColumnDependencyAnalyzer:
    def __init__(self, base_path=".", return_to_hub=False):
        """Initialize the analyzer with the base path containing CSV files."""
        self.base_path = Path(base_path)
        self.return_to_hub = return_to_hub
        self.columns_data = []
        self.column_lookup = {}  # For quick searching
        self.slices_data = []
        self.actions_data = []
        self.views_data = []
        self.format_rules_data = []
        self.unused_system_views = set() 


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
        columns_file = self.base_path / "appsheet_columns.csv"
        
        if not columns_file.exists():
            print(f"Error: Could not find {columns_file}")
            print("Please ensure appsheet_columns.csv is in the current directory.")
            return False
            
        try:
            with open(columns_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.columns_data.append(row)
                    # Create searchable identifier
                    identifier = row['unique_identifier']
                    self.column_lookup[identifier.lower()] = row
                    
            print(f"Loaded {len(self.columns_data)} columns from {columns_file.name}")
            return True
            
        except Exception as e:
            print(f"Error reading columns file: {e}")
            return False

    def load_slices_data(self):
        """Load the slices data from appsheet_slices.csv."""
        return self._load_data("appsheet_slices.csv", "slices_data", "slices")

    def load_actions_data(self):
        """Load the actions data from appsheet_actions.csv."""
        return self._load_data("appsheet_actions.csv", "actions_data", "actions")

    def load_views_data(self):
        """Load the views data from appsheet_views.csv."""
        return self._load_data("appsheet_views.csv", "views_data", "views")

    def load_format_rules_data(self):
        """Load the format rules data from appsheet_format_rules.csv."""
        return self._load_data("appsheet_format_rules.csv", "format_rules_data", "format rules")

    def search_columns(self, search_term):
        """Search for columns matching the search term."""
        search_term = search_term.lower().strip()
        matches = []
        
        for column in self.columns_data:
            identifier = column['unique_identifier']
            table_name = column['table_name']
            column_name = column['column_name']
            
            # Check various matching patterns
            if (identifier.lower().startswith(search_term) or
                column_name.lower().startswith(search_term.replace(f"{table_name.lower()}[", "").rstrip("]")) or
                (search_term in identifier.lower())):
                matches.append(column)
                
        return matches
    
    def display_matches(self, matches):
        """Display matching columns in a numbered list."""
        if not matches:
            print("\nNo columns found matching your search term.")
            return None
            
        count = len(matches)
        print(f"\nFound {count} matching {'column' if count == 1 else 'columns'}:")
        print("-" * 60)
        
        for i, column in enumerate(matches, 1):
            identifier = column['unique_identifier']
            is_virtual = column['is_virtual']
            col_type = column['type']
            
            # Add virtual indicator
            virtual_indicator = " [VIRTUAL]" if is_virtual == "Yes" else ""
            
            print(f"{i:3}. {identifier}{virtual_indicator} - Type: {col_type}")
            
            # Show description if available
            if column.get('description'):
                print(f"     Description: {column['description']}")
                
        print("-" * 60)
        return matches
    
    def get_user_selection(self, matches):
        """Get user's selection from the list of matches."""
        while True:
            try:
                selection = input("\nEnter the number of the column to analyze (or 'q' to quit): ").strip()
                
                if selection.lower() == 'q':
                    return None
                    
                index = int(selection) - 1
                if 0 <= index < len(matches):
                    return matches[index]
                else:
                    print(f"Please enter a number between 1 and {len(matches)}")
                    
            except ValueError:
                print("Please enter a valid number or 'q' to quit")

    def categorize_references(self, column, target_identifier, target_column_name, target_table_name):
        """Categorize how a column references the target column."""
        categories = []
        
        # Check in app_formula
        if column.get('app_formula') and (target_identifier in column['app_formula'] or 
                                         f"[{target_column_name}]" in column['app_formula'] or
                                         target_column_name in column['app_formula']):
            categories.append('app_formula')
        
        # Check in show_if (separate field)
        if column.get('show_if') and (target_identifier in column['show_if'] or 
                                      f"[{target_column_name}]" in column['show_if'] or
                                      target_column_name in column['show_if']):
            categories.append('show_if')
            
        # Check in valid_if (separate field)
        if column.get('valid_if') and (target_identifier in column['valid_if'] or 
                                       f"[{target_column_name}]" in column['valid_if'] or
                                       target_column_name in column['valid_if']):
            categories.append('valid_if')
            
        # Check in required_if (separate field)
        if column.get('required_if') and (target_identifier in column['required_if'] or 
                                          f"[{target_column_name}]" in column['required_if'] or
                                          target_column_name in column['required_if']):
            categories.append('required_if')
            
        # Check in editable_if (separate field)
        if column.get('editable_if') and (target_identifier in column['editable_if'] or 
                                          f"[{target_column_name}]" in column['editable_if'] or
                                          target_column_name in column['editable_if']):
            categories.append('editable_if')
            
        # Check in suggested_values (separate field)
        if column.get('suggested_values') and (target_identifier in column['suggested_values'] or 
                                               f"[{target_column_name}]" in column['suggested_values'] or
                                               target_column_name in column['suggested_values']):
            categories.append('suggested_values')

        # Check in display_name
        if column.get('display_name') and (target_identifier in column['display_name'] or 
                                          f"[{target_column_name}]" in column['display_name'] or
                                          target_column_name in column['display_name']):
            categories.append('display_name')
            
        # Check in initial_value
        if column.get('initial_value') and (target_identifier in column['initial_value'] or 
                                           f"[{target_column_name}]" in column['initial_value'] or
                                           target_column_name in column['initial_value']):
            categories.append('initial_value')
            
        # Check in type_qualifier_formulas (includes show_if, valid_if, etc.)
        if column.get('type_qualifier_formulas'):
            tq = column['type_qualifier_formulas']
            if target_identifier in tq or f"[{target_column_name}]" in tq or target_column_name in tq:
                # Try to identify specific formula types
                if 'Show_If:' in tq:
                    categories.append('show_if')
                if 'Valid_If:' in tq:
                    categories.append('valid_if')
                if 'Required_If:' in tq:
                    categories.append('required_if')
                if 'Editable_If:' in tq:
                    categories.append('editable_if')
                if 'Suggested_Values:' in tq:
                    categories.append('suggested_values')
                # If no specific type found, use generic
                if not any(cat in categories for cat in ['show_if', 'valid_if', 'required_if', 'editable_if', 'suggested_values']):
                    categories.append('type_qualifier_formulas')
                    
        return categories
    
    def analyze_column_dependencies(self, selected_column):
        """Analyze which other columns reference the selected column."""
        identifier = selected_column['unique_identifier']
        table_name = selected_column['table_name']
        column_name = selected_column['column_name']
        
        print(f"\n{'='*70}")
        print(f"ANALYZING DEPENDENCIES FOR {identifier}")
        print(f"{'='*70}")
        
        # Show basic column info
        print(f"\nColumn Information:")
        print(f"  Table: {table_name}")
        print(f"  Column: {column_name}")
        print(f"  Type: {selected_column['type']}")
        print(f"  Virtual: {selected_column['is_virtual']}")
        
        if selected_column.get('description'):
            print(f"  Description: {selected_column['description']}")
            
        if selected_column.get('app_formula'):
            formula = selected_column['app_formula']
            if len(formula) > 500:
                print(f"  Formula: {formula[:500]}... ({len(formula)} characters total)")
            else:
                print(f"  Formula: {formula}")
                
        # Collect all dependency data first
        # 1. Column dependencies
        referencing_columns = []
        reference_details = defaultdict(lambda: defaultdict(list))
        category_totals = defaultdict(list)
        
        for column in self.columns_data:
            if column['unique_identifier'] == identifier:
                continue  # Skip self
                
            # Check if this column is referenced
            referenced_cols = column.get('referenced_columns', '').split('|||') if column.get('referenced_columns') else []
            
            # Also check in other fields
            is_referenced = False
            for ref in referenced_cols:
                ref = ref.strip()
                if ref and (ref == identifier or 
                           ref == f"[{column_name}]" or 
                           ref == column_name or
                           ref == f"{table_name}[{column_name}]"):
                    is_referenced = True
                    break
                    
            if is_referenced:
                # Categorize the reference
                categories = self.categorize_references(column, identifier, column_name, table_name)
                if categories:
                    referencing_columns.append(column)
                    ref_table = column['table_name']
                    
                    for category in categories:
                        reference_details[ref_table][category].append(column)
                        category_totals[category].append(column)
        
        # 2. View dependencies
        view_dependencies = self.analyze_view_dependencies(selected_column)

        # 3. Slice dependencies
        slice_dependencies = self.analyze_slice_dependencies(selected_column)

        # 4. Format rule dependencies
        format_rule_dependencies = self.analyze_format_rule_dependencies(selected_column)
        
        # 5. Action dependencies
        action_dependencies = self.analyze_action_dependencies(selected_column)
        
        # Display summary first
        print(f"\n{'='*70}")
        print(f"DEPENDENCY SUMMARY FOR {identifier}")
        print(f"{'='*70}")
        
        # Column summary
        count = len(referencing_columns)
        print(f"\nColumns: {count} {'column references' if count == 1 else 'columns reference'} this column")
        if referencing_columns:
            for category, columns in sorted(category_totals.items()):
                cat_display = category.replace('_', ' ').title()
                count = len(columns)
                print(f"  - {cat_display}: {count} {'column' if count == 1 else 'columns'}")
        
        # View summary
        count = len(view_dependencies)
        print(f"\nViews: {count} {'view uses' if count == 1 else 'views use'} this column")
        if self.unused_system_views:
            print(f"  Note: {len(self.unused_system_views)} unreachable system views excluded from analysis")
        if view_dependencies:
            # Count usage types across all views
            view_usage_counts = defaultdict(int)
            for view_dep in view_dependencies:
                for usage in view_dep['usage_types']:
                    view_usage_counts[usage] += 1
            
            for usage, count in sorted(view_usage_counts.items()):
                print(f"  - {usage}: {count} {'view' if count == 1 else 'views'}")
        
        # Slice summary
        count = len(slice_dependencies)
        print(f"\nSlices: {count} {'slice uses' if count == 1 else 'slices use'} this column in filter conditions")
        if slice_dependencies:
            # Group by source table for summary
            by_table = defaultdict(int)
            for slice_dep in slice_dependencies:
                by_table[slice_dep['source_table']] += 1
            
            for table, count in sorted(by_table.items()):
                print(f"  - From {table}: {count} {'slice' if count == 1 else 'slices'}")

        # Format Rule summary
        count = len(format_rule_dependencies)
        print(f"\nFormat Rules: {count} {'format rule affects or uses' if count == 1 else 'format rules affect or use'} this column")
        if format_rule_dependencies:
            # Count by usage type
            formatting_count = 0
            condition_count = 0
            disabled_count = 0
            
            for rule_dep in format_rule_dependencies:
                if rule_dep['is_disabled']:
                    disabled_count += 1
                for usage in rule_dep['usage_types']:
                    if 'formatted by' in usage:
                        formatting_count += 1
                    elif 'condition' in usage or 'Referenced' in usage:
                        condition_count += 1
            
            if formatting_count > 0:
                print(f"  - Formatting this column: {formatting_count} {'rule' if formatting_count == 1 else 'rules'}")
            if condition_count > 0:
                print(f"  - Using in conditions: {condition_count} {'rule' if condition_count == 1 else 'rules'}")
            if disabled_count > 0:
                print(f"  - Disabled rules: {disabled_count}")
        
        # Action summary
        count = len(action_dependencies)
        print(f"\nActions: {count} {'action uses' if count == 1 else 'actions use'} this column")
        if action_dependencies:
            # Count by usage type
            usage_counts = defaultdict(int)
            system_count = 0
            for action_dep in action_dependencies:
                if action_dep['is_system']:
                    system_count += 1
                for usage in action_dep['usage_types']:
                    usage_counts[usage] += 1
            
            for usage, count in sorted(usage_counts.items()):
                print(f"  - {usage}: {count} {'action' if count == 1 else 'actions'}")
            if system_count > 0:
                print(f"  - System-generated from this column: {system_count} {'action' if system_count == 1 else 'actions'}")
        
        # Store all data for menu
        self.current_analysis = {
            'column_data': {
                'referencing_columns': referencing_columns,
                'reference_details': reference_details,
                'category_totals': category_totals
            },
            'view_data': {
                'dependencies': view_dependencies
            },
            'slice_data': {
                'dependencies': slice_dependencies
            },
            'format_rule_data': {
                'dependencies': format_rule_dependencies
            },
            'action_data': {
                'dependencies': action_dependencies
            }
        }
        self.current_analysis['selected_identifier'] = identifier

        # Show interactive menu
        self.show_main_analysis_menu()

    def show_main_analysis_menu(self):
        """Show the main menu for viewing detailed dependency information."""
        while True:
            print(f"\n{'-'*70}")
            print("VIEW DETAILED INFORMATION:")
            
            menu_options = {}
            option_num = 1
            
            # Column options
            if self.current_analysis['column_data']['referencing_columns']:
                count = len(self.current_analysis['column_data']['referencing_columns'])
                print(f"  {option_num}. Column dependencies ({count} {'column' if count == 1 else 'columns'})")
                menu_options[option_num] = ('columns', None)
                option_num += 1
            
            # View options
            if self.current_analysis['view_data']['dependencies']:
                count = len(self.current_analysis['view_data']['dependencies'])
                print(f"  {option_num}. View dependencies ({count} {'view' if count == 1 else 'views'})")
                menu_options[option_num] = ('views', None)
                option_num += 1
            
            # Slice options
            if self.current_analysis.get('slice_data', {}).get('dependencies'):
                count = len(self.current_analysis['slice_data']['dependencies'])
                print(f"  {option_num}. Slice dependencies ({count} {'slice' if count == 1 else 'slices'})")
                menu_options[option_num] = ('slices', None)
                option_num += 1
            
            # Format Rule options
            if self.current_analysis.get('format_rule_data', {}).get('dependencies'):
                count = len(self.current_analysis['format_rule_data']['dependencies'])
                print(f"  {option_num}. Format Rule dependencies ({count} {'rule' if count == 1 else 'rules'})")
                menu_options[option_num] = ('format_rules', None)
                option_num += 1
            
            # Action options
            if self.current_analysis.get('action_data', {}).get('dependencies'):
                count = len(self.current_analysis['action_data']['dependencies'])
                print(f"  {option_num}. Action dependencies ({count} {'action' if count == 1 else 'actions'})")
                menu_options[option_num] = ('actions', None)
                option_num += 1
            
            # Always available options
            print(f"  {option_num}. Return to search")
            return_num = option_num
            
            try:
                choice = input(f"\nEnter your choice (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                    
                choice_num = int(choice)
                
                if choice_num in menu_options:
                    dep_type, _ = menu_options[choice_num]
                    if dep_type == 'columns':
                        self.show_column_dependencies_detail()
                    elif dep_type == 'views':
                        self.show_view_dependencies_detail()
                    elif dep_type == 'slices':
                        self.show_slice_dependencies_detail()
                    elif dep_type == 'format_rules':
                        self.show_format_rule_dependencies_detail()
                    elif dep_type == 'actions':
                        self.show_action_dependencies_detail()
                else:
                    print("Invalid choice. Please try again.")
                    
            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nReturning to search...")
                break

    def show_column_dependencies_detail(self):
        """Show detailed menu for column dependencies."""
        data = self.current_analysis['column_data']
        reference_details = data['reference_details']
        category_totals = data['category_totals']
        
        # Build menu options
        table_options = {}
        category_options = {}
        option_num = 1
        
        # Table options
        for table in sorted(reference_details.keys()):
            table_options[option_num] = ('table', table)
            option_num += 1
        
        # Category options
        for category in sorted(category_totals.keys()):
            category_options[option_num] = ('category', category)
            option_num += 1
        
        # Show the existing reference details menu
        self.show_reference_details_menu(reference_details, category_totals, 
                                        table_options, category_options)
    
    def show_view_dependencies_detail(self):
        """Show detailed menu for view dependencies."""
        view_deps = self.current_analysis['view_data']['dependencies']
        
        if not view_deps:
            print("\nNo view dependencies found.")
            return
        
        # Pre-calculate which options have content
        user_views = [v for v in view_deps if not v['is_system']]
        system_views = [v for v in view_deps if v['is_system']]
        
        while True:
            print(f"\n{'-'*70}")
            print("VIEW DEPENDENCIES - Select display option:")
            
            menu_options = {}
            option_num = 1
            
            # Always show "all views"
            print(f"  {option_num}. Show all views with details")
            menu_options[option_num] = 'all'
            option_num += 1
            
            # Always show group by type (if we have views)
            print(f"  {option_num}. Group by view type")
            menu_options[option_num] = 'by_type'
            option_num += 1
            
            # Only show if we have user views
            if user_views:
                print(f"  {option_num}. Show only user views ({len(user_views)} {'view' if len(user_views) == 1 else 'views'})")
                menu_options[option_num] = 'user'
                option_num += 1
            
            # Only show if we have system views
            if system_views:
                print(f"  {option_num}. Show only system views ({len(system_views)} {'view' if len(system_views) == 1 else 'views'})")
                menu_options[option_num] = 'system'
                option_num += 1
            
            # Return option
            print(f"  {option_num}. Return to main menu")
            return_num = option_num
            
            try:
                choice = input(f"\nEnter your choice (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                    
                choice_num = int(choice)
                
                if choice_num in menu_options:
                    option = menu_options[choice_num]
                    
                    if option == 'all':
                        self.show_all_view_dependencies(view_deps)
                    elif option == 'by_type':
                        self.show_views_by_type(view_deps)
                    elif option == 'user':
                        self.show_all_view_dependencies(user_views, "USER VIEWS")
                    elif option == 'system':
                        self.show_all_view_dependencies(system_views, "SYSTEM VIEWS")
                else:
                    print("Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
    
    def show_all_view_dependencies(self, view_deps, title="ALL VIEWS"):
        """Display all view dependencies with details."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        print(f"\n{'='*70}")
        # Only add "USING {ident}" if title is generic
        if title in ["ALL VIEWS", "USER VIEWS", "SYSTEM VIEWS"]:
            print(f"{title} USING {ident}:")
        else:
            print(f"{title}:")
        print(f"{'='*70}")
        
        for view_dep in view_deps:
            view_name = view_dep['view_name']
            view_type = view_dep['view_type']
            is_system = view_dep['is_system']
            usage_types = view_dep['usage_types']
            
            # Build view description
            view_desc = f"{view_name} ({view_type} view"
            if is_system:
                view_desc += " - System"
            else:
                view_desc += " - User"
            view_desc += "):"
            
            print(f"\n  {view_desc}")
            for usage in usage_types:
                print(f"    - {usage}")
                
                # Show the actual formula/condition when relevant
                if usage == 'Used in show_if condition':
                    # Find the original view data to get the show_if formula
                    for view in self.views_data:
                        if view.get('view_name') == view_name:
                            show_if = view.get('show_if', '')
                            if show_if:
                                if len(show_if) > 150:
                                    print(f"      Show_If: {show_if[:150]}...")
                                else:
                                    print(f"      Show_If: {show_if}")
                            break

    
    def show_views_by_type(self, view_deps):
        """Display view dependencies grouped by view type."""
        print(f"\n{'='*70}")
        print(f"VIEWS BY TYPE:")
        print(f"{'='*70}")
        
        # Group by view type
        by_type = {}
        for view_dep in view_deps:
            view_type = view_dep['view_type']
            if view_type not in by_type:
                by_type[view_type] = []
            by_type[view_type].append(view_dep)
        
        # Display each type
        for view_type in sorted(by_type.keys()):
            views = by_type[view_type]
            print(f"\n{view_type.upper()} VIEWS ({len(views)}):")
            print("-" * 40)
            
            for view_dep in views:
                view_name = view_dep['view_name']
                is_system = " (System)" if view_dep['is_system'] else ""
                print(f"  • {view_name}{is_system}")
                for usage in view_dep['usage_types']:
                    print(f"      - {usage}")

    def show_slice_dependencies_detail(self):
        """Show detailed menu for slice dependencies."""
        slice_deps = self.current_analysis['slice_data']['dependencies']
        
        if not slice_deps:
            print("\nNo slice dependencies found.")
            return
        
        while True:
            print(f"\n{'-'*70}")
            print("SLICE DEPENDENCIES - Select display option:")
            print(f"  1. Show all slices with filter conditions")
            print(f"  2. Group by source table")
            print(f"  3. Return to main menu")
            
            try:
                choice = input("\nEnter your choice (1-3): ").strip()
                
                if choice == '3':
                    break
                elif choice == '1':
                    self.show_all_slice_dependencies(slice_deps)
                elif choice == '2':
                    self.show_slices_by_table(slice_deps)
                else:
                    print("Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
    
    def show_all_slice_dependencies(self, slice_deps):
        """Display all slice dependencies with their filter conditions."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        print(f"\n{'='*70}")
        print(f"SLICES USING {ident} IN FILTER CONDITIONS:")
        print(f"{'='*70}")
        
        for slice_dep in slice_deps:
            slice_name = slice_dep['slice_name']
            source_table = slice_dep['source_table']
            filter_condition = slice_dep['filter_condition']
            
            print(f"\n  {slice_name} (from {source_table}):")
            
            # Format the filter condition for readability
            if len(filter_condition) > 200:
                # Long condition - show first part
                print(f"    Filter: {filter_condition[:200]}...")
            elif '\n' in filter_condition:
                # Multi-line condition
                lines = filter_condition.split('\n')
                print(f"    Filter:")
                for line in lines[:5]:
                    print(f"      {line}")
                if len(lines) > 5:
                    print(f"      ... ({len(lines)-5} more lines)")
            else:
                # Short condition
                print(f"    Filter: {filter_condition}")

    
    def show_slices_by_table(self, slice_deps):
        """Display slice dependencies grouped by source table."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        print(f"\n{'='*70}")
        print(f"SLICES BY SOURCE TABLE FOR {ident}:")
        print(f"{'='*70}")

        # Group by source table
        by_table = defaultdict(list)
        for slice_dep in slice_deps:
            by_table[slice_dep['source_table']].append(slice_dep)

        # Display each table's slices
        for table_name in sorted(by_table.keys()):
            slices = by_table[table_name]
            print(f"\n{table_name} TABLE ({len(slices)} {'slice' if len(slices) == 1 else 'slices'}):")
            print("-" * 40)

            for slice_dep in slices:
                slice_name = slice_dep['slice_name']
                filter_condition = slice_dep['filter_condition']

                print(f"  • {slice_name}")

                # Show condensed filter
                if len(filter_condition) > 100:
                    print(f"      Filter: {filter_condition[:100]}.")
                else:
                    print(f"      Filter: {filter_condition}")


    def show_format_rule_dependencies_detail(self):
        """Show detailed menu for format rule dependencies."""
        rule_deps = self.current_analysis['format_rule_data']['dependencies']
        
        if not rule_deps:
            print("\nNo format rule dependencies found.")
            return
        
        # Pre-calculate which options have content
        formatting_rules = [r for r in rule_deps 
                           if any('formatted by' in u for u in r['usage_types'])]
        condition_rules = [r for r in rule_deps 
                         if any('condition' in u or 'Referenced' in u 
                               for u in r['usage_types'])]
        
        while True:
            print(f"\n{'-'*70}")
            print("FORMAT RULE DEPENDENCIES - Select display option:")
            
            menu_options = {}
            option_num = 1
            
            # Always show "all rules"
            print(f"  {option_num}. Show all rules with details")
            menu_options[option_num] = 'all'
            option_num += 1
            
            # Only show if we have formatting rules
            if formatting_rules:
                print(f"  {option_num}. Show rules formatting this column ({len(formatting_rules)} {'rule' if len(formatting_rules) == 1 else 'rules'})")
                menu_options[option_num] = 'formatting'
                option_num += 1
            
            # Only show if we have condition rules
            if condition_rules:
                print(f"  {option_num}. Show rules using this column in conditions ({len(condition_rules)} {'rule' if len(condition_rules) == 1 else 'rules'})")
                menu_options[option_num] = 'condition'
                option_num += 1
            
            # Always show group by table
            print(f"  {option_num}. Group by source table")
            menu_options[option_num] = 'by_table'
            option_num += 1
            
            # Return option
            print(f"  {option_num}. Return to main menu")
            return_num = option_num
            
            try:
                choice = input(f"\nEnter your choice (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                    
                choice_num = int(choice)
                
                if choice_num in menu_options:
                    option = menu_options[choice_num]

                    ident = self.current_analysis.get('selected_identifier', 'THIS COLUMN')
                    
                    if option == 'all':
                        self.show_all_format_rule_dependencies(rule_deps, f"ALL FORMAT RULES FOR {ident}")
                    elif option == 'formatting':
                        self.show_all_format_rule_dependencies(
                            formatting_rules,
                            f"RULES FORMATTING {ident}"
                        )
                    elif option == 'condition':
                        self.show_all_format_rule_dependencies(
                            condition_rules,
                            f"RULES USING {ident} IN CONDITIONS"
                        )
                    elif option == 'by_table':
                        self.show_format_rules_by_table(rule_deps)
                else:
                    print("Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
    
    def show_all_format_rule_dependencies(self, rule_deps, title="ALL FORMAT RULES"):
        """Display all format rule dependencies with details."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        # Only add identifier if not already in title and title is generic
        if title == "ALL FORMAT RULES":
            title = f"{title} FOR {ident}"

        print(f"\n{'='*70}")
        print(f"{title}")
        print(f"{'='*70}")

        for rule_dep in rule_deps:
            rule_name = rule_dep['rule_name']
            source_table = rule_dep['source_table']
            usage_types = rule_dep['usage_types']
            settings = rule_dep['settings_summary']
            is_disabled = rule_dep['is_disabled']
            condition = rule_dep['condition']

            # Build status indicator
            status = " [DISABLED]" if is_disabled else ""

            print(f"\n  {rule_name} (on {source_table}){status}")

            # Show how it's related
            for usage in usage_types:
                print(f"    • {usage}")

            # Show the formatting applied (if this rule formats the column)
            if any('formatted by' in u for u in usage_types) and settings:
                print(f"    Formatting: {settings}")

            # Show condition if it uses the column
            if any('condition' in u or 'Referenced' in u for u in usage_types) and condition:
                if len(condition) > 150:
                    print(f"    Condition: {condition[:150]}.")
                else:
                    print(f"    Condition: {condition}")

    def show_format_rules_by_table(self, rule_deps):
        """Display format rule dependencies grouped by source table."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        print(f"\n{'='*70}")
        print(f"FORMAT RULES BY TABLE FOR {ident}:")
        print(f"{'='*70}")

        by_table = defaultdict(list)
        for rule_dep in rule_deps:
            by_table[rule_dep['source_table']].append(rule_dep)

        for table_name in sorted(by_table.keys()):
            rules = by_table[table_name]
            print(f"\n{table_name} TABLE ({len(rules)} {'rule' if len(rules) == 1 else 'rules'}):")
            print("-" * 40)
            for rule_dep in rules:
                rule_name = rule_dep['rule_name']
                usage_types = rule_dep['usage_types']
                is_disabled = rule_dep['is_disabled']
                status = " [DISABLED]" if is_disabled else ""
                print(f"  • {rule_name}{status}")
                for usage in usage_types:
                    print(f"      - {usage}")


    def show_action_dependencies_detail(self):
        """Show detailed menu for action dependencies."""
        action_deps = self.current_analysis['action_data']['dependencies']
        
        if not action_deps:
            print("\nNo action dependencies found.")
            return
        
        # Pre-calculate which options have content
        modifying = [a for a in action_deps 
                    if 'Column is edited by this action' in a['usage_types']]
        conditional = [a for a in action_deps 
                      if 'Used in action condition' in a['usage_types']]
        attached = [a for a in action_deps 
                   if 'Action attached to this column' in a['usage_types']]
        user_actions = [a for a in action_deps if not a['is_system']]
        system_actions = [a for a in action_deps if a['is_system']]
        
        while True:
            print(f"\n{'-'*70}")
            print("ACTION DEPENDENCIES - Select display option:")
            
            menu_options = {}
            option_num = 1
            
            # Always show "all actions"
            print(f"  {option_num}. Show all actions with details")
            menu_options[option_num] = 'all'
            option_num += 1
            
            # Only show options that have content
            if modifying:
                print(f"  {option_num}. Show actions that modify this column ({len(modifying)} {'action' if len(modifying) == 1 else 'actions'})")
                menu_options[option_num] = 'modify'
                option_num += 1
                
            if conditional:
                print(f"  {option_num}. Show actions using this column in conditions ({len(conditional)} {'action' if len(conditional) == 1 else 'actions'})")
                menu_options[option_num] = 'condition'
                option_num += 1
                
            if attached:
                print(f"  {option_num}. Show actions attached to this column ({len(attached)} {'action' if len(attached) == 1 else 'actions'})")
                menu_options[option_num] = 'attached'
                option_num += 1
            
            # Always show group by type
            print(f"  {option_num}. Group by action type")
            menu_options[option_num] = 'by_type'
            option_num += 1
            
            if user_actions:
                print(f"  {option_num}. Show only user actions ({len(user_actions)} {'action' if len(user_actions) == 1 else 'actions'})")
                menu_options[option_num] = 'user'
                option_num += 1
                
            if system_actions:
                print(f"  {option_num}. Show only system actions ({len(system_actions)} {'action' if len(system_actions) == 1 else 'actions'})")
                menu_options[option_num] = 'system'
                option_num += 1
            
            # Return option
            print(f"  {option_num}. Return to main menu")
            return_num = option_num
            
            try:
                choice = input(f"\nEnter your choice (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                    
                choice_num = int(choice)
                
                if choice_num in menu_options:
                    option = menu_options[choice_num]
                    
                    if option == 'all':
                        self.show_all_action_dependencies(action_deps)
                    elif option == 'modify':
                        self.show_all_action_dependencies(modifying, 
                                                         "ACTIONS THAT MODIFY THIS COLUMN")
                    elif option == 'condition':
                        self.show_all_action_dependencies(conditional, 
                                                         "ACTIONS USING THIS COLUMN IN CONDITIONS")
                    elif option == 'attached':
                        self.show_all_action_dependencies(attached, 
                                                         "ACTIONS ATTACHED TO THIS COLUMN")
                    elif option == 'by_type':
                        self.show_actions_by_type(action_deps)
                    elif option == 'user':
                        self.show_all_action_dependencies(user_actions, "USER ACTIONS")
                    elif option == 'system':
                        self.show_all_action_dependencies(system_actions, "SYSTEM ACTIONS")
                else:
                    print("Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
    
    def show_all_action_dependencies(self, action_deps, title="ALL ACTIONS"):
        """Display all action dependencies with details."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        # Only add identifier if not already in title and title is generic
        if title == "ALL ACTIONS":
            title = f"{title} FOR {ident}"

        print(f"\n{'='*70}")
        print(f"{title}")
        print(f"{'='*70}")
        
        for action_dep in action_deps:
            action_name = action_dep['action_name']
            source_table = action_dep['source_table']
            action_type = action_dep['action_type']
            usage_types = action_dep['usage_types']
            is_system = action_dep['is_system']
            prominence = action_dep['prominence']
            
            # Build status indicators
            status = " [SYSTEM]" if is_system else ""
            
            print(f"\n  {action_name} (on {source_table}){status}")
            print(f"    Type: {action_type}")
            
            if prominence:
                print(f"    Prominence: {prominence}")

            # Show formulas/conditions for context
            if action_dep.get('to_value'):
                tv = action_dep['to_value']
                print(f"    To value: {tv[:150]}..." if len(tv) > 150 else f"    To value: {tv}")

            if action_dep.get('condition'):
                cond = action_dep['condition']
                print(f"    Condition: {cond[:150]}..." if len(cond) > 150 else f"    Condition: {cond}")
            
            # Show how it's related
            for usage in usage_types:
                print(f"    • {usage}")

    
    def show_actions_by_type(self, action_deps):
        """Display actions grouped by action type."""
        ident = self.current_analysis.get('selected_identifier', '<unknown>')
        print(f"\n{'='*70}")
        print(f"ACTIONS BY TYPE FOR {ident}:")
        print(f"{'='*70}")

        by_type = defaultdict(list)
        for action_dep in action_deps:
            action_type = action_dep.get('action_type') or 'Unknown'
            by_type[action_type].append(action_dep)

        for action_type in sorted(by_type.keys()):
            actions = by_type[action_type]
            print(f"\n{action_type.upper()} ({len(actions)} {'action' if len(actions) == 1 else 'actions'}):")
            print("-" * 40)

            for action_dep in actions:
                action_name = action_dep['action_name']
                is_system = " [SYSTEM]" if action_dep.get('is_system') else ""
                print(f"  • {action_name}{is_system}")

                for usage in action_dep.get('usage_types', []):
                    print(f"      - {usage}")

                if action_dep.get('prominence'):
                    print(f"      Prominence: {action_dep['prominence']}")


    def analyze_view_dependencies(self, selected_column):
        """Analyze which views use the selected column and how."""
        identifier = selected_column['unique_identifier']
        table_name = selected_column['table_name']
        column_name = selected_column['column_name']
        
        view_dependencies = []
        
        for view in self.views_data:
            # Skip unused system views entirely
            if view.get('view_name') in self.unused_system_views:
                continue
            
            usage_types = []
            
            # Check if column is in referenced_columns (primary source of truth)
            ref_cols = view.get('referenced_columns', '').split('|||') if view.get('referenced_columns') else []
            is_referenced = False
            for ref in ref_cols:
                ref = ref.strip()
                if not ref:
                    continue
                if (ref == identifier or 
                    ref == f"{table_name}[{column_name}]" or
                    (view.get('source_table') == table_name and ref in [column_name, f"[{column_name}]"])):
                    is_referenced = True
                    break
            
            if is_referenced:
                # Determine HOW it's used
                
                # Check if displayed (exact match only)
                view_cols = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
                for view_col in view_cols:
                    view_col = view_col.strip()
                    if view_col == column_name:
                        usage_types.append('Displayed as column')
                        break
                
                # Check if in show_if (exact match only)
                show_if = view.get('show_if', '')
                if show_if and (identifier in show_if or 
                               f"[{column_name}]" in show_if or
                               f"{table_name}[{column_name}]" in show_if):
                    usage_types.append('Used in show_if condition')
                
                # Check view configuration for specific uses
                config_str = view.get('view_configuration', '')
                if config_str and config_str != 'Microsoft.AspNetCore.Mvc.ViewFeatures.StringHtmlContent':
                    try:
                        config = json.loads(config_str)
                        
                        # Check for sorting
                        if 'SortBy' in config and config['SortBy']:
                            for sort_item in config['SortBy']:
                                if isinstance(sort_item, dict) and sort_item.get('Column') == column_name:
                                    usage_types.append('Used for sorting')
                                    break
                        
                        # Check for grouping
                        if 'GroupBy' in config and config['GroupBy']:
                            for group_item in config['GroupBy']:
                                if isinstance(group_item, dict) and group_item.get('Column') == column_name:
                                    usage_types.append('Used for grouping')
                                    break
                        
                        # Check deck-specific fields
                        if config.get('PrimaryDeckHeaderColumn') == column_name:
                            usage_types.append('Used as primary deck header')
                        if config.get('SecondaryDeckHeaderColumn') == column_name:
                            usage_types.append('Used as secondary deck header')
                        if config.get('MainDeckImageColumn') == column_name:
                            usage_types.append('Used as deck image')
                        if config.get('DeckSummaryColumn') == column_name:
                            usage_types.append('Used as deck summary')
                            
                    except:
                        pass
                
                # If referenced but no specific use found
                if is_referenced and not usage_types:
                    usage_types.append('Referenced in formulas')
                
                if usage_types:
                    view_dependencies.append({
                        'view_name': view.get('view_name'),
                        'view_type': view.get('view_type', 'unknown'),
                        'is_system': view.get('is_system_view') == 'Yes',
                        'usage_types': usage_types
                    })
        
        return view_dependencies

    def analyze_slice_dependencies(self, selected_column):
        """Analyze which slices use the selected column in their filter conditions."""
        identifier = selected_column['unique_identifier']
        table_name = selected_column['table_name']
        column_name = selected_column['column_name']
        
        slice_dependencies = []
        
        for slice_data in self.slices_data:
            # Keep condition only for display
            filter_condition = slice_data.get('row_filter_condition', '')
            source_table = slice_data.get('source_table')

            # Determine if slice references this column (exact + table-aware via referenced_columns)
            ref_cols = slice_data.get('referenced_columns', '')
            ref_cols = ref_cols.split('|||') if ref_cols else []

            ref_hit = False
            for ref in (r.strip() for r in ref_cols):
                if not ref:
                    continue
                if (
                    ref == identifier
                    or ref == f"{table_name}[{column_name}]"
                    or (source_table == table_name and ref in (column_name, f"[{column_name}]"))
                ):
                    ref_hit = True
                    break

            # Fallback: if referenced_columns is empty, accept only an exact bracketed token in condition
            if not ref_hit and source_table == table_name and filter_condition:
                if f"[{column_name}]" in filter_condition:
                    ref_hit = True

            if ref_hit:
                slice_dependencies.append({
                    'slice_name': slice_data.get('slice_name'),
                    'source_table': source_table,
                    'filter_condition': filter_condition
                })

        return slice_dependencies

    def analyze_format_rule_dependencies(self, selected_column):
        """Analyze which format rules affect or use the selected column."""
        identifier = selected_column['unique_identifier']
        table_name = selected_column['table_name']
        column_name = selected_column['column_name']
        
        format_rule_dependencies = []
        
        for rule in self.format_rules_data:
            usage_types = []
            
            # Check if this column is being formatted by the rule (exact + table-aware)
            formatted_cols = rule.get('formatted_columns', '').split('|||') if rule.get('formatted_columns') else []
            is_formatted = False
            for col in formatted_cols:
                col = col.strip()
                if not col:
                    continue
                if (
                    col == identifier
                    or col == f"{table_name}[{column_name}]"
                    or (rule.get('source_table') == table_name and col == column_name)
                    or (col == f"[{column_name}]" and rule.get('source_table') == table_name)
                ):
                    is_formatted = True
                    usage_types.append('Column is formatted by this rule')
                    break

            # Keep condition only for display
            condition = rule.get('condition', '')

            # Determine if rule references this column (exact + table-aware via referenced_columns)
            ref_cols = rule.get('referenced_columns', '').split('|||') if rule.get('referenced_columns') else []
            ref_hit = False
            for ref in (r.strip() for r in ref_cols):
                if not ref:
                    continue
                if (
                    ref == identifier
                    or ref == f"{table_name}[{column_name}]"
                    or (rule.get('source_table') == table_name and ref in (column_name, f"[{column_name}]"))
                ):
                    ref_hit = True
                    break

            if ref_hit:
                # referenced_columns aggregates actual references in the rule logic
                usage_types.append('Used in rule condition')

            
            if usage_types:
                # Parse the readable settings to show what formatting is applied
                settings_summary = rule.get('readable_settings', '')
                
                format_rule_dependencies.append({
                    'rule_name': rule.get('rule_name'),
                    'source_table': rule.get('source_table'),
                    'condition': condition,
                    'usage_types': usage_types,
                    'settings_summary': settings_summary,
                    'is_disabled': rule.get('is_disabled') == 'Yes'
                })
        
        return format_rule_dependencies

    def analyze_action_dependencies(self, selected_column):
        """Analyze which actions use the selected column."""
        identifier = selected_column['unique_identifier']
        table_name = selected_column['table_name']
        column_name = selected_column['column_name']
        
        action_dependencies = []
        
        for action in self.actions_data:
            usage_types = []
            source_table = action.get('source_table') or action.get('table')
            # Check if column is the target of editing
            if action.get('column_to_edit') == column_name:
                usage_types.append('Column is edited by this action')
            
            # Check if used in "to this value" formula
            to_value = action.get('to_this_value', '')
            condition = action.get('only_if_condition', '')

            # Determine exact/table-aware references via referenced_columns
            ref_cols = action.get('referenced_columns', '')
            ref_cols = ref_cols.split('|||') if ref_cols else []

            ref_hit = False
            for ref in (r.strip() for r in ref_cols):
                if not ref:
                    continue
                if (
                    ref == identifier
                    or ref == f"{table_name}[{column_name}]"
                    or (source_table == table_name and ref in (column_name, f"[{column_name}]"))
                ):
                    ref_hit = True
                    break

            # Attribute usage types based on where the exact token appears
            if ref_hit:
                value_hit = bool(to_value) and f"[{column_name}]" in to_value and source_table == table_name
                cond_hit  = bool(condition) and f"[{column_name}]" in condition and source_table == table_name
                
                # Check if used in input assignments (for grouped actions)
                with_properties = action.get('with_these_properties', '')
                input_hit = bool(with_properties) and f"[{column_name}]" in with_properties

                if value_hit:
                    usage_types.append('Used in value formula')
                if cond_hit:
                    usage_types.append('Used in action condition')
                if input_hit:
                    usage_types.append('Passed as input to referenced action')
                if not value_hit and not cond_hit and not input_hit:
                    usage_types.append('Referenced in action configuration')
            else:
                # Fallback: allow exact bracketed token only if same table
                if to_value and source_table == table_name and f"[{column_name}]" in to_value:
                    usage_types.append('Used in value formula')
                if condition and source_table == table_name and f"[{column_name}]" in condition:
                    usage_types.append('Used in action condition')
            
            # Check if column is used as attachment column
            if action.get('attach_to_column') == column_name:
                usage_types.append('Action attached to this column')
            
            # De-duplicate usage types (preserve order)
            if usage_types:
                seen = set()
                usage_types = [u for u in usage_types if not (u in seen or seen.add(u))]

                action_dependencies.append({
                    'action_name': action.get('action_name'),
                    'source_table': source_table,
                    'action_type': action.get('action_type_plain_english') or action.get('action_type_technical_name') or action.get('action_type'),
                    'prominence': action.get('prominence'),
                    'is_system': (action.get('is_system') == 'Yes'),
                    'to_value': to_value,
                    # ensure the expression shows up in the report
                    'condition': condition,
                    # pass usage types along in case the renderer uses the dict
                    'usage_types': usage_types
                })
        
        return action_dependencies

    def show_reference_details_menu(self, reference_details, category_totals, table_options, category_options):
        """Show interactive menu for viewing reference details."""
        all_options = {}
        all_options.update(table_options)
        all_options.update(category_options)
        view_all_num = len(all_options) + 1
        return_num = view_all_num + 1
        
        while True:
            print(f"\n{'-'*70}")
            print("Select what to view:")
            
            # Table options
            for num, (opt_type, value) in table_options.items():
                print(f"  {num}. All references in {value} table")
                
            # Category options  
            for num, (opt_type, value) in category_options.items():
                cat_display = value.replace('_', ' ').title()
                count = len(category_totals[value])
                print(f"  {num}. All {cat_display} references ({count} total)")
                
            print(f"  {view_all_num}. View all details")
            print(f"  {return_num}. Return to main menu")
            
            try:
                choice = input(f"\nEnter your choice (1-{return_num}): ").strip()
                
                if choice == str(return_num):
                    break
                    
                choice_num = int(choice)
                
                if choice_num == view_all_num:
                    # Show all details
                    self.show_all_references(reference_details)
                elif choice_num in all_options:
                    opt_type, value = all_options[choice_num]
                    if opt_type == 'table':
                        self.show_table_references(value, reference_details[value])
                    else:  # category
                        self.show_category_references(value, category_totals[value])
                else:
                    print("Invalid choice. Please try again.")
                    
            except ValueError:
                print("Please enter a valid number.")
                
            except KeyboardInterrupt:
                print("\nReturning to main menu...")
                break
                
    def show_table_references(self, table_name, categories):
        """Show all references from a specific table."""
        print(f"\n{'='*70}")
        print(f"References from {table_name} table:")
        print(f"{'='*70}")
        
        shown_columns = set()
        for category, columns in sorted(categories.items()):
            for col in columns:
                if col['unique_identifier'] not in shown_columns:
                    self.display_column_reference(col)
                    shown_columns.add(col['unique_identifier'])
                    
    def show_category_references(self, category, columns):
        """Show all references of a specific type."""
        cat_display = category.replace('_', ' ').title()
        print(f"\n{'='*70}")
        print(f"All {cat_display} References:")
        print(f"{'='*70}")
        
        # Group by table
        by_table = defaultdict(list)
        for col in columns:
            by_table[col['table_name']].append(col)
            
        for table_name in sorted(by_table.keys()):
            print(f"\nFrom {table_name}:")
            for col in by_table[table_name]:
                self.display_column_reference(col, show_category=category)
                
    def show_all_references(self, reference_details):
        """Show all references organized by table."""
        print(f"\n{'='*70}")
        print(f"All References (organized by table):")
        print(f"{'='*70}")
        
        for table_name in sorted(reference_details.keys()):
            print(f"\n{'-'*50}")
            print(f"From {table_name}:")
            print(f"{'-'*50}")
            
            shown_columns = set()
            categories = reference_details[table_name]
            
            for category, columns in sorted(categories.items()):
                for col in columns:
                    if col['unique_identifier'] not in shown_columns:
                        self.display_column_reference(col)
                        shown_columns.add(col['unique_identifier'])
                        
    def display_column_reference(self, col, show_category=None):
        """Display detailed information about a referencing column."""
        ref_identifier = col['unique_identifier']
        ref_virtual = " [VIRTUAL]" if col['is_virtual'] == "Yes" else ""
        
        print(f"\n  • {ref_identifier}{ref_virtual}")
        
        if show_category:
            # When showing by category, indicate which field contains the reference
            cat_display = show_category.replace('_', ' ').title()
            print(f"    Reference found in: {cat_display}")
            
        # Show relevant formulas based on what contains references
        if col.get('app_formula'):
            formula = col['app_formula']
            if '\n' in formula and len(formula) > 200:
                # Multi-line formula - show first few lines
                lines = formula.split('\n')
                print(f"    App Formula:")
                for i, line in enumerate(lines[:5]):
                    print(f"      {line}")
                if len(lines) > 5:
                    print(f"      ... ({len(lines)-5} more lines)")
            else:
                print(f"    App Formula: {formula}")
                
        if col.get('display_name'):
            print(f"    Display Name: {col['display_name']}")
            
        if col.get('initial_value'):
            print(f"    Initial Value: {col['initial_value']}")

        if col.get('show_if'):
            print(f"    Show If: {col['show_if']}")
            
        if col.get('valid_if'):
            valid_if = col['valid_if']
            if len(valid_if) > 200:
                print(f"    Valid If: {valid_if[:200]}...")
            else:
                print(f"    Valid If: {valid_if}")
                
        if col.get('required_if'):
            print(f"    Required If: {col['required_if']}")
            
        if col.get('editable_if'):
            print(f"    Editable If: {col['editable_if']}")
            
        if col.get('suggested_values'):
            suggested = col['suggested_values']
            if len(suggested) > 200:
                print(f"    Suggested Values: {suggested[:200]}...")
            else:
                print(f"    Suggested Values: {suggested}")
            
        if col.get('type_qualifier_formulas'):
            tq_formulas = col['type_qualifier_formulas']
            if len(tq_formulas) > 300:
                print(f"    Type Qualifier Formulas: {tq_formulas[:300]}...")
            else:
                print(f"    Type Qualifier Formulas: {tq_formulas}")

    def run(self, return_to_hub=False):
        """Main execution loop."""
        if return_to_hub:
            self.return_to_hub = return_to_hub
        
        print("AppSheet Column Dependency Analyzer")
        print("===================================")
        
        # Load columns data (required)
        if not self.load_columns_data():
            return
        
        # Load other component data (optional but enhances analysis)
        print("\nLoading additional component data:")
        self.load_slices_data()
        self.load_actions_data()
        self.load_views_data()
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
            
        # Main interaction loop
        while True:
            print("\n" + "="*70)
            search_term = input("Enter column name or partial name to search (or 'quit' to exit): ").strip()
            
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
            matches = self.search_columns(search_term)
            
            # Display matches
            displayed_matches = self.display_matches(matches)
            
            if displayed_matches:
                # Get user selection
                selected = self.get_user_selection(displayed_matches)
                
                if selected:
                    # Analyze dependencies
                    self.analyze_column_dependencies(selected)
                    
                    input("\nPress Enter to continue...")


def main():
    """Main entry point."""
    # Check if a path was provided
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Create and run analyzer
    analyzer = ColumnDependencyAnalyzer(base_path)
    analyzer.run()


if __name__ == "__main__":
    main()
