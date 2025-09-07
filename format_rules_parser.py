#!/usr/bin/env python3
"""
Format Rules Parser for AppSheet HTML Documentation
Extracts format rule information and tracks column/action references.
Handles apps with or without format rules gracefully.
"""

import csv
import os
import re
import json
from base_parser import BaseParser


class FormatRulesParser(BaseParser):
    """Parser specifically for AppSheet format rules."""
    
    def __init__(self, html_path=None, html_string=None, soup=None, debug_mode=False):
        super().__init__(html_path, html_string, soup, debug_mode=debug_mode)
        self.format_rules_data = []
        
        # Load slice mapping if available
        self.load_slice_mapping()
        
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
    
    def parse_formatted_items(self, formatted_items_cell):
        """
        Parse columns and actions from HTML cell containing <ol><li> structure.
        Returns a tuple of (columns_list, actions_list).
        
        Items can be:
        - Column names
        - Action names (often prefixed with __action__)
        """
        columns = []
        actions = []
        if not formatted_items_cell:
            return ([], [])
            
        # First, try to find ordered list structure
        ol_element = formatted_items_cell.find('ol')
        if ol_element:
            # Extract each <li> element separately
            items = ol_element.find_all('li')
            
            for li in items:
                item_text = li.get_text(strip=True)
                if item_text:
                    if item_text.startswith('__action__'):
                        action_name = item_text.replace('__action__', '', 1).strip()
                        actions.append(action_name)
                    else:
                        columns.append(item_text)            
            if columns or actions:
                return (columns, actions)
        
        # Try unordered list as backup
        ul_element = formatted_items_cell.find('ul')
        if ul_element:
            items = ul_element.find_all('li')
            
            for li in items:
                item_text = li.get_text(strip=True)
                if item_text:
                    if item_text.startswith('__action__'):
                        action_name = item_text.replace('__action__', '', 1).strip()
                        actions.append(action_name)
                    else:
                        columns.append(item_text)
                                    
            if columns or actions:
                return (columns, actions)
        
        # Fallback to text extraction if no list structure found
        text = formatted_items_cell.get_text(strip=True)
        if text:
            # Try to split by ||| if present
            if '|||' in text:
                items = text.split('|||')
            else:
                items = [text]
            
            for item in items:
                item = item.strip()
                if item:
                    if item.startswith('__action__'):
                        action_name = item.replace('__action__', '', 1).strip()
                        actions.append(action_name)
                    else:
                        columns.append(item)
        
        return (columns, actions)
    
    def extract_settings_data(self, settings_json):
        """
        Extract human-readable settings from the JSON settings field.
        Returns a formatted string of settings for easy understanding.
        """
        if not settings_json:
            return ''
            
        try:
            settings = json.loads(settings_json)
            
            readable_parts = []
            
            # Text formatting
            if settings.get('textColor'):
                readable_parts.append(f"Text: {settings['textColor']}")
            if settings.get('highlightColor'):
                readable_parts.append(f"Highlight: {settings['highlightColor']}")
            if settings.get('textSize') and settings['textSize'] != 1.0:
                readable_parts.append(f"Size: {settings['textSize']}")
            
            # Text styles
            styles = []
            if settings.get('bold'):
                styles.append('Bold')
            if settings.get('italic'):
                styles.append('Italic')
            if settings.get('underline'):
                styles.append('Underline')
            if settings.get('strikethrough'):
                styles.append('Strikethrough')
            if settings.get('uppercase'):
                styles.append('Uppercase')
            
            if styles:
                readable_parts.append(f"Style: {', '.join(styles)}")
            
            # Icon
            if settings.get('icon'):
                readable_parts.append(f"Icon: {settings['icon']}")
            
            # Image size
            if settings.get('imageSize'):
                readable_parts.append(f"Image size: {settings['imageSize']}")
            
            return ' | '.join(readable_parts) if readable_parts else 'No formatting'
            
        except (json.JSONDecodeError, TypeError):
            return 'Invalid settings'
    
    def parse(self):
        """
        Extract all format rules from the HTML.
        Returns a list of dictionaries containing format rule information.
        """
        print("🎨 Extracting format rules...")
        
        # Find all format rule headers - they contain "Rule name" in the label
        rule_headers = self.soup.find_all('h5', id=lambda x: x and x.startswith('view'))
        
        # Filter to only those that are actually format rules
        format_rule_headers = []
        for header in rule_headers:
            label = header.find('label')
            if label and 'Rule name' in label.get_text():
                format_rule_headers.append(header)
        
        if not format_rule_headers:
            print("  ℹ️  No format rules found in this app")
            return self.format_rules_data
        
        for rule_header in format_rule_headers:
            rule_table = rule_header.find_next('table')
            if rule_table and not self.is_element_processed(rule_header.get('id')):
                rule_info = self._extract_format_rule_data(rule_table, rule_header)
                
                if rule_info:
                    self.format_rules_data.append(rule_info)
                    self.mark_element_processed(rule_header.get('id'))
        
        print(f"  ✓ Found {len(self.format_rules_data)} format rules")
        
        # Print summary with statistics
        if self.format_rules_data:
            self._print_summary()
                
        return self.format_rules_data
    
    def _extract_format_rule_data(self, table_element, rule_header):
        """Extract data specific to a format rule."""
        # Get rule name from header
        rule_name = rule_header.get_text(strip=True)
        if rule_name.startswith('Rule name'):
            rule_name = rule_name.replace('Rule name', '').strip()
        
        # Get base component data
        rule_info = {'rule_name': rule_name}
        
        # Track the table/slice this rule applies to
        condition_formula = None
        formatted_items_cell = None
        settings_json = None
        
        # Extract data from table rows
        for row in table_element.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                label = cells[0].get_text(strip=True).lower()
                value = cells[1].get_text(strip=True)
                
                # Store based on label
                if 'for this data' in label:
                    rule_info['source_table'] = value
                elif 'format these columns' in label:
                    # Store the cell element for proper parsing
                    formatted_items_cell = cells[1]
                elif 'if this condition' in label:
                    condition_formula = value
                    rule_info['condition'] = value
                elif 'rule order' in label:
                    rule_info['rule_order'] = value
                elif 'disabled' in label:
                    rule_info['is_disabled'] = value
                elif 'like this' in label:
                    settings_json = value
                    rule_info['settings'] = value
                elif 'visible' in label:
                    rule_info['visible'] = value
                elif 'comment' in label:
                    rule_info['comment'] = value
        
        # Parse formatted items (columns and actions) from HTML structure
        if formatted_items_cell:
            columns, actions = self.parse_formatted_items(formatted_items_cell)
            
            # Create the new separated fields
            rule_info['formatted_columns'] = '|||'.join(columns)
            rule_info['formatted_actions'] = '|||'.join(actions)
            
            # Keep the old formatted_items field for backward compatibility
            all_items = []
            for col in columns:
                all_items.append(col)
            for act in actions:
                all_items.append(f'__action__{act}')
            rule_info['formatted_items'] = '|||'.join(all_items)
            
            # Update counts
            rule_info['formatted_columns_count'] = len(columns)
            rule_info['formatted_actions_count'] = len(actions)
        else:
            rule_info['formatted_items'] = ''
            rule_info['formatted_columns'] = ''
            rule_info['formatted_actions'] = ''
            rule_info['formatted_columns_count'] = 0
            rule_info['formatted_actions_count'] = 0
        
        # Extract human-readable settings
        if settings_json:
            rule_info['readable_settings'] = self.extract_settings_data(settings_json)
        else:
            rule_info['readable_settings'] = ''
        
        rule_info['formula_context_table'] = rule_info.get('source_table')
        
        # Extract references from the condition formula
        all_refs = []
        if condition_formula and condition_formula not in ['', '=true', '=false']:
            refs = self.extract_references_from_text(condition_formula, rule_info.get('source_table'))
            all_refs.extend(refs)
            
            # Store raw references
            raw_refs = [ref['raw'] for ref in refs]
            if raw_refs:
                rule_info['raw_references'] = ' | '.join(raw_refs)
        
        # Build absolute references from condition formula only
        if all_refs:
            absolute_refs = self.build_absolute_references(all_refs)
            rule_info['referenced_columns'] = '|||'.join(absolute_refs)
        else:
            rule_info['referenced_columns'] = ''
        
        return rule_info
    
    def _print_summary(self):
        """Print a summary of the parsed format rules."""
        print(f"\n  📊 Format Rules Summary:")
        
        # Count by table
        table_counts = {}
        total_column_formats = 0
        total_action_formats = 0
        
        for rule in self.format_rules_data:
            table = rule.get('source_table', 'Unknown')
            table_counts[table] = table_counts.get(table, 0) + 1
            total_column_formats += rule.get('formatted_columns_count', 0)
            total_action_formats += rule.get('formatted_actions_count', 0)
        
        # Print by table
        for table, count in sorted(table_counts.items()):
            print(f"    {table}: {count} rules")
        
        print(f"\n    Total formatting targets:")
        print(f"      Columns: {total_column_formats}")
        print(f"      Actions: {total_action_formats}")
        
        # Count disabled rules
        disabled_count = sum(1 for rule in self.format_rules_data 
                           if rule.get('is_disabled', '').lower() == 'yes')
        if disabled_count:
            print(f"    ⚠️  Disabled rules: {disabled_count}")
    
    def get_field_order(self):
        """
        Define the field order for format rules CSV output.
        """
        priority_fields = [
            'rule_name',
            'source_table',
            'referenced_columns',
            'formatted_columns',
            'formatted_actions',
            'formatted_items',
            'formatted_columns_count',
            'formatted_actions_count',
            'condition',
            'readable_settings',
            'is_disabled',
            'settings',
            'comment',
            'raw_references'
        ]
        
        # Get all unique fields from parsed data
        all_fields = set()

        # Exclude fields that only contain .NET type names
        excluded_fields = {'rule_order', 'visible', 'formula_context_table'}
        
        for rule_data in self.format_rules_data:
            all_fields.update(rule_data.keys())
        
        # Use ALL priority fields (for consistent CSV structure)
        
        # Add any remaining fields not in priority list
        other_fields = sorted([f for f in all_fields if f not in priority_fields and f not in excluded_fields])
        
        return priority_fields + other_fields
    
    def save_to_csv(self, output_path=None, filename='appsheet_format_rules.csv'):
        """Save parsed format rule data to CSV file."""
        if not self.format_rules_data:
            print("  ⚠️  No format rules found - creating empty format rules file")
            # Create empty CSV with headers so other parsers can still run
            if output_path is None:
                csv_path = filename
            else:
                csv_path = os.path.join(output_path, filename)
                
            # Write empty CSV with minimal headers
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)  # Add this!
                writer.writerow(['rule_name', 'source_table', 'formatted_columns', 'formatted_actions', 'formatted_items'])
                
            print(f"  ✅ Empty format rules file saved to: {csv_path}")
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
            writer.writerows(self.format_rules_data)
            
        print(f"  ✅ Format rules saved to: {output_path}")

def main():
    """Main function to run the format rules parser."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python format_rules_parser.py <html_file_path> [--debug]")
        sys.exit(1)
        
    html_path = sys.argv[1]
    debug_mode = '--debug' in sys.argv
    
    if not os.path.exists(html_path):
        print(f"❌ Error: File not found: {html_path}")
        sys.exit(1)
        
    print("🎨 AppSheet Format Rules Parser")
    if debug_mode:
        print("   🐛 DEBUG MODE ENABLED")
    print("=" * 50)
    
    parser = FormatRulesParser(html_path, debug_mode=debug_mode)
    
    try:
        parser.parse()
        parser.save_to_csv()
        
        print("\n✅ Format rules parsing complete!")
        
    except Exception as e:
        print(f"\n❌ Error during parsing: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()