#!/usr/bin/env python3
"""
AppSheet Navigation Expression Parser - Phase 1
Parses navigation expressions from actions into action_targets.csv

This parser extracts navigation targets and context conditions from 
AppSheet action expressions, preparing data for Phase 2 edge generation.
"""

import csv
import re
import sys
import os
from typing import Dict, List, Optional, Tuple
import json

class NavigationExpressionParser:
    """Parses AppSheet navigation expressions into structured targets."""
    
    def __init__(self):
        self.parsed_targets = []
        self.unparseable = []

        # Initialize counters for statistics
        self.action_counts = {
            'total': 0,
            'navigation': 0,
            'group': 0,
            'external_url': 0,
            'data_modifications': 0,
            'other': 0
        }
        self.target_counts = {
            'direct': 0,
            'linktoview': 0,
            'linktorow': 0,
            'total': 0
        }
        self.context_counts = {
            'view': 0,
            'viewtype': 0,
            'table': 0,
            'total': 0
        }

        # Add this new attribute to store table->detail view mapping
        self.table_detail_views = {}

    def load_views_csv(self, views_file: str):
        """Load appsheet_views.csv and build table->detail view mapping."""
        if not views_file or not os.path.exists(views_file):
            print(f"Warning: Could not load views file: {views_file}")
            return
            
        try:
            with open(views_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Only process system-generated detail views
                    if (row.get('view_type', '').lower() == 'detail' and 
                        row.get('is_system_view', '').strip().lower() == 'yes'):
                        source_table = row.get('source_table', '')
                        view_name = row.get('view_name', '')
                        if source_table and view_name:
                            self.table_detail_views[source_table] = view_name
            
        except Exception as e:
            print(f"Warning: Error loading views file: {e}")
        
    def normalize_value(self, value: str) -> str:
        """Normalize a value for matching (lowercase, trim, straight quotes)."""
        if not value:
            return ""
        # Replace smart quotes with straight quotes
        value = value.replace(chr(8220), '"').replace(chr(8221), '"')
        value = value.replace(chr(8216), "'").replace(chr(8217), "'")
        # Lowercase and strip whitespace
        return value.lower().strip()

    def classify_parse_failure(self, expression: str) -> str:
        """Classify why an expression couldn't be parsed."""
        if not expression:
            return "Empty expression"
        
        expr_upper = expression.upper()
        
        # Check for external URLs
        if 'HTTP://' in expr_upper or 'HTTPS://' in expr_upper:
            return "External URL"
        
        # Check for LINKTOPARENTVIEW
        if 'LINKTOPARENTVIEW' in expr_upper:
            return "LINKTOPARENTVIEW - requires navigation history"
        
        # Check for simple column reference
        if re.match(r'^=?\[[\w\s]+\]$', expression.strip()):
            return "Simple column reference"
        
        # Check for email/SMS/other non-navigation functions
        if any(func in expr_upper for func in ['MAILTO:', 'SMS:', 'TEL:', 'GEO:']):
            return "External protocol (mailto/sms/tel/geo)"
        
        # Default
        return "Unknown pattern"
    
    def extract_quoted_value(self, text: str, start_pos: int = 0) -> Optional[str]:
        """Extract a quoted value from text, handling escaped quotes."""
        # Find opening quote
        quote_match = re.search(r'"', text[start_pos:])
        if not quote_match:
            return None
        
        quote_start = start_pos + quote_match.start() + 1
        escaped = False
        
        for i in range(quote_start, len(text)):
            if text[i] == '"' and not escaped:
                return text[quote_start:i]
            escaped = (text[i] == '\\')
        
        return None
    
    def parse_direct_navigation(self, expression: str) -> List[Dict]:
        """Parse direct navigation expressions like ="#control=ViewName" or CONCATENATE with #control."""
        targets = []

        # Track that we found direct navigation
        if '#control=' in expression or '#page=' in expression:
            self.target_counts['direct'] += 1
            self.target_counts['total'] += 1
        
        # Pattern for ="#control=ViewName"
        control_pattern = r'#control=([^"&]+)'
        for match in re.finditer(control_pattern, expression):
            view_name = match.group(1).strip().strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
            targets.append({
                'target_view': view_name,
                'target_row_expr': '',
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'view_match_pattern': '',
                'view_match_type': '',
                'ifs_branch_index': '',
                'ifs_branch_text': ''
            })
        
        # Pattern for #page=detail&table=TableName
        page_pattern = r'#page=detail&table=([^&"]+)'
        for match in re.finditer(page_pattern, expression):
            table_name = match.group(1).strip().strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
            # URL decode if needed
            table_name = table_name.replace('%20', ' ')
            
            # Look up actual detail view for this table (handles renamed tables)
            if table_name in self.table_detail_views:
                view_name = self.table_detail_views[table_name]
            else:
                # Fallback to standard convention if no mapping found
                view_name = f"{table_name}_Detail"
                
            targets.append({
                'target_view': view_name,
                'target_row_expr': '',
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'view_match_pattern': '',
                'view_match_type': '',
                'ifs_branch_index': '',
                'ifs_branch_text': ''
            })
        
        return targets
    
    def parse_column_reference(self, expression: str) -> List[Dict]:
        """Parse simple column references like [Link] that contain navigation URLs."""
        targets = []
        
        # If it's just a column reference like [ColumnName], mark it as dynamic
        if re.match(r'^\[[^\]]+\]$', expression.strip()):
            targets.append({
                'target_view': 'DYNAMIC_COLUMN_VALUE',
                'target_row_expr': expression.strip(),
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'view_match_pattern': '',
                'view_match_type': ''
            })
        
        return targets
    
    def parse_linktoview(self, expression: str) -> List[Dict]:
        """Parse LINKTOVIEW expressions (both quoted and unquoted view names)."""
        targets = []

        # Track LINKTOVIEW usage
        if 'LINKTOVIEW' in expression.upper():
            self.target_counts['linktoview'] += 1
            self.target_counts['total'] += 1
        
        # Pattern 1: Quoted view names (e.g., LINKTOVIEW("ViewName"))
        quoted_pattern = r'LINKTOVIEW\s*\(\s*"([^"]+)"\s*\)'
        
        for match in re.finditer(quoted_pattern, expression, re.IGNORECASE):
            view_name = match.group(1).strip().strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
            targets.append({
                'target_view': view_name,
                'target_row_expr': '',
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'view_match_pattern': '',
                'view_match_type': '',
                'ifs_branch_index': '',
                'ifs_branch_text': ''
            })
        
        # Pattern 2: Unquoted view names (e.g., LINKTOVIEW(Session confirmation))
        # This pattern looks for LINKTOVIEW( followed by content until the closing )
        # We need to be careful about nested parentheses
        unquoted_pattern = r'LINKTOVIEW\s*\(([^")][^)]*)\)'
        
        # Only process if we haven't already found quoted matches at this position
        quoted_positions = [match.span() for match in re.finditer(quoted_pattern, expression, re.IGNORECASE)]
        
        for match in re.finditer(unquoted_pattern, expression, re.IGNORECASE):
            # Check if this match overlaps with any quoted match
            current_span = match.span()
            is_overlap = any(
                (current_span[0] >= q[0] and current_span[0] < q[1]) or 
                (current_span[1] > q[0] and current_span[1] <= q[1])
                for q in quoted_positions
            )
            
            if not is_overlap:
                view_name = match.group(1).strip()
                # Clean up the view name
                view_name = view_name.strip().strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
                targets.append({
                    'target_view': view_name,
                    'target_row_expr': '',
                    'must_be_in_views': '',
                    'must_not_be_in_views': '',
                    'must_be_viewtype': '',
                    'must_not_be_viewtype': '',
                    'must_be_table': '',
                    'must_not_be_table': '',
                    'view_match_pattern': '',
                    'view_match_type': '',
                    'ifs_branch_index': '',
                    'ifs_branch_text': ''
                })
        
        return targets
    
    def parse_linktorow(self, expression: str) -> List[Dict]:
        """Parse LINKTOROW expressions."""
        targets = []

        # Track LINKTOROW usage
        if 'LINKTOROW' in expression.upper():
            self.target_counts['linktorow'] += 1
            self.target_counts['total'] += 1
        # Find LINKTOROW and capture everything in parentheses
        linktorow_match = re.search(r'LINKTOROW\s*\((.*)\)', expression, re.IGNORECASE | re.DOTALL)
        if not linktorow_match:
            return targets
        
        content = linktorow_match.group(1)
        
        # Find the last comma that separates row_expr from view_name
        # We need to track parentheses depth to handle nested functions
        paren_depth = 0
        quote_char = None
        last_comma_pos = -1
        
        for i, char in enumerate(content):
            if quote_char:
                if char == quote_char and (i == 0 or content[i-1] != '\\'):
                    quote_char = None
            elif char in ['"', "'", chr(8220), chr(8221)]:  # Include smart quotes
                quote_char = char
            elif char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                last_comma_pos = i
        
        if last_comma_pos > 0:
            row_expr = content[:last_comma_pos].strip()
            view_name = content[last_comma_pos+1:].strip()
            
            # Remove delimiter quotes (both regular and smart)
            view_name = view_name.strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
            
            # Check for self-referential forced sync pattern
            # LINKTOROW([_THISROW], CONTEXT("View")) is just a sync trigger, not navigation
            if '[_THISROW]' in row_expr.upper() and 'CONTEXT' in view_name.upper():
                # This is a forced sync, not real navigation - skip it
                return targets
            
            targets.append({
                'target_view': view_name,
                'target_row_expr': row_expr,
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'view_match_pattern': '',
                'view_match_type': '',
                'ifs_branch_index': '',
                'ifs_branch_text': ''
            })
        
        return targets

    def count_only_if_contexts(self, only_if_condition: str):
        """Count context conditions in only_if_condition field."""
        if not only_if_condition or 'CONTEXT' not in only_if_condition.upper():
            return
        
        # Count each type of context
        view_matches = len(re.findall(r'CONTEXT\s*\(\s*"View"\s*\)', only_if_condition, re.IGNORECASE))
        viewtype_matches = len(re.findall(r'CONTEXT\s*\(\s*"ViewType"\s*\)', only_if_condition, re.IGNORECASE))
        table_matches = len(re.findall(r'CONTEXT\s*\(\s*"Table"\s*\)', only_if_condition, re.IGNORECASE))
        
        self.context_counts['view'] += view_matches
        self.context_counts['viewtype'] += viewtype_matches
        self.context_counts['table'] += table_matches
        self.context_counts['total'] += (view_matches + viewtype_matches + table_matches)
    
    def parse_context_condition(self, condition: str) -> Tuple[str, str, str]:
        """
        Parse a CONTEXT condition.
        Returns: (context_type, operator, value)
        """
        # Pattern for CONTEXT("View")="value" or CONTEXT("ViewType")="value"
        # Note: Allow case variations in the context type
        pattern = r'CONTEXT\s*\(\s*"(View|ViewType|Table|VIEW|VIEWTYPE|TABLE)"\s*\)\s*(=|<>|!=)\s*"([^"]+)"'
        match = re.search(pattern, condition, re.IGNORECASE)
        
        if match:
            # Normalize the context type to standard case
            context_type = match.group(1).capitalize()
            if context_type == 'Viewtype':
                context_type = 'ViewType'
            
            # Track context condition usage
            if context_type == 'View':
                self.context_counts['view'] += 1
            elif context_type == 'ViewType':
                self.context_counts['viewtype'] += 1
            elif context_type == 'Table':
                self.context_counts['table'] += 1
            self.context_counts['total'] += 1
            
            return context_type, match.group(2), match.group(3)
        
        # Check for LEFT function with CONTEXT
        left_pattern = r'LEFT\s*\(\s*CONTEXT\s*\(\s*"(View)"\s*\)\s*,\s*\d+\s*\)\s*(=|<>|!=)\s*"([^"]+)"'
        match = re.search(left_pattern, condition, re.IGNORECASE)
        if match:
            self.context_counts['view'] += 1
            self.context_counts['total'] += 1
            return match.group(1), match.group(2), match.group(3)
        
        return None, None, None
    
    def parse_if_expression(self, expression: str) -> List[Dict]:
        """Parse IF expressions with CONTEXT conditions."""
        targets = []
        
        # Find IF( and remove it
        if_match = re.match(r'^\s*=?\s*IF\s*\((.*)\)\s*$', expression, re.IGNORECASE | re.DOTALL)
        if not if_match:
            return targets
        
        content = if_match.group(1)
        
        # Split into condition, true_expr, false_expr by tracking parentheses
        parts = []
        current_part = []
        paren_depth = 0
        quote_char = None
        comma_count = 0  # Track how many top-level commas we've seen
        
        for i, char in enumerate(content):
            if quote_char:
                current_part.append(char)
                if char == quote_char and (i == 0 or content[i-1] != '\\'):
                    quote_char = None
            elif char in ['"', "'", chr(8220), chr(8221)]:
                current_part.append(char)
                # Don't track quotes inside function calls
                if paren_depth == 0:
                    quote_char = char
            elif char == '(':
                current_part.append(char)
                paren_depth += 1
            elif char == ')':
                current_part.append(char)
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                if comma_count < 2:  # Only split on first 2 commas
                    parts.append(''.join(current_part).strip())
                    current_part = []
                    comma_count += 1
                else:
                    current_part.append(char)
            else:
                current_part.append(char)
        
        # Add the last part
        if current_part:
            parts.append(''.join(current_part).strip())
        
        if len(parts) != 3:
            return targets
        
        condition = parts[0]
        true_expr = parts[1]
        false_expr = parts[2]
        
        # Check if condition contains OR
        if 'OR(' in condition.upper():
            # Extract all conditions from OR
            or_match = re.search(r'OR\s*\((.*)\)', condition, re.IGNORECASE | re.DOTALL)
            if or_match:
                or_content = or_match.group(1)
                # Find all CONTEXT conditions within the OR
                pattern = r'CONTEXT\s*\(\s*"(View|ViewType|Table|VIEW|VIEWTYPE|TABLE)"\s*\)\s*=\s*"([^"]+)"'
                matches = list(re.finditer(pattern, or_content, re.IGNORECASE))
                
                if matches:
                    # Collect all values for the OR condition
                    context_type = matches[0].group(1).capitalize()
                    if context_type == 'Viewtype':
                        context_type = 'ViewType'
                    
                    values = []
                    for match in matches:
                        value = match.group(2).strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
                        values.append(value)
                    
                    # Track context usage
                    if context_type == 'View':
                        self.context_counts['view'] += len(matches)
                    elif context_type == 'ViewType':
                        self.context_counts['viewtype'] += len(matches)
                    elif context_type == 'Table':
                        self.context_counts['table'] += len(matches)
                    self.context_counts['total'] += len(matches)
                    
                    # Parse true branch - must be in one of the OR'd values
                    true_targets = self.parse_navigation_expression(true_expr)
                    for target in true_targets:
                        if context_type == "View":
                            target['must_be_in_views'] = '|||'.join(values)
                        elif context_type == "ViewType":
                            target['must_be_viewtype'] = '|||'.join(values)
                        elif context_type == "Table":
                            target['must_be_table'] = '|||'.join(values)
                        targets.append(target)
                    
                    # Parse false branch - must NOT be in any of the OR'd values
                    false_targets = self.parse_navigation_expression(false_expr)
                    for target in false_targets:
                        if context_type == "View":
                            target['must_not_be_in_views'] = '|||'.join(values)
                        elif context_type == "ViewType":
                            target['must_not_be_viewtype'] = '|||'.join(values)
                        elif context_type == "Table":
                            target['must_not_be_table'] = '|||'.join(values)
                        targets.append(target)
                    
                    return targets
        
        # Original single condition logic continues here
        # Parse condition
        context_type, operator, value = self.parse_context_condition(condition)
        
        # If no CONTEXT condition found, check if branches contain navigation
        if not context_type:
            # Check if branches contain navigation
            has_nav_true = ('LINKTOVIEW' in true_expr.upper() or 'LINKTOROW' in true_expr.upper())
            has_nav_false = ('LINKTOVIEW' in false_expr.upper() or 'LINKTOROW' in false_expr.upper())
            
            if has_nav_true or has_nav_false:
                # This is a data-dependent condition with navigation outcomes
                # Parse branches that have navigation
                if has_nav_true:
                    true_targets = self.parse_navigation_expression(true_expr)
                    for target in true_targets:
                        target['view_match_pattern'] = f'data_dependent:{condition}'
                        target['view_match_type'] = 'data_dependent_true'
                        targets.append(target)
                
                if has_nav_false:
                    false_targets = self.parse_navigation_expression(false_expr)
                    for target in false_targets:
                        target['view_match_pattern'] = f'data_dependent:{condition}'
                        target['view_match_type'] = 'data_dependent_false'
                        targets.append(target)
                
                return targets
        
        # Strip quotes from the value if present
        if value:
            value = value.strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
        
        # Parse true branch
        true_targets = self.parse_navigation_expression(true_expr)
        for target in true_targets:
            if context_type == "View":
                if operator in ['=', '==']:
                    target['must_be_in_views'] = value
                elif operator in ['<>', '!=']:
                    target['must_not_be_in_views'] = value
            elif context_type == "ViewType":
                if operator in ['=', '==']:
                    target['must_be_viewtype'] = value
                elif operator in ['<>', '!=']:
                    target['must_not_be_viewtype'] = value
            elif context_type == "Table":
                if operator in ['=', '==']:
                    target['must_be_table'] = value
                elif operator in ['<>', '!=']:
                    target['must_not_be_table'] = value
            targets.append(target)
        
        # Parse false branch
        false_targets = self.parse_navigation_expression(false_expr)
        for target in false_targets:
            if context_type == "View":
                if operator in ['=', '==']:
                    target['must_not_be_in_views'] = value
                elif operator in ['<>', '!=']:
                    target['must_be_in_views'] = value
            elif context_type == "ViewType":
                if operator in ['=', '==']:
                    target['must_not_be_viewtype'] = value
                elif operator in ['<>', '!=']:
                    target['must_be_viewtype'] = value
            elif context_type == "Table":
                if operator in ['=', '==']:
                    target['must_not_be_table'] = value
                elif operator in ['<>', '!=']:
                    target['must_be_table'] = value
            targets.append(target)
        
        return targets
    
    def parse_ifs_expression(self, expression: str) -> List[Dict]:
        """Parse IFS expressions with multiple conditions."""
        targets = []
        
        # Remove leading =IFS( and trailing )
        ifs_match = re.match(r'^\s*=?\s*IFS\s*\((.*)\)\s*$', expression, re.IGNORECASE | re.DOTALL)
        if not ifs_match:
            return targets
        
        content = ifs_match.group(1)
        
        # Split by lines to handle the Session flag format
        lines = content.split('\n')
        
        # Track processed conditions to avoid duplicates
        processed_conditions = set()
        branch_index = 0  # Add this counter
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove trailing comma if present
            line = line.rstrip(',')
            
            # Try to parse each condition-action pair
            parts = self.split_condition_action(line)
            if len(parts) == 2:
                branch_index += 1  # Increment for each valid branch
                condition = parts[0].strip()
                action = parts[1].strip()
                
                # Parse the condition
                context_type, operator, value = self.parse_context_condition(condition)
                
                # Strip quotes from the value if present
                if value:
                    value = value.strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
                
                # Parse the navigation action
                nav_targets = self.parse_navigation_expression(action)
                
                for target in nav_targets:
                    if context_type == "View":
                        if operator in ['=', '==']:
                            # Positive condition - set must_be_in_views
                            target['must_be_in_views'] = value
                            # Don't set must_not_be_in_views when we have a positive requirement
                        elif operator in ['<>', '!=']:
                            # Negative condition - set must_not_be_in_views
                            target['must_not_be_in_views'] = value
                    elif context_type == "ViewType":
                        if operator in ['=', '==']:
                            target['must_be_viewtype'] = value
                        elif operator in ['<>', '!=']:
                            target['must_not_be_viewtype'] = value
                    elif context_type == "Table":
                        if operator in ['=', '==']:
                            target['must_be_table'] = value
                        elif operator in ['<>', '!=']:
                            target['must_not_be_table'] = value
                    # Add debug info
                    target['ifs_branch_index'] = branch_index  # Use the actual branch counter
                    target['ifs_branch_text'] = line
                    targets.append(target)
        
        return targets

    def split_condition_action(self, line: str) -> List[str]:
        """Split a condition-action pair, handling nested functions."""
        # Find the comma that separates condition from action
        # Need to handle nested parentheses
        paren_depth = 0
        quote_char = None
        
        for i, char in enumerate(line):
            if quote_char:
                if char == quote_char and (i == 0 or line[i-1] != '\\'):
                    quote_char = None
            elif char in ['"', "'"]:
                quote_char = char
            elif char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
            elif char == ',' and paren_depth == 0:
                return [line[:i], line[i+1:]]
        
        return [line]
    
    def parse_navigation_expression(self, expression: str) -> List[Dict]:
        """Parse any navigation expression."""
        if not expression:
            return []
        
        expression = expression.strip()
        
        # Check for direct navigation patterns first
        if '#control=' in expression or '#page=' in expression:
            return self.parse_direct_navigation(expression)
        
        # Skip simple column references - they're not navigation expressions
        if re.match(r'^\[[\w\s]+\]$', expression):
            return []  # Return empty list but don't mark as unparseable
        
        # Check for IFS BEFORE other functions (IFS can contain LINKTOVIEW/LINKTOROW)
        if expression.upper().startswith('=IFS') or expression.upper().startswith('IFS'):
            return self.parse_ifs_expression(expression)

        # Check for IF BEFORE other functions (IF can contain LINKTOVIEW/LINKTOROW)
        if expression.upper().startswith('=IF') or expression.upper().startswith('IF'):
            return self.parse_if_expression(expression)
                
        # Check for LINKTOVIEW
        if 'LINKTOVIEW' in expression.upper():
            return self.parse_linktoview(expression)
        
        # Check for LINKTOROW
        if 'LINKTOROW' in expression.upper():
            return self.parse_linktorow(expression)
        
        return []
    
    def process_action(self, row: Dict) -> List[Dict]:
        """Process a single action row and generate target records."""
        targets = []
        
        # Include navigation actions AND group actions (which may contain navigation)
        if row['action_type_technical_name'] not in ['go_to_view', 'Navigate', 'execute_group']:
            return targets
        
        # For group actions, we need to check referenced_actions
        if row['action_type_technical_name'] == 'execute_group':
            only_if_condition = row.get('only_if_condition', '').strip()
            self.count_only_if_contexts(only_if_condition)
            # Store group action info even without navigation target
            # Phase 2 will resolve which navigation actions it contains
            target = {
                'source_action': row['action_name'],
                'source_table': row.get('source_table', ''),  # NEW
                'action_type': row['action_type_technical_name'],
                'action_prominence': row.get('action_prominence', ''),  # NEW
                'attach_to_column': row.get('attach_to_column', '') if row.get('action_prominence') == 'Display_Inline' else '',  # NEW
                'target_view': '',  # Leave blank for group actions
                'target_row_expr': '',
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'view_match_pattern': '',
                'view_match_type': '',
                'only_if_condition': row.get('only_if_condition', ''),
                'referenced_actions': row.get('referenced_actions', ''),  # Store child actions for debugging
                'ifs_branch_index': '',  # Not applicable for group actions
                'ifs_branch_text': '',   # Not applicable for group actions
                'original_expression': ''  # Not applicable for group actions
            }
            
            # Parse only_if_condition if present - use same multi-condition logic
            only_if_condition = row.get('only_if_condition', '').strip()
            if only_if_condition and 'CONTEXT' in only_if_condition.upper():
                # Parse ALL CONTEXT conditions in the only_if_condition
                pattern = r'CONTEXT\s*\(\s*"(View|ViewType|Table|VIEW|VIEWTYPE|TABLE)"\s*\)\s*(=|<>|!=)\s*"([^"]+)"'
                
                view_must_be = []
                view_must_not_be = []
                viewtype_must_be = []
                viewtype_must_not_be = []
                table_must_be = []
                table_must_not_be = []
                
                for match in re.finditer(pattern, only_if_condition, re.IGNORECASE):
                    context_type = match.group(1).capitalize()
                    if context_type == 'Viewtype':
                        context_type = 'ViewType'
                    operator = match.group(2)
                    value = match.group(3).strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
                    
                    if context_type == "View":
                        if operator in ['=', '==']:
                            view_must_be.append(value)
                        elif operator in ['<>', '!=']:
                            view_must_not_be.append(value)
                    elif context_type == "ViewType":
                        if operator in ['=', '==']:
                            viewtype_must_be.append(value)
                        elif operator in ['<>', '!=']:
                            viewtype_must_not_be.append(value)
                    elif context_type == "Table":
                        if operator in ['=', '==']:
                            table_must_be.append(value)
                        elif operator in ['<>', '!=']:
                            table_must_not_be.append(value)
                
                # Join multiple conditions with |||
                if view_must_be:
                    target['must_be_in_views'] = '|||'.join(view_must_be)
                if view_must_not_be:
                    target['must_not_be_in_views'] = '|||'.join(view_must_not_be)
                if viewtype_must_be:
                    target['must_be_viewtype'] = '|||'.join(viewtype_must_be)
                if viewtype_must_not_be:
                    target['must_not_be_viewtype'] = '|||'.join(viewtype_must_not_be)
                if table_must_be:
                    target['must_be_table'] = '|||'.join(table_must_be)
                if table_must_not_be:
                    target['must_not_be_table'] = '|||'.join(table_must_not_be)
            
            # Add normalized columns
            target['source_action_normalized'] = self.normalize_value(target['source_action'])
            target['target_view_normalized'] = self.normalize_value(target['target_view'])
            target['must_be_in_views_normalized'] = self.normalize_value(target['must_be_in_views'])
            target['must_not_be_in_views_normalized'] = self.normalize_value(target['must_not_be_in_views'])
            target['must_be_table_normalized'] = self.normalize_value(target['must_be_table'])
            target['must_not_be_table_normalized'] = self.normalize_value(target['must_not_be_table'])
            
            targets.append(target)
            return targets
        
        # Get the navigation expression
        nav_expr = row.get('navigate_target', '').strip()
        if not nav_expr:
            return targets
        
        # Check if it's a column reference (silently skip)
        if re.match(r'^=?\[[\w\s]+\]$', nav_expr):
            return targets  # Skip without marking as unparseable
        
        # Parse the action's visibility condition FIRST
        only_if_condition = row.get('only_if_condition', '').strip()
        action_conditions = {
            'must_be_in_views': '',
            'must_not_be_in_views': '',
            'must_be_viewtype': '',
            'must_not_be_viewtype': '',
            'must_be_table': '',
            'must_not_be_table': ''
        }
        self.count_only_if_contexts(only_if_condition)

        if only_if_condition and 'CONTEXT' in only_if_condition.upper():
            # Check if this is an IF statement with true in one branch (data-dependent)
            # Pattern: IF(context_condition, something, true) or IF(context_condition, true, something)
            if_with_true_pattern = r'(?i)=?if\s*\(.*context.*,.*,\s*true\s*\)|=?if\s*\(.*context.*,\s*true\s*,.*\)'
            if re.search(if_with_true_pattern, only_if_condition):
                # This is a data-dependent condition - ignore CONTEXT for edge generation
                pass  # Leave action_conditions empty
            else:
                # Parse ALL CONTEXT conditions in the only_if_condition
                # Use finditer to find all CONTEXT patterns
                pattern = r'CONTEXT\s*\(\s*"(View|ViewType|Table|VIEW|VIEWTYPE|TABLE)"\s*\)\s*(=|<>|!=)\s*"([^"]+)"'
                
                view_must_be = []
                view_must_not_be = []
                viewtype_must_be = []
                viewtype_must_not_be = []
                table_must_be = []
                table_must_not_be = []
                
                for match in re.finditer(pattern, only_if_condition, re.IGNORECASE):
                    context_type = match.group(1).capitalize()
                    if context_type == 'Viewtype':
                        context_type = 'ViewType'
                    operator = match.group(2)
                    value = match.group(3).strip('"').strip("'").strip(chr(8220)).strip(chr(8221))
                    
                    if context_type == "View":
                        if operator in ['=', '==']:
                            view_must_be.append(value)
                        elif operator in ['<>', '!=']:
                            view_must_not_be.append(value)
                    elif context_type == "ViewType":
                        if operator in ['=', '==']:
                            viewtype_must_be.append(value)
                        elif operator in ['<>', '!=']:
                            viewtype_must_not_be.append(value)
                    elif context_type == "Table":
                        if operator in ['=', '==']:
                            table_must_be.append(value)
                        elif operator in ['<>', '!=']:
                            table_must_not_be.append(value)
                
                # Join multiple conditions with |||
                if view_must_be:
                    action_conditions['must_be_in_views'] = '|||'.join(view_must_be)
                if view_must_not_be:
                    action_conditions['must_not_be_in_views'] = '|||'.join(view_must_not_be)
                if viewtype_must_be:
                    action_conditions['must_be_viewtype'] = '|||'.join(viewtype_must_be)
                if viewtype_must_not_be:
                    action_conditions['must_not_be_viewtype'] = '|||'.join(viewtype_must_not_be)
                if table_must_be:
                    action_conditions['must_be_table'] = '|||'.join(table_must_be)
                if table_must_not_be:
                    action_conditions['must_not_be_table'] = '|||'.join(table_must_not_be)
        
        # Parse the expression
        parsed = self.parse_navigation_expression(nav_expr)
        
        if not parsed:
            # Record unparseable expression with full row data
            unparseable_record = row.copy()  # Preserve all original columns
            unparseable_record['parse_failure_reason'] = self.classify_parse_failure(nav_expr)
            unparseable_record['expression_attempted'] = nav_expr
            self.unparseable.append(unparseable_record)
            return targets
        
        # Create target records
        for target_info in parsed:
            # Merge action-level conditions with expression-level conditions
            # Using ||| separator for multiple conditions
            def merge_conditions(action_cond, expr_cond):
                if action_cond and expr_cond:
                    return f"{action_cond}|||{expr_cond}"
                return action_cond or expr_cond
            
            target = {
                'source_action': row['action_name'],
                'source_table': row.get('source_table', ''),  # NEW
                'action_type': row['action_type_technical_name'],
                'action_prominence': row.get('action_prominence', ''),  # NEW
                'attach_to_column': row.get('attach_to_column', '') if row.get('action_prominence') == 'Display_Inline' else '',  # NEW
                'target_view': target_info['target_view'],
                'target_row_expr': target_info['target_row_expr'],
                'only_if_condition': only_if_condition,  # Store the original condition
                'must_be_in_views': merge_conditions(
                    action_conditions['must_be_in_views'], 
                    target_info['must_be_in_views']
                ),
                'must_not_be_in_views': merge_conditions(
                    action_conditions['must_not_be_in_views'], 
                    target_info['must_not_be_in_views']
                ),
                'must_be_viewtype': merge_conditions(
                    action_conditions['must_be_viewtype'], 
                    target_info['must_be_viewtype']
                ),
                'must_not_be_viewtype': merge_conditions(
                    action_conditions['must_not_be_viewtype'], 
                    target_info['must_not_be_viewtype']
                ),
                'must_be_table': merge_conditions(
                    action_conditions['must_be_table'], 
                    target_info['must_be_table']
                ),
                'must_not_be_table': merge_conditions(
                    action_conditions['must_not_be_table'], 
                    target_info['must_not_be_table']
                ),
                'ifs_branch_index': target_info.get('ifs_branch_index', ''),  # Empty if not from IFS
                'ifs_branch_text': target_info.get('ifs_branch_text', ''),   # Empty if not from IFS
                'view_match_pattern': target_info['view_match_pattern'],
                'view_match_type': target_info['view_match_type'],
                'referenced_actions': '',  # Empty for non-group actions
                'original_expression': nav_expr
            }
            
            # Add normalized columns
            target['source_action_normalized'] = self.normalize_value(target['source_action'])
            target['target_view_normalized'] = self.normalize_value(target['target_view'])
            target['must_be_in_views_normalized'] = self.normalize_value(target['must_be_in_views'])
            target['must_not_be_in_views_normalized'] = self.normalize_value(target['must_not_be_in_views'])
            target['must_be_table_normalized'] = self.normalize_value(target['must_be_table'])
            target['must_not_be_table_normalized'] = self.normalize_value(target['must_not_be_table'])
            
            targets.append(target)
        
        return targets
    
    def write_unparseable_csv(self, output_file: str):
        """Write unparseable expressions to a separate CSV file."""
        if not self.unparseable:
            return
        
        # Determine output filename
        base_name = output_file.rsplit('.', 1)[0] if '.' in output_file else output_file
        unparseable_file = f"{base_name}_unparseable.csv"
        
        # Use the same fieldnames as the input appsheet_actions.csv
        # plus our additional tracking fields
        fieldnames = [
            'action_name', 'source_table', 'action_type_plain_english', 
            'action_type_technical_name', 'referenced_columns', 'referenced_actions',
            'action_prominence', 'navigate_target', 'referenced_views', 
            'attach_to_column', 'modifies_data', 'only_if_condition',
            'display_name', 'action_icon', 'needs_confirmation', 
            'bulk_applicable', 'column_to_edit', 'to_this_value',
            'with_these_properties', 'raw_references', 'is_system_generated',
            'parse_failure_reason', 'expression_attempted'
        ]
        
        # Write CSV
        with open(unparseable_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(self.unparseable)
        
    def get_action_counts(self):
        """Return categorized counts of loaded actions."""
        return self.action_counts
    
    def get_target_counts(self):
        """Return counts of parsed navigation targets by type."""
        return self.target_counts
    
    def get_context_counts(self):
        """Return counts of context conditions by type."""
        return self.context_counts
    
    def get_unparseable_counts(self):
        """Return counts of unparseable expressions by reason."""
        counts = {}
        for expr in self.unparseable:
            reason = expr.get('parse_failure_reason', 'Unknown')
            counts[reason] = counts.get(reason, 0) + 1
        return counts
    
    def parse_actions_csv(self, input_file: str, output_file: str):
        """Parse actions CSV and generate action_targets CSV."""
        
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            for row in reader:
                # Count actions by type
                self.action_counts['total'] += 1
                action_type = row.get('action_type_technical_name', '')
                
                if action_type == 'go_to_view':
                    self.action_counts['navigation'] += 1
                elif action_type == 'execute_group':
                    self.action_counts['group'] += 1
                elif action_type == 'open_url':
                    self.action_counts['external_url'] += 1
                elif row.get('action_type_plain_english', '') in ['Write', 'Delete', 'Add row', 'Edit', 'Add new row']:
                    self.action_counts['data_modifications'] += 1
                else:
                    self.action_counts['other'] += 1
                
                targets = self.process_action(row)
                self.parsed_targets.extend(targets)
        
        # Write output CSV
        if self.parsed_targets:
            fieldnames = [
                # Primary columns
                'source_action',
                'source_table',  # NEW
                'action_type',
                'action_prominence',  # NEW
                'attach_to_column',  # NEW
                'target_view',
                'target_row_expr',
                'only_if_condition',
                'must_be_in_views', 'must_not_be_in_views',
                'must_be_viewtype', 'must_not_be_viewtype',
                'must_be_table', 'must_not_be_table',
                'ifs_branch_index',  # Which branch of IFS generated this row
                'ifs_branch_text',   # The actual branch text for debugging
                'view_match_pattern', 'view_match_type',
                'referenced_actions',  # Added for debugging group actions
                'original_expression',
                # Normalized columns
                'source_action_normalized', 'target_view_normalized',
                'must_be_in_views_normalized', 'must_not_be_in_views_normalized',
                'must_be_table_normalized', 'must_not_be_table_normalized'
            ]
            
            with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(self.parsed_targets)
        
        # Write unparseable expressions CSV
        self.write_unparseable_csv(output_file)
        
        # Return statistics for integration
        return {
            'targets_count': len(self.parsed_targets),
            'unparseable_count': len(self.unparseable),
            'action_counts': self.action_counts,
            'target_counts': self.target_counts,
            'context_counts': self.context_counts,
            'unparseable_counts': self.get_unparseable_counts()
        }

def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python action_target_parser.py <input_actions.csv> <output_targets.csv>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    parser = NavigationExpressionParser()
    
    # Load views CSV if it exists in same directory as actions CSV
    input_dir = os.path.dirname(input_file)
    views_file = os.path.join(input_dir, 'appsheet_views.csv')
    parser.load_views_csv(views_file)
    
    parser.parse_actions_csv(input_file, output_file)

    