#!/usr/bin/env python3
"""
AppSheet Views Parser
Extracts view definitions from AppSheet HTML documentation and outputs to CSV.
Enhanced with unified referenced_columns field for dependency tracking.
"""

import re
import csv
import json
import os
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
import html
from base_parser import BaseParser

class ViewsParser(BaseParser):
    def __init__(self, html_path=None, html_string=None, soup=None, debug_mode=False):
        """Initialize the views parser."""
        super().__init__(html_path, html_string, soup, debug_mode)
        self.views = []
        self.views_data = []
        self.view_type_map = {}
        self.system_view_names = set()
        self.slice_mapping = {}
        self.view_to_table_map = {}
        self.view_categories = {}
        self.actions_mapping = {}
        self.html_path = html_path
        self.slice_columns_map = {}  # slice -> list of included columns
        self.table_columns_map = defaultdict(list)  # table -> list of all columns
        self.table_hidden_columns_map = defaultdict(list)  # table -> list of hidden columns
        self.table_actions_map = defaultdict(list)  # table -> list of all actions for that table
        self.slice_data_map = {}  # slice -> complete slice row data (includes slice_actions)

    def get_output_filename(self, input_filename):
        """Return the output filename for views data."""
        return "appsheet_views.csv"
    
    def clean_text(self, text):
        """Clean HTML entities and formatting from text."""
        if not text:
            return ""
        
        # Unescape HTML entities
        text = html.unescape(text)
        
        # Remove non-breaking spaces
        text = text.replace('\xa0', ' ')
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def parse_views_file(self, file_path):
        """Parse a single views text file and return view data."""
        views_data = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Parse the text file
            current_category = None
            current_ref_parent = None
            
            lines = content.split('\n')
            i = 0
            
            while i < len(lines):
                line = lines[i].strip()
                
                
                # Footer / non-content guards to avoid parsing preview/footer blocks
                if line in ('Edit', 'open_in_new', 'Preview app as', 'Apply'):
                    current_category = None
                    i += 1
                    continue
                if line.startswith(('View:', 'Table:', '|')):
                    i += 1
                    continue

# Check for category headers
                if line.endswith('Views') and not line.startswith('Data:'):
                    if 'primary' in line.lower() or 'bottom bar' in line.lower():
                        current_category = 'primary'
                        current_ref_parent = None
                    elif 'menu' in line.lower():
                        current_category = 'menu'
                        current_ref_parent = None
                    elif 'ref' in line.lower():
                        current_category = 'ref'
                        current_ref_parent = None
                    elif 'other' in line.lower():
                        current_category = 'other'
                        current_ref_parent = None
                    i += 1
                    continue
                
                # In Ref Views section, check for parent table/slice headers
                if current_category == 'ref' and line and not any(x in line for x in ['Data:', 'Type:', 'first', 'middle', 'next', 'later', 'last']) and not '(' in line:
                    # Check if this is a parent header by looking ahead
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        
                        # If next line is empty or is a view name (no Data/Type), this is a parent header
                        if not next_line or (next_line and not any(x in next_line for x in ['Data:', 'Type:', 'first', 'middle', 'next', 'later', 'last'])):
                            # This is a parent table/slice header
                            current_ref_parent = line
                            i += 1
                            continue
                
                # Parse view entries
                if line and not line.endswith('Views') and current_category:
                    # Skip empty lines
                    if not line.strip():
                        i += 1
                        continue
                        
                    view_name = line
                    position = None
                    data_source = None
                    view_type = None
                    
                    # Check next line for position or data info
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        
                        # Check if next line contains position+data combo (narrow screen format)
                        if 'Data:' in next_line and not next_line.startswith('Data:'):
                            # Extract position (everything before 'Data:')
                            position = next_line.split('Data:')[0].strip()
                            
                            # Check if Type is also on this line
                            if 'Type:' in next_line:
                                # Everything is on one line
                                temp_after_data = next_line.split('Data:')[1]
                                data_source = temp_after_data.split('Type:')[0].strip()
                                view_type = temp_after_data.split('Type:')[1].strip()
                                i += 1
                            else:
                                # Data is here, but Type might be on the next line
                                data_source = next_line.split('Data:')[1].strip()
                                i += 1
                                
                                # Look for Type on the following line
                                if i + 1 < len(lines):
                                    type_line = lines[i + 1].strip()
                                    if type_line.startswith('Type:'):
                                        view_type = type_line.split('Type:')[1].strip()
                                        i += 1
                        
                        # Check for wide screen format (position on separate line)
                        elif any(pos in next_line for pos in ['first', 'middle', 'next', 'later', 'last']) and 'Data:' not in next_line:
                            position = next_line
                            i += 1
                            
                            # Look for Data line
                            if i + 1 < len(lines):
                                data_line = lines[i + 1].strip()
                                if data_line.startswith('Data:'):
                                    # Check if Type is on same line
                                    if 'Type:' in data_line:
                                        temp = data_line.split('Data:')[1]
                                        data_source = temp.split('Type:')[0].strip()
                                        view_type = temp.split('Type:')[1].strip()
                                        i += 1
                                    else:
                                        # Just Data on this line
                                        data_source = data_line.split('Data:')[1].strip()
                                        i += 1
                                        
                                        # Look for Type line
                                        if i + 1 < len(lines):
                                            type_line = lines[i + 1].strip()
                                            if type_line.startswith('Type:'):
                                                view_type = type_line.split('Type:')[1].strip()
                                                i += 1
                        
                        # Check for direct Data line (no position)
                        elif next_line.startswith('Data:'):
                            # Check if Type is on same line
                            if 'Type:' in next_line:
                                temp = next_line.split('Data:')[1]
                                data_source = temp.split('Type:')[0].strip()
                                view_type = temp.split('Type:')[1].strip()
                            else:
                                data_source = next_line.split('Data:')[1].strip()
                                # Look for Type on next line
                                if i + 2 < len(lines):
                                    type_line = lines[i + 2].strip()
                                    if type_line.startswith('Type:'):
                                        view_type = type_line.split('Type:')[1].strip()
                                        i += 1
                            i += 1
                        
                        # Check for Type line only (dashboards)
                        elif next_line.startswith('Type:'):
                            view_type = next_line.split('Type:')[1].strip()
                            i += 1
                    
                    # Store the mapping
                    if view_name:
                        views_data[view_name] = {
                            'data_source': data_source,
                            'view_type': view_type,
                            'category': current_category,
                            'position': position,
                            'ref_parent': current_ref_parent if current_category == 'ref' else None
                        }
                
                i += 1
            
            return views_data
            
        except Exception as e:
            print(f"  ❌ Error reading {file_path}: {str(e)}")
            return {}
    
    def load_views_text_mapping(self, html_view_names=None):
        """
        Load view-to-table mappings from views1.txt and views2.txt files.
        Automatically detect which file has system views by comparing counts.
        """
        # Determine where views files should be located
        # First, check if we have an HTML path set
        if hasattr(self, 'html_path') and self.html_path:
            html_dir = os.path.dirname(os.path.abspath(self.html_path))
        # If not, but we have soup loaded, try to find the original path
        elif hasattr(self, 'soup') and self.soup:
            # Check if we stored the original path during initialization
            # This is a fallback - the html_path should be set
            print("  ⚠️  Warning: html_path not set, using current directory")
            html_dir = os.getcwd()
        else:
            html_dir = os.getcwd()
        
        views1_path = os.path.join(html_dir, 'views1.txt')
        views2_path = os.path.join(html_dir, 'views2.txt')
        
        # Check if files exist
        views1_exists = os.path.exists(views1_path)
        views2_exists = os.path.exists(views2_path)
        
        if not views1_exists and not views2_exists:
            print(f"\n  ⚠️  IMPORTANT: No views files found")
            print(f"\n  In the legacy mode of the AppSheet editor, go to UX > Views")
            print(f"  1. With 'Show system views' checked, copy all text and save as 'views1.txt'")
            print(f"  2. With 'Show system views' unchecked, copy all text and save as 'views2.txt'")
            print(f"  3. Save both files in: {html_dir}")
            
            while True:
                print(f"\n  When you are ready, respond with the appropriate number:")
                print(f"    1) I've put both views files in the folder")
                print(f"    2) Continue without views files (table mappings will be missing)")
                print(f"    3) Abort")
                
                response = input("\n  Choice (1/2/3): ").strip()
                
                if response == '1':
                    # Check if files now exist
                    if os.path.exists(views1_path) and os.path.exists(views2_path):
                        print("\n  ✅ Found both views files! Continuing...")
                        break
                    else:
                        missing = []
                        if not os.path.exists(views1_path):
                            missing.append("views1.txt")
                        if not os.path.exists(views2_path):
                            missing.append("views2.txt")
                        print(f"\n  ❌ Still missing: {', '.join(missing)}")
                        continue
                        
                elif response == '2':
                    print("\n  Continuing without table mappings...")
                    return False
                    
                elif response == '3':
                    print("\n  Aborting. Please add views files and re-run.")
                    sys.exit(0)
                else:
                    print("\n  Invalid choice. Please enter 1, 2, or 3.")
        
        elif views1_exists and not views2_exists:
            print(f"\n  ⚠️  Found views1.txt but missing views2.txt")
            print(f"  For system view detection, both files are needed.")
            print(f"  Continuing with views1.txt only (no system view identification)...")
            # Load just views1.txt
            views1_data = self.parse_views_file(views1_path)
            self.update_view_mappings(views1_data)
            print(f"  ✅ Loaded {len(views1_data)} view mappings from views1.txt")
            return True
            
        elif not views1_exists and views2_exists:
            print(f"\n  ⚠️  Found views2.txt but missing views1.txt")
            print(f"  For system view detection, both files are needed.")
            print(f"  Continuing with views2.txt only (no system view identification)...")
            # Load just views2.txt
            views2_data = self.parse_views_file(views2_path)
            self.update_view_mappings(views2_data)
            print(f"  ✅ Loaded {len(views2_data)} view mappings from views2.txt")
            return True
        
        # Both files exist - proceed with comparison
        print(f"  📂 Loading view mappings from views1.txt and views2.txt")
        
        views1_data = self.parse_views_file(views1_path)
        views2_data = self.parse_views_file(views2_path)
        
        views1_count = len(views1_data)
        views2_count = len(views2_data)
        
        print(f"  📊 Found views1.txt ({views1_count} views) and views2.txt ({views2_count} views)")
        
        # Determine which file has system views
        if views1_count > views2_count:
            # views1.txt has system views
            print(f"  ✅ Identified views1.txt as containing system views")
            with_system = views1_data
            without_system = views2_data
        elif views2_count > views1_count:
            # views2.txt has system views
            print(f"  ✅ Identified views2.txt as containing system views")
            with_system = views2_data
            without_system = views1_data
        else:
            # Same count - can't determine system views
            print(f"\n  ⚠️  WARNING: Both files contain the same number of views ({views1_count})")
            print(f"  Cannot automatically identify system views.")
            
            # Just use views1 data
            self.update_view_mappings(views1_data)
            print(f"  ✅ Loaded {len(views1_data)} views")
            return True
        
        # Identify system views
        system_view_names = set(with_system.keys()) - set(without_system.keys())
        self.system_views = system_view_names
        
        print(f"  ✅ Found {len(system_view_names)} system views and {len(without_system)} user views")
        
        # Use the complete data (with system views)
        self.update_view_mappings(with_system)
        
        # Store view type mappings
        for view_name, info in with_system.items():
            if info.get('view_type'):
                self.view_type_map[view_name] = info['view_type']
        
        return True
    
    def update_view_mappings(self, views_data):
        """Update the view mappings with data from parsed file."""
        for view_name, info in views_data.items():
            self.view_to_table_map[view_name] = info
            self.view_categories[view_name] = info.get('category', '')
    
    def extract_view_columns(self, columns_str: str, context_table: str) -> List[str]:
        """
        Extract view columns and return as list.
        This preserves the original format for the view_columns field.
        """
        if not columns_str or columns_str == 'Microsoft.AspNetCore.Mvc.ViewFeatures.StringHtmlContent':
            return []
        
        # Split by comma and clean each column
        columns = [col.strip() for col in columns_str.split(',') if col.strip()]
        
        # Filter out special indicators
        valid_columns = []
        for col in columns:
            if not (col.startswith('**') and col.endswith('**')):
                valid_columns.append(col)
                
        return valid_columns
    
    def build_column_references(self, columns: List[str], context_table: str) -> List[Dict]:
        """Build reference dictionaries for view columns."""
        references = []
        
        if not context_table or context_table == 'Microsoft.AspNetCore.Mvc.ViewFeatures.StringHtmlContent':
            return references
            
        for col in columns:
            if col and not (col.startswith('**') and col.endswith('**')):
                references.append({
                    'type': 'view_column',
                    'table': context_table,
                    'column': col,
                    'raw': f"{context_table}[{col}]"
                })
                
        return references
    
    def parse_view_configuration(self, config_str: str, context_table: str) -> List[Dict]:
        """Extract column references from view configuration JSON."""
        references = []
        
        if not config_str or config_str == 'Microsoft.AspNetCore.Mvc.ViewFeatures.StringHtmlContent':
            return references
        
        try:
            # First extract any references using BaseParser's method
            refs = self.extract_references_from_json(config_str, context_table)
            references.extend(refs)
            
            # Also do specific parsing for known view configuration fields
            config = json.loads(config_str)
            
            # Fields that contain column names
            column_fields = [
                'MainDeckImageColumn',
                'PrimaryDeckHeaderColumn', 
                'SecondaryDeckHeaderColumn',
                'DeckSummaryColumn',
                'DeckNestedTableColumn',
                'MainSlideshowImageColumn',
                'DetailContentColumn',
                'PrimarySortColumn'
            ]
            
            for field in column_fields:
                if field in config and config[field]:
                    value = config[field]
                    if isinstance(value, str) and value != '**none**' and context_table:
                        references.append({
                            'type': 'config_column',
                            'table': context_table,
                            'column': value,
                            'raw': f"{context_table}[{value}]",
                            'json_path': field
                        })
            
            # Handle lists of columns
            list_fields = ['ColumnOrder', 'HeaderColumns', 'QuickEditColumns']
            for field in list_fields:
                if field in config and isinstance(config[field], list):
                    for col in config[field]:
                        if isinstance(col, str) and col and col != '**none**' and context_table:
                            references.append({
                                'type': 'config_column',
                                'table': context_table,
                                'column': col,
                                'raw': f"{context_table}[{col}]",
                                'json_path': field
                            })
            
            # Handle SortBy and GroupBy (list of dicts)
            for field in ['SortBy', 'GroupBy']:
                if field in config and isinstance(config[field], list):
                    for item in config[field]:
                        if isinstance(item, dict) and 'Column' in item and context_table:
                            col = item['Column']
                            if col and col != '**none**':
                                references.append({
                                    'type': 'config_column',
                                    'table': context_table,
                                    'column': col,
                                    'raw': f"{context_table}[{col}]",
                                    'json_path': field
                                })
                                
        except (json.JSONDecodeError, TypeError):
            # If not valid JSON, references were already extracted above
            pass
        
        return references
    
    def load_slice_mapping(self):
        """Load slice to source table mapping and slice columns from CSV file."""
        slice_csv_path = Path("appsheet_slices.csv")
        
        if slice_csv_path.exists():
            print(f"  📂 Loading slice mapping from {slice_csv_path.name}")
            try:
                with open(slice_csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        slice_name = row.get('slice_name', '').strip()
                        source_table = row.get('source_table', '').strip()
                        slice_columns = row.get('slice_columns', '').strip()
                        
                        if slice_name and source_table:
                            self.slice_mapping[slice_name] = source_table
                            # Also update BaseParser's mapping
                            self.slice_to_table_map[slice_name] = source_table
                            
                            # Parse slice columns if available
                            if slice_columns:
                                # Assuming columns are separated by |||
                                columns = [col.strip() for col in slice_columns.split('|||') if col.strip()]
                                self.slice_columns_map[slice_name] = columns
                             
                            # Store the entire row data for slice actions
                            self.slice_data_map[slice_name] = row                          

                print(f"  ✅ Loaded {len(self.slice_mapping)} slice mappings")
            except Exception as e:
                print(f"  ⚠️  Warning: Could not load slice mapping: {e}")    

    def load_actions_mapping(self):
        """Load action mapping from CSV file if available."""
        actions_csv_path = Path("appsheet_actions.csv")
        
        if actions_csv_path.exists():
            print(f"  📂 Loading actions mapping from {actions_csv_path.name}")
            try:
                with open(actions_csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        action_name = row.get('action_name', '').strip()
                        if action_name:
                            self.actions_mapping[action_name] = row
                            
                print(f"  ✅ Loaded {len(self.actions_mapping)} action mappings")
            except Exception as e:
                print(f"  ⚠️  Warning: Could not load actions mapping: {e}") 

    def load_columns_data(self):
        """Load column data from CSV file if available."""
        columns_csv_path = Path("appsheet_columns.csv")
        
        if columns_csv_path.exists():
            print(f"  📂 Loading columns data from {columns_csv_path.name}")
            try:
                # Initialize data structures
                self.table_columns_map = defaultdict(list)  # table -> list of all columns
                self.table_hidden_columns_map = defaultdict(list)  # table -> list of hidden columns
                
                with open(columns_csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        table_name = row.get('table_name', '').strip()
                        column_name = row.get('column_name', '').strip()
                        is_hidden = row.get('hidden', '').strip().lower() == 'yes'
                        
                        if table_name and column_name:
                            # Add to all columns for this table
                            self.table_columns_map[table_name].append(column_name)
                            
                            # Add to hidden columns if marked as hidden
                            if is_hidden:
                                self.table_hidden_columns_map[table_name].append(column_name)
                            
                print(f"  ✅ Loaded column data for {len(self.table_columns_map)} tables")
            except Exception as e:
                print(f"  ⚠️  Warning: Could not load columns data: {e}")
        else:
            print(f"  ⚠️  Columns data file not found: {columns_csv_path}")

    def load_actions_data(self):
        """Load action data from CSV file if available."""
        actions_csv_path = Path("appsheet_actions.csv")
        
        if actions_csv_path.exists():
            print(f"  📂 Loading actions data from {actions_csv_path.name}")
            try:
                # Initialize data structure
                self.table_actions_map = defaultdict(list)  # table -> list of all actions
                
                with open(actions_csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        table_name = row.get('source_table', '').strip()
                        action_name = row.get('action_name', '').strip()
                        
                        if table_name and action_name:
                            # Add action to the table's action list
                            self.table_actions_map[table_name].append(action_name)
                            
                print(f"  ✅ Loaded action data for {len(self.table_actions_map)} tables")
            except Exception as e:
                print(f"  ⚠️  Warning: Could not load actions data: {e}")
        else:
            print(f"  ⚠️  Actions data file not found: {actions_csv_path}")

    def parse_view_block(self, view_element, view_name):
        """Parse a single view block and extract all information."""
        info = {
            'view_name': view_name,
            'category': '',
            'data_source': '',
            'source_table': '',
            'view_type': '',
            'is_system_view': 'No',
            'position': '',
            'ref_parent': '',
            'referenced_columns': '',
            'referenced_actions': '',
            'event_actions': '',
            'dashboard_view_entries': '',
            'show_if': '',
            'display_mode': '',
            'view_columns': '',  # Keep original format for display
            'available_columns': '',  # All columns accessible to this view
            'hidden_columns': '',    # Columns marked as hidden
            'available_actions': '',     # Actions available through the slice (for Automatic mode)
            'action_display_mode': '',  # Automatic or Manual
            'icon': '',
            'created_by': '',
            'action_type': '',
            'html_position': '',
            'show_action_bar': '',
            'use_card_layout': '',
            'view_configuration': '',
        }
        
        # Get mapping from views text if available
        text_mapping = self.view_to_table_map.get(view_name, {})
        if text_mapping:
            info['data_source'] = text_mapping.get('data_source', '')
            info['category'] = text_mapping.get('category', '')
            info['position'] = text_mapping.get('position', '')
            info['view_type'] = text_mapping.get('view_type', '')
            
            # Add ref parent if this is a ref view
            if text_mapping.get('ref_parent'):
                info['ref_parent'] = text_mapping['ref_parent']
            
            # Resolve data source if it's a slice
            if info['data_source']:
                actual_table = self.resolve_table_reference(info['data_source'])
                info['source_table'] = actual_table
        
        # Check if this is a system view
        if view_name in self.system_views:
            info['is_system_view'] = 'Yes'
        elif self.system_views:  # We have system view data
            info['is_system_view'] = 'No'
        else:  # No system view data available
            info['is_system_view'] = 'Unknown'
        
        # Collect all references
        all_references = []
        
        # Extract data from table rows
        # IMPORTANT: Find the table that immediately follows this specific view header
        # to avoid mixing data between views
        tables = view_element.find_all('table', class_='react-bridge-group')
        
        # Find the correct table for this view
        correct_table = None
        for table in tables:
            # Check if this table's data-index matches our view position
            # or if it's the first table after our view header
            if table:
                correct_table = table
                break
        
        if correct_table:
            for row in correct_table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) == 2:
                    label_cell = cells[0]
                    value_cell = cells[1]
                    
                    # Get the label text
                    label_text = label_cell.get_text(strip=True).lower()
                    
                    # For value, get the actual text content, not the object type
                    value = value_cell.get_text(separator='\n', strip=True)
                    
                    # Clean up any StringHtmlContent references
                    if 'StringHtmlContent' in value:
                        value = ''
                    
                    # Map common fields
                    if 'view name' in label_text:
                        # Already have this from header
                        pass
                    elif 'created by' in label_text:
                        info['created_by'] = value
                    elif 'view type' in label_text and 'action' not in label_text:
                        if not info['view_type']:  # Don't override text mapping
                            info['view_type'] = value
                    elif 'actiontype' in label_text.lower():
                        info['action_type'] = value
                    elif 'position' in label_text:
                        info['html_position'] = value
                    elif 'view configuration' in label_text or 'settings' in label_text:
                        # Make sure we get the actual JSON, not a repeated value
                        actual_value = value_cell.get_text(strip=True)
                        if actual_value and 'StringHtmlContent' not in actual_value:
                            info['view_configuration'] = actual_value
                            # Extract references from configuration
                            if info['source_table']:
                                config_refs = self.parse_view_configuration(actual_value, info['source_table'])
                                all_references.extend(config_refs)
                        else:
                            info['view_configuration'] = value
                    elif 'icon' in label_text:
                        # Extract icon class
                        icon_element = value_cell.find('i')
                        if icon_element and icon_element.get('class'):
                            info['icon'] = ' '.join(icon_element['class'])
                        else:
                            info['icon'] = value
                    elif 'show if' in label_text:
                        # Get the actual show_if value for this specific view
                        actual_value = value_cell.get_text(strip=True)
                        if actual_value and 'StringHtmlContent' not in actual_value:
                            info['show_if'] = actual_value
                            # Extract column references from formulas
                            if actual_value and info['source_table']:
                                refs = self.extract_references_from_text(actual_value, info['source_table'])
                                all_references.extend(refs)
                        else:
                            info['show_if'] = value        
        # Extract additional information from view configuration JSON
        if info['view_configuration'] and info['view_configuration'] != 'Microsoft.AspNetCore.Mvc.ViewFeatures.StringHtmlContent':
            try:
                config = json.loads(info['view_configuration'])
                
                # Extract display settings
                if 'DisplayMode' in config:
                    info['display_mode'] = config['DisplayMode']
                if 'UseCardLayout' in config:
                    info['use_card_layout'] = str(config['UseCardLayout'])
                if 'ShowActionBar' in config:
                    info['show_action_bar'] = str(config['ShowActionBar'])
                
                # Extract view columns
                view_columns = []
                
                # For deck views, extract displayed columns from deck-specific fields
                if info['view_type'] == 'deck':
                    deck_columns = []
                    
                    # Check each deck-specific column field
                    deck_fields = ['PrimaryDeckHeaderColumn', 'SecondaryDeckHeaderColumn', 
                                   'MainDeckImageColumn', 'DeckSummaryColumn']
                    
                    for field in deck_fields:
                        if field in config and config[field] and config[field] != '**none**':
                            deck_columns.append(config[field])
                    
                    view_columns = deck_columns
                    
                # For other view types, use ColumnOrder
                elif 'ColumnOrder' in config and isinstance(config['ColumnOrder'], list):
                    view_columns = [col for col in config['ColumnOrder'] if col and col != '**none**']
                
                if view_columns:
                    info['view_columns'] = '|||'.join(view_columns)
                    # Build references for dependency tracking
                    if info['source_table']:
                        column_refs = self.build_column_references(view_columns, info['source_table'])
                        all_references.extend(column_refs)
                
                # Extract dashboard view entries
                if 'ViewEntries' in config and config['ViewEntries']:
                    view_entries = []
                    for entry in config['ViewEntries']:
                        if 'ViewName' in entry:
                            view_entries.append(entry['ViewName'])
                    if view_entries:
                        info['dashboard_view_entries'] = '|||'.join(view_entries)

                # Determine action display mode
                if 'ActionBarEntries' in config:
                    # If ActionBarEntries exists and has specific actions, it's Manual mode
                    if config['ActionBarEntries'] and len(config['ActionBarEntries']) > 0:
                        info['action_display_mode'] = 'Manual'
                    else:
                        info['action_display_mode'] = 'Automatic'
                elif 'ShowActionBar' in config and config['ShowActionBar']:
                    # If ShowActionBar is true but no ActionBarEntries, it's Automatic
                    info['action_display_mode'] = 'Automatic' 

                # Extract action references
                action_refs = []
                if 'ActionColumns' in config and config['ActionColumns']:
                    action_refs.extend(config['ActionColumns'])
                if 'ActionBarEntries' in config and config['ActionBarEntries']:
                    action_refs.extend(config['ActionBarEntries'])
                if 'Events' in config and config['Events']:
                    for event in config['Events']:
                        if event.get('EventAction') not in ['**auto**','**none**', None]:
                            action_refs.append(event['EventAction'])
                if action_refs:
                    info['referenced_actions'] = '|||'.join(action_refs)

                # Extract event actions separately
                event_actions = []
                if 'Events' in config and config['Events']:
                    for event in config['Events']:
                        event_action = event.get('EventAction', '')
                        if event_action and event_action not in ['**auto**', '**none**', None, '']:
                            event_actions.append(event_action)
                if event_actions:
                    info['event_actions'] = '|||'.join(event_actions)
                    
            except (json.JSONDecodeError, TypeError):
                # Already extracted references above
                pass
        
        # Determine category if not set
        if not info['category']:
            if info['is_system_view'] == 'Yes':
                info['category'] = 'system'
            elif info['position'] in ['first', 'middle', 'next', 'later', 'last']:
                info['category'] = 'primary'
            elif view_name.upper().endswith(('_FORM', '_DETAIL', '_INLINE')):
                info['category'] = 'ref'
            else:
                info['category'] = 'menu'
        
        # Populate available_columns and hidden_columns
        if info['source_table']:
            # Get available columns based on whether view uses a table or slice
            if info['data_source'] in self.slice_columns_map:
                # View uses a slice - only slice columns are available
                available_cols = self.slice_columns_map.get(info['data_source'], [])
            else:
                # View uses a table directly - all table columns are available
                available_cols = self.table_columns_map.get(info['source_table'], [])

            # Get available actions based on whether view uses a table or slice
            if info['data_source'] in self.slice_mapping:
                # View uses a slice - need to get actions from slice_actions column
                if info['data_source'] in self.slice_data_map:
                    slice_data = self.slice_data_map.get(info['data_source'], {})
                    actions_str = slice_data.get('slice_actions', '')
                    if actions_str:
                        # Actions are ||| delimited in the slice CSV
                        available_actions = [a.strip() for a in actions_str.split('|||') if a.strip()]
                        
                        # Check if slice uses auto-assign (shows as **auto** in the data)
                        if len(available_actions) == 1 and available_actions[0] == '**auto**':
                            # Replace with all table actions
                            available_actions = self.table_actions_map.get(info['source_table'], [])
                            if self.debug_mode:
                                print(f"    Expanding **auto** to {len(available_actions)} table actions")
                    else:
                        available_actions = []
                else:
                    available_actions = []
            else:
                # View uses a table directly - all table actions are available
                available_actions = self.table_actions_map.get(info['source_table'], [])

            # Format as ||| delimited string
            info['available_actions'] = '|||'.join(available_actions) if available_actions else ''
            
            if self.debug_mode and available_actions:
                print(f"  DEBUG: View '{view_name}' - {len(available_actions)} available actions")
                if info['data_source'] in self.slice_mapping:
                    print(f"    Using slice '{info['data_source']}' actions")
                    
            # Get hidden columns for the source table
            hidden_cols = self.table_hidden_columns_map.get(info['source_table'], [])
            
            # Format as ||| delimited strings
            info['available_columns'] = '|||'.join(available_cols) if available_cols else ''
            info['hidden_columns'] = '|||'.join(hidden_cols) if hidden_cols else ''
               
            if self.debug_mode and available_cols:
                print(f"  DEBUG: View '{view_name}' - {len(available_cols)} available columns, {len(hidden_cols)} hidden")
                if info['data_source'] in self.slice_columns_map:
                    print(f"    Using slice '{info['data_source']}' columns")

        # Build absolute references using BaseParser's method
        if all_references:
            absolute_refs = self.build_absolute_references(all_references)
            info['referenced_columns'] = '|||'.join(absolute_refs)
            
            if self.debug_mode:
                print(f"  DEBUG: Total {len(absolute_refs)} unique column references for view '{view_name}'")
        
        return info
    
    def parse(self, html_path=None):
        """Parse the HTML file and extract all views."""
        if html_path:
            # Store the absolute path before any directory changes
            self.html_path = os.path.abspath(html_path)
            self.load_html_from_file(self.html_path)
        print(f"👁️  Extracting views...")
        
        # Load slice mapping
        self.load_slice_mapping()
        
        # Load actions mapping if available
        self.load_actions_mapping()

        # Load columns data
        self.load_columns_data()

        # Load actions data
        self.load_actions_data()
        
        # Find all view headers
        view_headers = self.soup.find_all('h5', id=lambda x: x and x.startswith('view'))
        
        # First pass: collect all view names from headers
        html_view_names = set()
        valid_view_headers = []
        
        for view_header in view_headers:
            # Get the text content properly
            label_elem = view_header.find('label')
            if label_elem and 'View name' in label_elem.get_text():
                # This is a view, not a format rule
                header_text = view_header.get_text(strip=True)
                view_name = header_text.replace('View name', '').strip()
                
                # Skip if this looks like a formula fragment
                if view_name and not any(char in view_name for char in ['=', '[', ']']):
                    valid_view_headers.append(view_header)
                    html_view_names.add(view_name)
                elif self.debug_mode:
                    print(f"  DEBUG: Skipping invalid view name: {view_name}")
        
        if not valid_view_headers:
            print("  ℹ️  No views found in this app")
            return self.views_data
        
        print(f"  📊 Found {len(valid_view_headers)} view headers in HTML")
        
        # Load view mappings from text files
        self.load_views_text_mapping(html_view_names=html_view_names)
        
        # Second pass: parse view details
        self.views_data = []
        for view_header in valid_view_headers:
            # Get view name
            header_text = view_header.get_text(strip=True)
            view_name = header_text.replace('View name', '').strip()
            
            # Get the next sibling table that belongs to this view
            # This ensures we're parsing the correct table for each view
            view_table = None
            for sibling in view_header.find_next_siblings():
                if sibling.name == 'table' and 'react-bridge-group' in sibling.get('class', []):
                    view_table = sibling
                    break
                elif sibling.name == 'h5':  # Stop if we hit another view header
                    break
            
            # Create a temporary container with just this view's elements
            class ViewContainer:
                def __init__(self, header, table):
                    self.header = header
                    self.table = table
                
                def find_all(self, *args, **kwargs):
                    if args[0] == 'table' and self.table:
                        return [self.table]
                    return []
                
                def find(self, *args, **kwargs):
                    if args[0] == 'table' and self.table:
                        return self.table
                    return None
            
            view_section = ViewContainer(view_header, view_table)
            
            # Parse the view block
            view_info = self.parse_view_block(view_section, view_name)            
            if view_info:
                self.views_data.append(view_info)
                if view_header.get('id'):
                    self.mark_element_processed(view_header.get('id'))
        
        # Assign to self.views for compatibility
        self.views = self.views_data
        
        print(f"  ✓ Found {len(self.views)} views")
        
        # Print summary statistics
        self.print_summary()
        
        return self.views

    def print_summary(self):
        """Print summary statistics about parsed views."""
        if not self.views:
            return
            
        view_counts = defaultdict(int)
        category_counts = defaultdict(int)
        system_counts = {'System views': 0, 'User views': 0, 'Unknown': 0}
        missing_mappings = []
        
        for view in self.views:
            # Count by type
            view_type = view.get('view_type', 'unknown')
            view_counts[view_type] += 1
            
            # Count by category
            category = view.get('category', 'unknown')
            category_counts[category] += 1
            
            # Count by system status
            if view.get('is_system_view') == 'Yes':
                system_counts['System views'] += 1
            elif view.get('is_system_view') == 'No':
                system_counts['User views'] += 1
            else:
                system_counts['Unknown'] += 1
            
            # Track missing mappings
            if not view.get('data_source') and view.get('view_type') != 'dashboard':
                missing_mappings.append(view)
        
        # Print summaries
        print("\n  📊 Views Summary:")
        
        # Category summary
        for category in ['primary', 'menu', 'ref', 'system', 'other']:
            if category in category_counts:
                print(f"    {category.capitalize()}: {category_counts[category]} views")
        
        # System status summary
        print("\n    System status:")
        if system_counts['System views'] > 0 or system_counts['User views'] > 0:
            print(f"      System views: {system_counts['System views']}")
            print(f"      User views: {system_counts['User views']}")
        if system_counts['Unknown'] > 0:
            print(f"      Unknown: {system_counts['Unknown']}")
        
        # Type summary
        print("\n    By type:")
        for vtype, count in sorted(view_counts.items()):
            if vtype != 'unknown':
                print(f"      {vtype}: {count}")
        if 'unknown' in view_counts:
            print(f"      unknown: {view_counts['unknown']}")
        
        # Warning about missing mappings
        if missing_mappings:
            print(f"\n    ⚠️  {len(missing_mappings)} non-dashboard view{'s' if len(missing_mappings)>1 else ''} missing table/slice mappings:")
            for v in missing_mappings[:5]:
                print(f"       - {v['view_name']} ({v.get('view_type','unknown')})")
            if len(missing_mappings) > 5:
                print(f"       ... and {len(missing_mappings)-5} more")
            if not self.view_to_table_map:
                print(f"       (Add views1.txt and views2.txt to get complete mappings)")
            else:
                print(f"       (These views may have been deleted or renamed)")
    
    def save_to_csv(self, output_path=None, filename='appsheet_views.csv'):
        """Save parsed views to CSV file."""
        if not self.views:
            print("  ⚠️  No views found - creating empty views file")
            # Create empty CSV with headers
            if output_path is None:
                csv_path = filename
            else:
                csv_path = os.path.join(output_path, filename)
                
            # Write empty CSV with minimal headers
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['view_name', 'category', 'view_type', 'data_source', 'source_table'])
                
            print(f"  ✅ Empty views file saved to: {csv_path}")
            return
            
        if output_path is None:
            csv_path = filename
        else:
            csv_path = os.path.join(output_path, filename)
            
        # Define field names in the desired order - important fields first
        fieldnames = [
            # View Identity & Type
            'view_name', 'view_type', 'category', 'is_system_view',
            # Data Source
            'data_source', 'source_table',
            # View Position & Display
            'position', 'ref_parent', 'display_mode', 'use_card_layout',
            # Actions (with show_action_bar moved here)
            'show_action_bar', 'action_display_mode', 'referenced_actions', 'event_actions', 'available_actions',
            # Columns
            'view_columns', 'available_columns', 'hidden_columns', 'referenced_columns',
            # Other View Settings
            'dashboard_view_entries', 'show_if', 'icon', 'created_by', 
            'action_type', 'html_position', 'view_configuration'
        ]

        # Clean up data before writing - replace newlines in problematic fields
        cleaned_views = []
        for view in self.views:
            cleaned_view = view.copy()
            
            # Fields that might contain newlines - clean them
            newline_fields = ['show_if', 'view_configuration', 'referenced_columns']
            for field in newline_fields:
                if field in cleaned_view and cleaned_view[field]:
                    # Replace newlines with spaces or a special delimiter
                    cleaned_view[field] = cleaned_view[field].replace('\n', ' ').replace('\r', '')
                    
            cleaned_views.append(cleaned_view)

        # Write CSV with proper quoting for all fields
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore',
                                  quoting=csv.QUOTE_ALL)  # Changed to QUOTE_ALL
            writer.writeheader()
            writer.writerows(cleaned_views)
            
        print(f"  ✅ Views saved to: {csv_path}")

# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse AppSheet views from HTML documentation')
    parser.add_argument('html_file', help='Path to the HTML file containing views')
    parser.add_argument('--output', '-o', default='appsheet_views.csv',
                      help='Output CSV file path (default: appsheet_views.csv)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    print("👁️  AppSheet Views Parser")
    print("=" * 50)
    
    # Run parser
    views_parser = ViewsParser(debug_mode=args.debug)
    views_parser.parse(args.html_file)
    views_parser.save_to_csv(args.output)

        