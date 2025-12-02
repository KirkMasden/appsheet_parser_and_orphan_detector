#!/usr/bin/env python3
"""
Actions Parser for AppSheet HTML Documentation
Extracts action information including types, references, and dependencies.
Identifies system-generated vs user-created actions using actions.txt file.
"""

import csv
import os
import re
import json
import sys
from collections import defaultdict
from base_parser import BaseParser

class ActionsParser(BaseParser):
    """Parser specifically for AppSheet actions."""
    
    def __init__(self, html_path=None, html_string=None, soup=None, debug_mode=False):
        super().__init__(html_path, html_string, soup, debug_mode=debug_mode)
        self.actions_data = []
        
        # Store the absolute HTML path before any directory changes
        if html_path:
            self.html_path = os.path.abspath(html_path)
        else:
            self.html_path = None
        
        # Load slice mapping if available
        self.load_slice_mapping()
        
        # Track action dependencies
        self.action_dependencies = defaultdict(set)
        
        # Maps action names to system status
        self.action_system_status = {}

        # Track which action keys have been used
        self.used_action_keys = set()

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
        else:
            print(f"  ⚠️  Slice mapping file not found: {csv_path}")
            print(f"     Creating empty mapping (assuming no slices in app)")

    def parse_actions_text_file(self, file_path):
        """Parse actions.txt file to extract system-generated status."""
        actions_data = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_table = None
            i = 0
            
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines
                if not line:
                    i += 1
                    continue
                
                # Check if this is a table header (lines not starting with whitespace and not containing "Effect:" or "System generated")
                if not line.startswith((' ', '\t')) and 'Effect:' not in line and 'System generated' not in line:
                    # Check if next line exists and contains an action indicator
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if 'Effect:' in next_line or 'System generated' in next_line:
                            # This line is an action name, not a table
                            pass
                        else:
                            # This is likely a table name
                            current_table = line
                            i += 1
                            continue
                
                # Parse action entry
                action_name = None
                is_system = False
                
                # Check for wide format (action name and status on same line)
                if 'System generated' in line:
                    # Wide format: "Action Name System generated"
                    action_name = line.replace('System generated', '').strip()
                    is_system = True
                elif 'Effect:' in line:
                    # Wide format: "Action Name Effect: description"
                    action_name = line.split('Effect:')[0].strip()
                    is_system = False
                else:
                    # Might be narrow format - check next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line == 'System generated':
                            # Narrow format
                            action_name = line
                            is_system = True
                            i += 1  # Skip the next line since we've processed it
                        elif next_line.startswith('Effect:'):
                            # Narrow format
                            action_name = line
                            is_system = False
                            i += 1  # Skip the next line since we've processed it
                        else:
                            # This might be a table name or other content
                            action_name = line
                            is_system = False
                
                # Check if this is the UI element pattern: add / New Action / Search actions
                if action_name == 'add' and i + 2 < len(lines):
                    next_line = lines[i + 1].strip()
                    line_after = lines[i + 2].strip() if i + 2 < len(lines) else ''
                    if next_line == 'New Action' and line_after == 'Search actions':
                        # This is the UI pattern, skip all three lines
                        i += 3
                        continue
                
                if action_name and action_name not in ['Search actions']:
                    # Normalize action name for compound key (collapse multiple spaces)
                    normalized_action_name = ' '.join(action_name.split())
                    
                    # Always use table name in key if available, and include system status
                    if current_table:
                        system_suffix = "||SYSTEM" if is_system else "||USER"
                        compound_key = f"{current_table}||{normalized_action_name}{system_suffix}"
                    else:
                        compound_key = normalized_action_name
                    
                    actions_data[compound_key] = {
                        'is_system': is_system,
                        'table': current_table,
                        'action_name': action_name  # Keep original name for display
                    }
                
                i += 1
            
            return actions_data
            
        except Exception as e:
            if self.debug_mode:
                print(f"  DEBUG: Error reading actions.txt: {str(e)}")
            return {}

    def load_actions_text_file(self):
        """Load and validate actions.txt file with user interaction if needed."""
        # Determine where actions.txt should be located
        
        if hasattr(self, 'html_path') and self.html_path:
            html_dir = os.path.dirname(os.path.abspath(self.html_path))
        else:
            html_dir = os.getcwd()
        
        actions_file_path = os.path.join(html_dir, 'actions.txt')

        # Check if file exists
        if not os.path.exists(actions_file_path):
            print(f"\n  ⚠️  IMPORTANT: No actions.txt file found")
            print(f"\n  In the legacy mode of the AppSheet editor:")
            print(f"  1. Click on 'Behavior' in the left sidebar")
            print(f"  2. Scroll to the bottom of the page")
            print(f"  3. Click on 'Show all' to display system actions")
            print(f"  4. Select ALL text on the page (Ctrl+A / Cmd+A)")
            print(f"  5. Copy and paste into a file named 'actions.txt'")
            print(f"  6. Save the file in the folder with your Application Documentation.html file")
            print(f"\n  Looking for actions.txt in: {html_dir}")
            
            while True:
                print(f"\n  To continue with file parsing, choose one of the following:")
                print(f"    1) I've added actions.txt")
                print(f"    2) Continue without system action detection")
                print(f"    3) Abort")
                
                response = input("\n  Choice (1/2/3): ").strip()
                
                if response == '1':
                    if os.path.exists(actions_file_path):
                        print("\n  ✅ Found actions.txt! Continuing...")
                        break
                    else:
                        print("\n  ❌ Still can't find actions.txt")
                        continue
                        
                elif response == '2':
                    print("\n  Continuing without system action detection...")
                    return False
                    
                elif response == '3':
                    print("\n  Aborting.")
                    sys.exit(0)
                else:
                    print("\n  Invalid choice. Please enter 1, 2, or 3.")
        
        # File exists, now parse it
        print(f"  📂 Loading system action data from actions.txt")
        actions_text_data = self.parse_actions_text_file(actions_file_path)
        
        if not actions_text_data:
            print("  ⚠️  Warning: Could not parse actions.txt")
            return False
        
        # Check for system actions
        system_action_count = sum(1 for a in actions_text_data.values() if a['is_system'])
        total_actions_in_file = len(actions_text_data)
        
        print(f"  📊 Found {total_actions_in_file} actions in text file ({system_action_count} system-generated)")
        
        # Handle case where no system actions found
        if system_action_count == 0 and total_actions_in_file > 0:
            print(f"\n  ⚠️  No system actions found in actions.txt")
            print(f"\n  Found {total_actions_in_file} actions in the file, but none marked as 'System generated'")
            print(f"\n  This could mean either:")
            print(f"  1. 'Show all' was not clicked before copying (most common)")
            print(f"  2. This app genuinely has no system actions (rare but possible)")
            print(f"\n  To verify:")
            print(f"  1. Return to Behavior section in the legacy editor")
            print(f"  2. Look for 'Show all' link at the bottom of the page")
            print(f"  3. If you see 'Show all':")
            print(f"     - Click it to reveal system actions")
            print(f"     - Select ALL text on the page (Ctrl+A / Cmd+A)")
            print(f"     - Copy and replace contents of actions.txt")
            print(f"  4. If you see 'Hide system actions' instead:")
            print(f"     - System actions are already visible")
            print(f"     - This app may genuinely have no system actions")
            
            while True:
                print(f"\n  To continue with file parsing, choose one of the following:")
                print(f"    1) I've updated actions.txt")
                print(f"    2) No system actions exist (continue anyway)")
                print(f"    3) Abort")
                
                response = input("\n  Choice (1/2/3): ").strip()
                
                if response == '1':
                    # Re-parse the file
                    return self.load_actions_text_file()
                    
                elif response == '2':
                    print("\n  Continuing with all actions marked as user-created...")
                    break
                    
                elif response == '3':
                    print("\n  Aborting.")
                    sys.exit(0)
                else:
                    print("\n  Invalid choice. Please enter 1, 2, or 3.")
        
        # Store the system status data
        self.action_system_status = actions_text_data
        
        return True

    def validate_actions_match(self, html_actions, text_actions):
        """Validate that actions.txt matches the HTML file."""
        # Extract actual action names from compound keys
        text_action_names = {}
        for key, data in text_actions.items():
            action_name = data.get('action_name', key)
            text_action_names[action_name] = data
        
        # Create normalized versions for matching only
        html_to_normalized = {action: ' '.join(action.split()) for action in html_actions}
        text_to_normalized = {action: ' '.join(action.split()) for action in text_action_names.keys()}
        
        # Create reverse mapping to find originals
        normalized_to_html = {v: k for k, v in html_to_normalized.items()}
        normalized_to_text = {v: k for k, v in text_to_normalized.items()}
        
        # Compare normalized versions
        html_normalized = set(html_to_normalized.values())
        text_normalized = set(text_to_normalized.values())
        
        matched_normalized = html_normalized & text_normalized
        only_in_html_normalized = html_normalized - text_normalized
        only_in_text_normalized = text_normalized - html_normalized
        
        # Get original names for reporting
        html_action_names = set(html_actions)
        only_in_html = {action for action in html_action_names 
                       if html_to_normalized.get(action) in only_in_html_normalized}
        only_in_text = {action for action in text_action_names.keys() 
                       if text_to_normalized.get(action) in only_in_text_normalized}
        matched = {action for action in html_action_names 
                  if html_to_normalized.get(action) in matched_normalized}
        
        match_percentage = (len(matched) / len(html_action_names) * 100) if html_action_names else 0
        
        # If match rate is very low, likely different app
        if match_percentage < 30 and len(html_action_names) > 10:
            print(f"\n  ⚠️  WARNING: actions.txt appears to be from a different app")
            print(f"\n  Significant mismatch detected:")
            print(f"  - Actions in HTML file: {len(html_action_names)}")
            print(f"  - Actions in text file: {len(text_action_names)}")
            print(f"  - Successfully matched: {len(matched)} (only {match_percentage:.0f}%)")
            
            # Show examples
            print(f"\n  Examples of mismatched action names:")
            if only_in_html:
                print(f"    In HTML but not in text:")
                for i, action in enumerate(sorted(only_in_html)[:3]):
                    print(f"      - {action}")
                if len(only_in_html) > 3:
                    print(f"      ... and {len(only_in_html) - 3} more")
            
            if only_in_text:
                print(f"\n    In text but not in HTML:")
                for i, action in enumerate(sorted(only_in_text)[:3]):
                    print(f"      - {action}")
                if len(only_in_text) > 3:
                    print(f"      ... and {len(only_in_text) - 3} more")
            
            print(f"\n  This usually means:")
            print(f"  1. The actions.txt file is from a different AppSheet app")
            print(f"  2. The app has been significantly modified since actions.txt was created")
            
            print(f"\n  To fix:")
            print(f"  1. Open THIS app in the legacy mode of the AppSheet editor")
            print(f"  2. Click on 'Behavior' in the left sidebar")
            print(f"  3. Scroll to the bottom of the page")
            print(f"  4. Click on 'Show all' to display system actions")
            print(f"  5. Select ALL text on the page (Ctrl+A / Cmd+A)")
            print(f"  6. Copy and paste into actions.txt (replacing current contents)")
            print(f"  7. Save the file in the folder with your Application Documentation.html file")
            
            while True:
                print(f"\n  To continue with file parsing, choose one of the following:")
                print(f"    1) I've updated actions.txt from the correct app")
                print(f"    2) Continue with partial data (NOT recommended)")
                print(f"    3) Abort")
                
                response = input("\n  Choice (1/2/3): ").strip()
                
                if response == '1':
                    # Re-load and re-validate
                    return False  # Signal to retry
                    
                elif response == '2':
                    print("\n  Continuing with partial match...")
                    print(f"  ⚠️  System status will only be available for {len(matched)} matched actions")
                    return True
                    
                elif response == '3':
                    print("\n  Aborting.")
                    sys.exit(0)
                else:
                    print("\n  Invalid choice. Please enter 1, 2, or 3.")
        
        # Good match rate
        elif match_percentage < 100 or only_in_text:
            print(f"  ✅ Matched {len(matched)} of {len(html_action_names)} actions ({match_percentage:.0f}%)")
            if only_in_html:
                print()  # Add blank line before special message
                print(f"  ℹ️  {len(only_in_html)} actions in HTML not found in text file:")

                # Show all if 10 or fewer, otherwise show first 10
                actions_to_show = sorted(only_in_html)[:10]
                for action in actions_to_show:
                    print(f"      - {action}")
                if len(only_in_html) > 10:
                    print(f"      ... and {len(only_in_html) - 10} more")
            if only_in_text:
                print()  # Add blank line before special message
                print(f"  ℹ️  {len(only_in_text)} actions in text file not found in HTML:")
                actions_to_show = sorted(only_in_text)[:10]
                for action in actions_to_show:
                    print(f"      - {action}")
                if len(only_in_text) > 10:
                    print(f"      ... and {len(only_in_text) - 10} more")
        
        return True

    def detect_duplicate_action_names(self, actions_list):
        """
        Detect duplicate action names in the parsed actions.
        Returns a dict of duplicate names and their counts.
        """
        from collections import Counter
        
        # Create compound keys with table name + action name
        compound_names = []
        for action in actions_list:
            table = action.get('source_table', 'Unknown')
            name = action['action_name']
            compound_key = f"{table}||{name}"
            compound_names.append(compound_key)
        
        # Count occurrences of each compound key
        name_counts = Counter(compound_names)
        
        # Find duplicates (count > 1)
        duplicates = {}
        for compound_key, count in name_counts.items():
            if count > 1:
                # Extract just the action name for the duplicates dict
                table, name = compound_key.split('||', 1)
                # Include table info in the duplicate reporting
                display_name = f"{name} (in table: {table})"
                duplicates[display_name] = count
        
        return duplicates

    def handle_duplicate_warning(self, duplicates):
        """
        Display warning about duplicate action names and get user choice.
        Returns True to continue with limitations, False to exit.
        """
        print(f"\n  ⚠️  WARNING: Duplicate action names detected!")
        print(f"\n  Found duplicate action names in your app:")
        
        for name, count in duplicates.items():
            print(f"    • \"{name}\" appears {count} times")
        
        print(f"\n  ISSUE: When actions share the same name, we cannot reliably determine")
        print(f"  which is system-generated and which is user-created. This prevents")
        print(f"  accurate orphan detection for these actions.")
        
        print(f"\n  RECOMMENDATION: Rename the user-created action(s) to have unique names.")
        print(f"  (Note: System-generated action names cannot be changed)")
        
        while True:
            print(f"\n  How would you like to proceed?")
            print(f"    1) Exit and fix the issue")
            print(f"       - Edit your app in AppSheet to rename the user-created action(s)")
            print(f"       - Generate fresh HTML and text files")
            print(f"       - Run the analysis again")
            print(f"    2) Continue with limitations")
            print(f"       - Duplicate-named actions will be marked as \"Unsure\" status")
            print(f"       - These actions will be excluded from orphan detection")
            print(f"       - All other orphan detection will proceed normally")
            
            response = input("\n  Choice (1/2): ").strip()
            
            if response == '1':
                print("\n  Exiting to allow fixes.")
                sys.exit(0)
            elif response == '2':
                print("\n  Continuing with limitations...")
                return True
            else:
                print("\n  Invalid choice. Please enter 1 or 2.")

    def detect_action_type_from_json(self, json_str):
        """
        Detect action type based on JSON structure patterns.
        Returns a tuple of (category, specific_type).
        Uses fallback regex patterns if JSON parsing fails.
        """
        if not json_str:
            return ('Unknown', 'unknown')
            
        try:
            # Clean up the JSON string - handle escaped quotes
            clean_json = json_str.replace('\\"', '"')
            data = json.loads(clean_json)
            
            # Analyze JSON structure to determine action type
            return self._analyze_json_structure(data)
                
        except (json.JSONDecodeError, TypeError) as e:
            if self.debug_mode:
                print(f"  DEBUG: JSON parse failed, using fallback pattern matching: {e}")
            
            # Fallback: Use regex patterns on raw JSON string
            return self._analyze_json_fallback(json_str)
    
    def _analyze_json_structure(self, data):
        """Analyze parsed JSON data to determine action type."""
        
        # 1. Execute a group of actions - has Actions array
        if 'Actions' in data and isinstance(data['Actions'], list):
            return ('Execute a group of actions', 'execute_group')
        
        # 2. Edit actions - has DesktopBehavior with form
        if 'DesktopBehavior' in data and 'form' in str(data['DesktopBehavior']).lower():
            return ('Edit', 'edit_form')
        
        # 3. Navigation actions - has NavigateTarget
        if 'NavigateTarget' in data:
            nt = str(data['NavigateTarget'])
            lower_nt = nt.lower()
            
            # Check for external indicators
            # LaunchExternal field presence indicates external URL (regardless of value)
            # Also check for URL patterns in the target
            if 'LaunchExternal' in data or 'http://' in lower_nt or 'https://' in lower_nt:
                return ('Go to a website', 'open_url')
            # Only treat it as a new-record-form when you're explicitly calling LINKTOFORM(...)
            elif 'linktoform(' in lower_nt:
                return ('Make a new record', 'new_record_form')
            else:
                return ('Navigate', 'go_to_view')
      
        # 4. Write/Set values actions - has Assignments with ColumnToEdit
        if 'Assignments' in data and isinstance(data['Assignments'], list):
            if any('ColumnToEdit' in assign for assign in data['Assignments']):
                return ('Write', 'set_columns')
        
        # 5. Execute action on set of rows - has ReferencedTable + ReferencedAction
        if 'ReferencedTable' in data and 'ReferencedAction' in data:
            return ('Execute an action on a set of rows', 'execute_on_rows')
        
        # 6. Add row actions - has ReferencedTable + Assignments (without ReferencedAction)
        if ('ReferencedTable' in data and 'Assignments' in data and 
            'ReferencedAction' not in data):
            return ('Add row', 'add_row')
        
        # 7. Delete actions - has InputParametersUsed set to null and ModifiesData true
        if (data.get('InputParametersUsed') is None and 
            data.get('ModifiesData') is True and
            'Assignments' not in data and 'NavigateTarget' not in data):
            return ('Delete', 'delete')
        
        # 8. Simple column set action - has ColumnToEdit at root level
        if 'ColumnToEdit' in data:
            return ('Write', 'set_column')
        
        # Default: try to infer from other properties
        if data.get('ModifiesData') is True:
            return ('Unknown', 'modifies_data')
        else:
            return ('Unknown', 'unclassified')
    
    def _analyze_json_fallback(self, json_str):
        """
        Fallback analysis using regex patterns when JSON parsing fails.
        Looks for key patterns in the raw JSON string.
        """
        json_lower = json_str.lower()
        
        # 1. Execute a group of actions
        if '"actions":[' in json_lower:
            return ('Execute a group of actions', 'execute_group')
        
        # 2. Edit actions
        if '"desktopbehavior"' in json_lower and 'form' in json_lower:
            return ('Edit', 'edit_form')
        
        # 3. Navigation actions
        if '"navigatetarget"' in json_lower:
            # Check for external indicators
            if '"launchexternal"' in json_lower or 'http://' in json_lower or 'https://' in json_lower:
                return ('Go to a website', 'open_url')
            # Only LINKTOFORM(...) is a new-record-form action
            elif 'linktoform(' in json_lower:
                return ('Make a new record', 'new_record_form')
            else:
                return ('Navigate', 'go_to_view')
        
        # 4. Write/Set values actions
        if '"assignments"' in json_lower and '"columntoedit"' in json_lower:
            return ('Write', 'set_columns')
        
        # 5. Execute action on set of rows
        if '"referencedtable"' in json_lower and '"referencedaction"' in json_lower:
            return ('Execute an action on a set of rows', 'execute_on_rows')
        
        # 6. Add row actions
        if ('"referencedtable"' in json_lower and '"assignments"' in json_lower and 
            '"referencedaction"' not in json_lower):
            return ('Add row', 'add_row')
        
        # 7. Delete actions
        if ('"inputparametersused":null' in json_lower and 
            '"modifiesdata":true' in json_lower and
            '"assignments"' not in json_lower and '"navigatetarget"' not in json_lower):
            return ('Delete', 'delete')
        
        # 8. Simple column set action
        if '"columntoedit"' in json_lower and '"assignments"' not in json_lower:
            return ('Write', 'set_column')
        
        # Check for data modification patterns
        if '"modifiesdata":true' in json_lower:
            return ('Unknown', 'modifies_data_fallback')
        
        return ('Unknown', 'fallback_unclassified')

    def extract_action_type(self, action_type_text):
        """
        Extract and categorize the action type from the 'Do this' field.
        Returns a tuple of (category, specific_type).
        """
        if not action_type_text:
            return ('unknown', 'unknown')
            
        # Common action type patterns
        type_mappings = {
            'Data: add a new row to another table': ('data', 'add_row'),
            'Data: set the values of some columns in this row': ('data', 'set_columns'),
            'Data: set values of columns': ('data', 'set_columns'),
            'Data: delete this row': ('data', 'delete'),
            'Data: execute an action on a set of rows': ('data', 'execute_on_rows'),
            'App: go to another view within this app': ('navigation', 'go_to_view'),
            'App: go to another view': ('navigation', 'go_to_view'),
            'App: open a form to edit this row': ('navigation', 'edit_form'),
            'External: go to a website': ('external', 'open_url'),
            'External: open a URL': ('external', 'open_url'),
            'External: start an email': ('external', 'send_email'),
            'External: start a phone call': ('external', 'phone_call'),
            'External: start a text message': ('external', 'send_sms'),
            'Grouped: execute a sequence of actions': ('grouped', 'sequence'),
            'Grouped: run a set of actions': ('grouped', 'sequence')
        }
        
        # Check for exact matches first
        for pattern, (category, specific) in type_mappings.items():
            if pattern.lower() in action_type_text.lower():
                return (category, specific)
        
        # Check for partial matches
        if 'data:' in action_type_text.lower():
            return ('data', 'other')
        elif 'app:' in action_type_text.lower():
            return ('navigation', 'other')
        elif 'external:' in action_type_text.lower():
            return ('external', 'other')
        elif 'grouped:' in action_type_text.lower():
            return ('grouped', 'other')
            
        return ('unknown', action_type_text)
    
    def parse_action_json(self, json_str, action_type_plain_english):
        """
        Parse the 'With these properties' JSON based on action type.
        Returns a dictionary with extracted information.
        """
        if not json_str:
            return {}
            
        try:
            data = json.loads(json_str)
            parsed = {}
            
            # Common fields across all action types
            for field in ['Prominence', 'NeedsConfirmation', 'ConfirmationMessage', 
                         'ModifiesData', 'BulkApplicable']:
                if field in data:
                    parsed[field.lower()] = data[field]
            
            # Extract based on action type (using new human-readable names)
            if action_type_plain_english == 'Write':
                # Data change actions
                if 'Assignments' in data:
                    assignments = []
                    for assign in data['Assignments']:
                        assignments.append({
                            'column': assign.get('ColumnToEdit', ''),
                            'value': assign.get('NewColumnValue', '')
                        })
                    parsed['assignments'] = assignments
                    
                if 'ColumnToEdit' in data:
                    parsed['column_to_edit'] = data['ColumnToEdit']
                if 'NewColumnValue' in data:
                    parsed['new_column_value'] = data['NewColumnValue']
                    
            elif action_type_plain_english == 'Navigate':
                # Navigation actions
                if 'NavigateTarget' in data:
                    parsed['navigate_target'] = data['NavigateTarget']
                if 'NavigateTargetType' in data:
                    parsed['navigate_target_type'] = data['NavigateTargetType']
                if 'NavigateExpression' in data:
                    parsed['navigate_expression'] = data['NavigateExpression']
                    
            elif action_type_plain_english == 'Go to a website':
                # External URL actions
                if 'NavigateTarget' in data:
                    parsed['navigate_target'] = data['NavigateTarget']
                # LaunchExternal is preserved in the raw JSON but not extracted as separate field
                    
            elif action_type_plain_english == 'Execute a group of actions':
                # Grouped actions - this is the key fix!
                if 'Actions' in data:
                    referenced_actions = []
                    for action in data['Actions']:
                        if 'ActionName' in action:
                            referenced_actions.append(action['ActionName'])
                    parsed['referenced_actions'] = referenced_actions
                    
            elif action_type_plain_english == 'external':
                # External actions
                if 'NavigateTarget' in data:
                    parsed['url'] = data['NavigateTarget']
                if 'LaunchExternal' in data:
                    parsed['launch_external'] = data['LaunchExternal']
                    
            # Handle "Execute an action on a set of rows" type
            if action_type_plain_english == 'Execute an action on a set of rows':
                if 'ReferencedAction' in data and data['ReferencedAction'] is not None:
                    # Store as a list with single item for consistency
                    parsed['referenced_actions'] = [data['ReferencedAction']]
                    
            # Reference actions (actions that call other actions)
            if 'ReferencedTable' in data:
                parsed['referenced_table'] = data['ReferencedTable']
            if 'ReferencedRows' in data:
                parsed['referenced_rows'] = data['ReferencedRows']
            # Handle ReferencedAction for other action types that might have it
            if 'ReferencedAction' in data and action_type_plain_english != 'Execute an action on a set of rows':
                parsed['referenced_action'] = data['ReferencedAction']
                
            return parsed
            
        except (json.JSONDecodeError, TypeError) as e:
            if self.debug_mode:
                print(f"  DEBUG: JSON parse error in action properties: {e}")
            return {}
    
    def extract_views_from_navigate_target(self, navigate_target):
        """
        Extract view name(s) from NavigateTarget formula.
        Returns a list of view names.
        """
        if not navigate_target:
            return []
    
        # Canonicalize quotes & whitespace
        navigate_target = self.normalize_string(navigate_target)

        view_names = []
        
        # Debug: Print what we're working with
        if self.debug_mode:
            print(f"\n  DEBUG: Extracting views from navigate_target: '{navigate_target}'")
            print(f"  DEBUG: Length: {len(navigate_target)}")
            print(f"  DEBUG: Repr: {repr(navigate_target)}")
        
        # Pattern 1: LINKTOVIEW("ViewName", ...)
        linktoview_matches = re.findall(r'LINKTOVIEW\(\s*"([^"]+)"', navigate_target)
        if self.debug_mode and linktoview_matches:
            print(f"  DEBUG: LINKTOVIEW matches: {linktoview_matches}")
        view_names.extend(linktoview_matches)
        
        # Pattern 2: LINKTOROW(..., "ViewName") - removed the \) at the end
        linktorow_matches = re.findall(r'LINKTOROW\([^,]+,\s*"([^"]+)"', navigate_target)
        if self.debug_mode and linktorow_matches:
            print(f"  DEBUG: LINKTOROW matches: {linktorow_matches}")
        view_names.extend(linktorow_matches)
        
        # Pattern 3: #control=ViewName in URLs (unquoted)
        # This handles cases where #control appears without quotes
        # Strip any trailing whitespace from matches
        control_matches = re.findall(r'#control=([^"&]+)', navigate_target)
        if control_matches:
            # Clean up any trailing whitespace from matches
            control_matches = [match.strip() for match in control_matches]
            if self.debug_mode:
                print(f"  DEBUG: #control matches: {control_matches}")
        view_names.extend(control_matches)
        
        # Pattern 4: CONCATENATE with #control= (like CONCATENATE("#control=Definition&row=", ...))
        # This pattern now properly captures view names with spaces until & or "
        concat_matches = re.findall(r'CONCATENATE\(\s*"#control=([^"&]+)[&"]', navigate_target)
        if self.debug_mode and concat_matches:
            print(f"  DEBUG: CONCATENATE matches: {concat_matches}")
        view_names.extend(concat_matches)
        
        # Pattern 5: Simple quoted strings with #control= (like "#control=ViewName&...")
        # This catches cases that aren't wrapped in CONCATENATE
        simple_control_matches = re.findall(r'^"#control=([^"&]+)[&"]', navigate_target)
        if self.debug_mode and simple_control_matches:
            print(f"  DEBUG: Simple #control matches: {simple_control_matches}")
        view_names.extend(simple_control_matches)
        
        # Debug: Show final results
        if self.debug_mode:
            print(f"  DEBUG: Final view_names: {view_names}")
        
        # Return unique view names
        return list(set(view_names))

    def parse(self):
        """
        Extract all actions from the HTML.
        Returns a list of dictionaries containing action information.
        """
        print("⚡ Extracting actions...")
        print()  # Add blank line for better visual separation
        
        # Load system action status from text file
        actions_loaded = self.load_actions_text_file()
        
        # Store whether we have system status data
        self.has_system_status = actions_loaded and bool(self.action_system_status)

        # Find all action headers
        action_headers = self.soup.find_all('h5', id=lambda x: x and x.startswith('action_'))
        
        if not action_headers:
            print("  ℹ️  No actions found in this app")
            return self.actions_data
        
        for index, action_header in enumerate(action_headers):
            action_table = action_header.find_next('table')
            element_key = f"{action_header.get('id')}_{index}"
            if action_table and not self.is_element_processed(element_key):
                action_info = self._extract_action_data(action_table, action_header)
                
                if action_info:
                    self.actions_data.append(action_info)
                    self.mark_element_processed(element_key)
        
        # Validate actions match if we loaded text file
        if self.has_system_status:
            # Get list of action names from HTML
            html_action_names = [action['action_name'] for action in self.actions_data]
            
            # Validate match
            if not self.validate_actions_match(html_action_names, self.action_system_status):
                # User chose to reload - try again
                self.action_system_status = {}
                self.has_system_status = False
                actions_loaded = self.load_actions_text_file()
                self.has_system_status = actions_loaded and bool(self.action_system_status)
                
                # Re-validate if loaded
                if self.has_system_status:
                    self.validate_actions_match(html_action_names, self.action_system_status)       

        # Check for duplicate action names AFTER system status has been assigned
        duplicates = self.detect_duplicate_action_names(self.actions_data)
        if duplicates:
            # Store duplicate names for later use
            self.duplicate_action_names = set(duplicates.keys())
            # Handle warning and get user choice
            self.handle_duplicate_warning(duplicates)
            
            # Now update only true same‑table duplicates to "Unsure"
            for action in self.actions_data:
                # build the same “display_name” string you used when detecting duplicates
                display_name = (
                    f"{action['action_name']} "
                    f"(in table: {action.get('source_table', 'Unknown')})"
                )
                if display_name in self.duplicate_action_names:
                    action['is_system_generated'] = 'Unsure'
        else:
            self.duplicate_action_names = set()

        # Check for action names with double spaces and warn in terminal
        spaced_actions = [
            action['action_name']
            for action in self.actions_data
            if re.search(r'\s{2,}', action['action_name'])
        ]
        
        if spaced_actions:
            print("\n  ⚠️  Warning: The following action names contain multiple consecutive spaces:")
            for name in spaced_actions:
                print(f"    • {name}")
            print("    Consider renaming them in AppSheet to avoid confusion.\n")

        # Print summary
        if self.actions_data:
            self._print_summary()
                
        return self.actions_data
    
    def _extract_action_data(self, table_element, action_header):
        """Extract data specific to an action."""
        
        # Get action name from header
        action_name = action_header.get_text(strip=True)
        if action_name.startswith('Action name'):
            action_name = action_name.replace('Action name', '').strip()
        
        # Initialize action info
        action_info = {'action_name': action_name}
        
        # Track key properties
        source_table = None
        action_type_text = None
        json_properties = None
        condition_formula = None
        attached_column = None
        
        # Extract data from table rows
        for row in table_element.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                
                # Map label to field name
                if 'for a record of this table' in label:
                    source_table = value
                    action_info['source_table'] = value
                elif 'with these properties' in label:
                    json_properties = value
                    action_info['with_these_properties'] = value
                elif 'only if this condition' in label:
                    condition_formula = value
                    action_info['only_if_condition'] = value
                elif 'attach to column' in label:
                    attached_column = value
                    action_info['attach_to_column'] = value
                elif 'needs confirmation' in label:
                    action_info['needs_confirmation'] = value
                elif 'modifies data' in label:
                    action_info['modifies_data'] = value
                elif 'bulk action' in label:
                    action_info['bulk_applicable'] = value
                elif 'display name' in label:
                    action_info['display_name'] = value
                elif 'action icon' in label:
                    # Extract icon class
                    icon_element = cells[1].find('i')
                    if icon_element and icon_element.get('class'):
                        action_info['action_icon'] = ' '.join(icon_element['class'])
                    else:
                        action_info['action_icon'] = value
                elif 'set this column' in label:
                    action_info['column_to_edit'] = value
                elif 'to this value' in label:
                    action_info['to_this_value'] = value
                elif 'action order' in label:
                    action_info['action_order'] = value
                elif 'does this action apply to the whole table' in label:
                    action_info['table_scope'] = value
                elif 'visible' in label:
                    action_info['visible'] = value
        
        # Resolve table reference (could be a slice)
        if source_table:
            actual_table = self.resolve_table_reference(source_table)
            action_info['source_table'] = actual_table
        
        # Extract and categorize action type from JSON (more reliable than broken HTML text)
        if json_properties:
            category, specific = self.detect_action_type_from_json(json_properties)
            action_info['action_type_plain_english'] = category
            action_info['action_type_technical_name'] = specific
        else:
            action_info['action_type_plain_english'] = 'Unknown'
            action_info['action_type_technical_name'] = 'no_json'
        
        # Parse JSON properties based on action type
        if json_properties:
            parsed_json = self.parse_action_json(json_properties, 
                                               action_info.get('action_type_plain_english', ''))
            
            # Add parsed fields to action info
            for key, value in parsed_json.items():
                if key == 'referenced_actions':
                    # Track action dependencies
                    action_info['referenced_actions'] = '|||'.join(value)
                    for ref_action in value:
                        self.action_dependencies[action_name].add(ref_action)
                elif key == 'prominence':
                    # Extract prominence as a direct field
                    action_info['action_prominence'] = value
                elif key == 'navigate_target':
                    # Extract navigate target as a direct field
                    action_info['navigate_target'] = value
                    # Also extract the view names for easier reference
                    view_names = self.extract_views_from_navigate_target(value)
                    if view_names:
                        action_info['referenced_views'] = '|||'.join(view_names)
                else:
                    action_info[f'json_{key}'] = value
        
        # Extract references from various formula fields
        all_refs = []
        
        # From condition
        if condition_formula and condition_formula.lower() not in ['true', 'false', '']:
            refs = self.extract_references_from_text(condition_formula, actual_table)
            all_refs.extend(refs)
        
        # From display name
        if action_info.get('display_name'):
            refs = self.extract_references_from_text(action_info['display_name'], actual_table)
            all_refs.extend(refs)
        
        # From JSON properties
        if json_properties:
            refs = self.extract_references_from_json(json_properties, actual_table)
            all_refs.extend(refs)
        
        # From 'to this value' field
        if action_info.get('to_this_value'):
            refs = self.extract_references_from_text(action_info['to_this_value'], actual_table)
            all_refs.extend(refs)
        
        # Build absolute references
        if all_refs:
            absolute_refs = self.build_absolute_references(all_refs)
            action_info['referenced_columns'] = '|||'.join(absolute_refs)
            
            # Store raw references
            raw_refs = [ref['raw'] for ref in all_refs]
            if raw_refs:
                action_info['raw_references'] = ' | '.join(raw_refs)
        else:
            action_info['referenced_columns'] = ''
        
        # Add system status if available
        if self.has_system_status and hasattr(self, 'action_system_status'):
            action_data = None
            
            # Normalize action name for matching (collapse multiple spaces)
            normalized_action_name = ' '.join(action_name.split())
            
            # Try to find with compound key first (using normalized name)
            if source_table:
                # Try both SYSTEM and USER suffixes
                for suffix in ['||SYSTEM', '||USER']:
                    compound_key = f"{source_table}||{normalized_action_name}{suffix}"
                    if compound_key in self.action_system_status:
                        action_data = self.action_system_status[compound_key]
                        break
            
            # If not found with compound key, try direct normalized name
            if not action_data:
                action_data = self.action_system_status.get(normalized_action_name, {})
            
            # If still not found, try normalized name matching against all keys
            if not action_data:
                for text_action_name, data in self.action_system_status.items():
                    # Extract just the action name part from compound keys
                    if '||' in text_action_name:
                        key_action_name = text_action_name.split('||')[1].replace('||SYSTEM', '').replace('||USER', '')
                    else:
                        key_action_name = text_action_name
                    
                    # Compare normalized versions
                    if ' '.join(key_action_name.split()) == normalized_action_name:
                        action_data = data
                        break
            
            if action_data:
                action_info['is_system_generated'] = 'Yes' if action_data.get('is_system', False) else 'No'
            else:
                # Action not found in text file
                action_info['is_system_generated'] = 'Unknown'
        else:
            # No system status data available
            action_info['is_system_generated'] = 'Unknown'
        
        return action_info
    
    def _print_summary(self):
        """Print a summary of the parsed actions.w"""
        print()
        print("  📊 Actions Summary:")
        
        # Count by type
        type_counts = defaultdict(int)
        
        # Count system vs user actions
        system_count = 0
        user_count = 0
        unsure_count = 0
        unknown_count = 0
        
        for action in self.actions_data:
            category = action.get('action_type_plain_english', 'unknown')
            type_counts[category] += 1
            
            # Count by system status
            status = action.get('is_system_generated', 'Unknown')
            if status == 'Yes':
                system_count += 1
            elif status == 'No':
                user_count += 1
            elif status == 'Unsure':
                unsure_count += 1
            else:
                unknown_count += 1
        
        # Print totals with blank line after header
        print("")
        print(f"    Total actions found: {len(self.actions_data)}")
        print(f"      User-created: {user_count}")
        print(f"      System-generated: {system_count}")
        if unsure_count > 0:
            print(f"      Unsure (duplicates): {unsure_count}")
        if unknown_count > 0:
            print(f"      Unknown: {unknown_count}")
        
        # Only print type breakdown if we have real categories
        if len(type_counts) > 1 or 'unknown' not in type_counts:
            print(f"\n    By category:")
            for action_type, count in sorted(type_counts.items()):
                print(f"      {action_type}: {count}")    
    def get_field_order(self):
        """
        Define the field order for actions CSV output.
        """
        priority_fields = [
            'action_name',
            'source_table',
            'action_type_plain_english',
            'action_type_technical_name',
            'referenced_columns',
            'referenced_actions',
            'action_prominence',
            'navigate_target',  
            'referenced_views',
            'attach_to_column',
            'modifies_data',
            'only_if_condition',
            'display_name',
            'action_icon',
            'needs_confirmation',
            'bulk_applicable',
            'column_to_edit',
            'to_this_value',
            'with_these_properties',
            'raw_references'
        ]
        
        # Get all unique fields from parsed data
        all_fields = set()
        for action_data in self.actions_data:
            all_fields.update(action_data.keys())
        
        # Remove fields that start with underscore or json_, and remove placeholder fields
        excluded_fields = {'action_order', 'table_scope', 'visible'}
        all_fields = {f for f in all_fields if not f.startswith('_') and not f.startswith('json_') and f not in excluded_fields}
        
        # Use ALL priority fields (for consistent CSV structure)
        # Add any remaining fields not in priority list
        other_fields = sorted([f for f in all_fields if f not in priority_fields])
        
        # Make sure is_system_generated is always last
        final_fields = priority_fields + other_fields
        if 'is_system_generated' in final_fields:
            final_fields.remove('is_system_generated')
        final_fields.append('is_system_generated')
        
        return final_fields
    
    def save_to_csv(self, output_path=None, filename='appsheet_actions.csv'):
        """Save parsed action data to CSV file."""
        if not self.actions_data:
            print("  ⚠️  No actions found - creating empty actions file")
            # Create empty CSV with headers so other parsers can still run
            if output_path is None:
                csv_path = filename
            else:
                csv_path = os.path.join(output_path, filename)
                
            # Write empty CSV with minimal headers
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)  # Add this!
                writer.writerow(['action_name', 'source_table', 'action_type_plain_english'])
                
            print(f"  ✅ Empty actions file saved to: {csv_path}")
            return
            
        if output_path is None:
            output_path = filename
        else:
            output_path = os.path.join(output_path, filename)
            
        # Get field order
        fields = self.get_field_order()
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore',
                                   quoting=csv.QUOTE_ALL)  # Add this!
            writer.writeheader()
            writer.writerows(self.actions_data)        
        print(f"  ✅ Actions saved to: {output_path}")

def main():
    """Main function to run the actions parser."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python actions_parser.py <html_file_path> [--debug]")
        sys.exit(1)
        
    html_path = sys.argv[1]
    debug_mode = '--debug' in sys.argv
    
    if not os.path.exists(html_path):
        print(f"❌ Error: File not found: {html_path}")
        sys.exit(1)
        
    print("⚡ AppSheet Actions Parser")
    if debug_mode:
        print("   🐛 DEBUG MODE ENABLED")
    print("=" * 50)
    
    parser = ActionsParser(html_path, debug_mode=debug_mode)
    
    try:
        parser.parse()
        parser.save_to_csv()
        
        print("\n✅ Actions parsing complete!")
        
    except Exception as e:
        print(f"\n❌ Error during parsing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
