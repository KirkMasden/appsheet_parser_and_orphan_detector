#!/usr/bin/env python3
"""
Slice Parser for AppSheet HTML Documentation
Extracts slice information and properly resolves slice references to source tables.
Includes improved action separation and FIXED slice column parsing.
"""

import csv
import os
import re
from base_parser import BaseParser


class SliceParser(BaseParser):
    """Parser specifically for AppSheet slices."""
    
    def __init__(self, html_path=None, html_string=None, soup=None):
        super().__init__(html_path, html_string, soup)
        self.slices_data = []

    def extract_all_tables(self):
        """
        Extract ALL tables from the HTML, including system and process tables.
        Returns a dictionary with table names as keys and column counts as values.
        """
        tables = {}
        
        # Find all table headers - just the actual tables, not schemas
        table_headers = self.soup.find_all('h5', id=lambda x: x and x.startswith('table_') and not x.endswith('_Schema'))
        
        for header in table_headers:
            # Extract table name from the id attribute
            table_id = header.get('id', '')
            table_name = table_id.replace('table_', '')
            
            # Find the next schema section after this table
            # Look for the corresponding schema header
            schema_id = f"table_{table_name}_Schema"
            schema_header = self.soup.find('h5', id=schema_id)
            
            if schema_header:
                
                # Get all text content from this schema section to the next table
                schema_text = ''
                current = schema_header
                while current:
                    current = current.find_next_sibling()
                    if not current:
                        break
                    if current.name == 'h5' and current.get('id', '').startswith('table_'):
                        break
                    schema_text += current.get_text() + ' '
                
                # Find all "Column X:" patterns in the accumulated text
                import re
                matches = re.findall(r'Column (\d+):', schema_text)
                if matches:
                    column_count = max(int(m) for m in matches)
                else:
                    column_count = 0
                    
                tables[table_name] = column_count
            else:
                # No schema section found, set to 0
                tables[table_name] = 0
        
        return tables

    def print_complete_table_summary(self, regular_tables, system_tables, process_tables):
        """Print complete table summary with column counts."""
        print(f"\n  📊 Complete Table Summary:\n")
        
        # Regular tables
        if regular_tables:
            regular_total = sum(regular_tables.values())
            print(f"  📁 Regular Tables: {len(regular_tables)} ({regular_total:,} columns total)")
            for table_name, col_count in sorted(regular_tables.items()):
                print(f"     ├─ {table_name}: {col_count} columns")
        
        # System tables
        if system_tables:
            system_total = sum(system_tables.values())
            print(f"\n  📁 System Table: {len(system_tables)} ({system_total:,} columns total)")
            for table_name, col_count in sorted(system_tables.items()):
                print(f"     └─ {table_name}: {col_count} columns")
        
        # Process tables
        if process_tables:
            process_total = sum(process_tables.values())
            print(f"\n  📁 Process Tables: {len(process_tables)} ({process_total:,} columns total)")
            for i, (table_name, col_count) in enumerate(sorted(process_tables.items())):
                is_last = i == len(process_tables) - 1
                prefix = "└─" if is_last else "├─"
                print(f"     {prefix} {table_name}: {col_count} columns")
        
       # Total
        total_columns = sum(regular_tables.values()) + sum(system_tables.values()) + sum(process_tables.values())
        print(f"\n  📊 Total number of columns: {total_columns:,} ✓")
        print(f"  📊 Total number of tables: {len(regular_tables) + len(system_tables) + len(process_tables)} ✓")

    def parse_slice_columns(self, slice_columns_cell):
        """
        Parse slice columns from HTML cell containing <ol><li> structure.
        Returns comma-separated list of column names.
        
        Args:
            slice_columns_cell: BeautifulSoup element containing the cell
        """
        if not slice_columns_cell:
            return ''
            
        # First, try to find ordered list structure
        ol_element = slice_columns_cell.find('ol')
        if ol_element:
            # Extract each <li> element separately
            column_items = ol_element.find_all('li')
            column_names = []
            
            for li in column_items:
                column_text = li.get_text(strip=True)
                if column_text:
                    column_names.append(column_text)
            
            if column_names:
                return '|||'.join(column_names)
        
        # Try unordered list as backup
        ul_element = slice_columns_cell.find('ul')
        if ul_element:
            column_items = ul_element.find_all('li')
            column_names = []
            
            for li in column_items:
                column_text = li.get_text(strip=True)
                if column_text:
                    column_names.append(column_text)
            
            if column_names:
                return '|||'.join(column_names)
        
        # Fallback to text extraction if no list structure found
        text = slice_columns_cell.get_text(strip=True)
        if not text:
            return ''
        
        # Try to split on common patterns if no proper structure
        if ',' in text:
            columns = [col.strip() for col in text.split(',') if col.strip()]
            return '|||'.join(columns)
        
        # If no commas, might be concatenated - try to detect patterns
        # Look for patterns like "ColumnName1ColumnName2" where capital letters start new columns
        if text and ',' not in text:
            # Try to split on capital letters that follow lowercase letters
            # This is a heuristic - adjust based on your actual data patterns
            import re
            # Split on capital letter that follows a lowercase letter or digit
            potential_splits = re.split(r'(?<=[a-z0-9])(?=[A-Z])', text)
            if len(potential_splits) > 1:
                # Clean up the splits
                columns = [col.strip() for col in potential_splits if col.strip()]
                return '|||'.join(columns)
        
        # Return as-is if no patterns detected
        return text
        
    def parse_slice_actions(self, actions_text):
        """
        Parse slice actions from raw text into a clean, comma-separated list.
        
        Actions can be separated by various patterns:
        - Comma followed by space
        - Direct concatenation (no separator)
        - Mixed separators
        
        Returns: Clean comma-separated string of action names
        """
        if not actions_text or not actions_text.strip():
            return ''
            
        # Clean up the text
        actions_text = actions_text.strip()
        
        # Try different separation strategies
        actions = []
        
        # Strategy 1: Split on commas first (most reliable)
        if ',' in actions_text:
            # Split on commas and clean each part
            potential_actions = [action.strip() for action in actions_text.split(',')]
            actions.extend([action for action in potential_actions if action])
        else:
            # Strategy 2: Look for patterns that suggest action boundaries
            # Actions often have patterns like:
            # - "Action Name (context)"
            # - "Action Name" followed by capital letter
            # - Numbers at the end suggesting separate actions
            
            # For now, if no commas, treat as single action or try to split on common patterns
            # This is where you might need to refine based on actual data patterns
            
            # Look for parenthetical expressions that might indicate separate actions
            paren_pattern = r'([^()]+(?:\([^)]*\))?)'
            matches = re.findall(paren_pattern, actions_text)
            
            if len(matches) > 1:
                actions.extend([match.strip() for match in matches if match.strip()])
            else:
                # Fall back to treating the whole thing as one action
                actions.append(actions_text)
        
        # Clean up action names
        cleaned_actions = []
        for action in actions:
            action = action.strip()
            if action:
                # Remove any leading/trailing punctuation that might be artifacts
                action = re.sub(r'^[^\w]+|[^\w\s)]+$', '', action).strip()
                if action:
                    cleaned_actions.append(action)
        
        # Remove duplicates while preserving order
        unique_actions = []
        seen = set()
        for action in cleaned_actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)
        
        return '|||'.join(unique_actions)
        
    def parse(self):
        """
        Extract all slices from the HTML.
        Returns a list of dictionaries containing slice information.
        """
        print("📊 Extracting data sources...")

        # First, extract ALL tables for complete transparency
        all_tables = self.extract_all_tables()
        
        # Categorize tables
        regular_tables = {}
        system_tables = {}
        process_tables = {}
        
        for table_name, col_count in all_tables.items():
            if table_name.startswith('_') or table_name.startswith('*'):
                system_tables[table_name] = col_count
            elif 'Process' in table_name or 'Output' in table_name:
                process_tables[table_name] = col_count
            else:
                regular_tables[table_name] = col_count
        
        # Print complete table summary
        print(f"  ✓ Found {len(all_tables)} tables ({len(regular_tables)} regular, {len(system_tables)} system, {len(process_tables)} process)")
        self.print_complete_table_summary(regular_tables, system_tables, process_tables)
        self.regular_tables_column_total = sum(regular_tables.values())
        
        # Find all slice headers
        slice_headers = self.soup.find_all('h5', id=lambda x: x and x.startswith('slice_'))
        
        for slice_header in slice_headers:
            slice_table = slice_header.find_next('table')
            if slice_table and not self.is_element_processed(slice_header.get('id')):
                slice_info = self._extract_slice_data(slice_table, slice_header)
                
                if slice_info:
                    self.slices_data.append(slice_info)
                    self.mark_element_processed(slice_header.get('id'))
                    
        # After parsing all slices, build the slice-to-table map
        self._build_slice_to_table_map()
        
        # Now re-process references to resolve slice names
        self._resolve_slice_references()
        
        # Print slice mapping for debugging
        if self.slice_to_table_map:
            print(f"  📋 Loaded {len(self.slice_to_table_map)} slice-to-table mappings")
                
        return self.slices_data
        
    def _extract_slice_data(self, table_element, slice_header):
        """Extract data specific to a slice with improved column parsing."""
        # Get base component data using the parent method
        slice_info = self.extract_component_data(table_element, 'slice')
        
        # Get slice name from header
        slice_name = slice_header.get_text(strip=True)
        if slice_name.startswith('Slice Name'):
            slice_name = slice_name.replace('Slice Name', '').strip()
        slice_info['slice_name'] = slice_name
        
        # Track slice source table for context
        source_table = slice_info.get('source_table', '')
        if source_table:
            slice_info['formula_context_table'] = source_table
            
        # FIXED: Process slice columns with proper HTML parsing
        # We need to find the actual cell element, not use the extracted text
        slice_columns_cell = None
        for row in table_element.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                label = cells[0].get_text(strip=True).lower()
                if 'slice' in label and 'column' in label:
                    slice_columns_cell = cells[1]
                    break
        
        if slice_columns_cell:
            # Parse the HTML structure directly
            parsed_columns = self.parse_slice_columns(slice_columns_cell)
            slice_info['slice_columns'] = parsed_columns
        elif 'slice_columns' in slice_info:
            # Fallback: try to clean up the text if we already have it
            raw_columns = slice_info['slice_columns']
            if raw_columns and ',' not in raw_columns:
                # Attempt basic cleanup for concatenated text
                # This is a last resort and may not work well
                slice_info['slice_columns'] = raw_columns
            
        # Process slice actions with proper HTML parsing
        slice_actions_cell = None
        for row in table_element.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                label = cells[0].get_text(strip=True).lower()
                if 'slice' in label and 'action' in label:
                    slice_actions_cell = cells[1]
                    break

        if slice_actions_cell:
            # Parse the HTML structure directly (same approach as slice columns)
            parsed_actions = self.parse_slice_columns(slice_actions_cell)
            slice_info['slice_actions'] = parsed_actions
        elif 'slice_actions' in slice_info:
            # Fallback if we already have it but no cell found
            raw_actions = slice_info['slice_actions']
            parsed_actions = self.parse_slice_actions(raw_actions)
            slice_info['slice_actions'] = parsed_actions            

        # Re-extract references from row filter condition with proper context
        if slice_info.get('row_filter_condition') and source_table:
            refs = self.extract_references_from_text(
                slice_info['row_filter_condition'],
                source_table
            )
            
            # Store these references globally for the orphan detector
            for ref in refs:
                ref['source_field'] = 'row_filter_condition'
                ref['source_component'] = f"Slice:{slice_info.get('slice_name', '')}"
                self.all_references.append(ref)
                
        return slice_info
        
    def _build_slice_to_table_map(self):
        """Build mapping of slice names to their source tables."""
        for slice_data in self.slices_data:
            slice_name = slice_data.get('slice_name', '')
            source_table = slice_data.get('source_table', '')
            
            if slice_name and source_table:
                self.slice_to_table_map[slice_name] = source_table
                
    def _resolve_slice_references(self):
        """
        Re-process all slice data to resolve slice references in formulas.
        This must be done after all slices are parsed so we have the complete mapping.
        """
        for slice_data in self.slices_data:
            # Re-process row filter condition
            if slice_data.get('row_filter_condition'):
                context_table = slice_data.get('source_table', '')
                refs = self.extract_references_from_text(
                    slice_data['row_filter_condition'],
                    context_table
                )
                
                # Rebuild referenced columns with resolved references
                if refs:
                    absolute_refs = self.build_absolute_references(refs)
                    slice_data['referenced_columns'] = '|||'.join(absolute_refs)
                else:
                    slice_data['referenced_columns'] = ''
                    
            # Re-process slice columns if they contain references
            if slice_data.get('slice_columns'):
                # Slice columns might reference other slices
                refs = self.extract_references_from_text(
                    slice_data['slice_columns'],
                    slice_data.get('source_table', '')
                )
                
                if refs:
                    # Add to existing referenced columns
                    existing = slice_data.get('referenced_columns', '')
                    absolute_refs = self.build_absolute_references(refs)
                    all_refs = existing.split('|||') if existing else []
                    all_refs.extend(absolute_refs)
                    # Remove duplicates while preserving order
                    unique_refs = []
                    seen = set()
                    for ref in all_refs:
                        if ref and ref not in seen:
                            seen.add(ref)
                            unique_refs.append(ref)
                    slice_data['referenced_columns'] = '|||'.join(unique_refs)
                    
    def get_field_order(self):
        """
        Define the field order for slice CSV output.
        Updated to match the agreed-upon order.
        """
        # Updated priority fields order
        priority_fields = [
            'slice_name',
            'source_table',
            'referenced_columns',
            'row_filter_condition',
            'slice_columns',
            'slice_actions',
            'formula_context_table',
            'update_mode',
            'visible',
            'raw_references'
        ]
        
        # Get all unique fields from parsed data
        all_fields = set()
        for slice_data in self.slices_data:
            all_fields.update(slice_data.keys())
            
        # Remove component_type since it's redundant in a slices-only file
        all_fields.discard('component_type')
        
        # Use ALL priority fields (for consistent CSV structure)
        
        # Add any remaining fields not in priority list
        other_fields = sorted([f for f in all_fields if f not in priority_fields])
        
        return priority_fields + other_fields
        
    def save_to_csv(self, output_path=None, filename='appsheet_slices.csv'):
        """Save parsed slice data to CSV file."""
        if not self.slices_data:
            print("  ⚠️  No slices found - creating empty slice mapping file")
            # Create empty CSV with headers so column parser can still run
            if output_path is None:
                csv_path = filename
            else:
                csv_path = os.path.join(output_path, filename)
                
            # Write empty CSV with just headers
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)  # Add this!
                writer.writerow(['slice_name', 'source_table'])  # Minimal headers
                
            print(f"  ✅ Empty slice mapping saved to: {csv_path}")
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
            writer.writerows(self.slices_data)
            
        print(f"  ✅ Slices saved to: {filename}")
        
        # Print hierarchical summary
        self.print_hierarchical_summary()

    def print_hierarchical_summary(self):
        """Print a hierarchical summary of slices grouped by source table."""
        print(f"\n  📊 Regular tables to be analyzed (system and process tables excluded):\n")
        
        # Group slices by source table
        table_to_slices = {}
        for slice_data in self.slices_data:
            source_table = slice_data.get('source_table', 'Unknown')
            if source_table not in table_to_slices:
                table_to_slices[source_table] = []
            table_to_slices[source_table].append(slice_data)
        
        # Count total tables (including those without slices if we knew about them)
        # For now, just count tables that have slices
        print(f"  📁 Number of tables: {len(table_to_slices)}")
        
        # Sort tables by name for consistent output
        sorted_tables = sorted(table_to_slices.items())
        
        # Print each table and its slices
        for i, (table_name, slices) in enumerate(sorted_tables):
            # Determine if this is the last table for proper tree characters
            is_last_table = (i == len(sorted_tables) - 1)
            table_prefix = "   └─ " if is_last_table else "   ├─ "
            
            # Use singular/plural correctly
            slice_word = "slice" if len(slices) == 1 else "slices"
            print(f"{table_prefix}{table_name} ({len(slices)} {slice_word})")
            
            # Sort slices by name
            sorted_slices = sorted(slices, key=lambda x: x.get('slice_name', ''))
            
            # Print each slice with its details
            for j, slice_data in enumerate(sorted_slices):
                # Determine if this is the last slice for this table
                is_last_slice = (j == len(sorted_slices) - 1)
                
                # Use consistent indentation for all slices
                slice_prefix = "      └─ " if is_last_slice else "      ├─ "
                
                # Get counts
                slice_name = slice_data.get('slice_name', 'Unknown')
                actions = slice_data.get('slice_actions', '')
                action_count = len(actions.split('|||')) if actions else 0
                columns = slice_data.get('slice_columns', '')
                col_count = len(columns.split('|||')) if columns else 0
                
                # Use singular/plural correctly
                action_word = "action" if action_count == 1 else "actions"
                col_word = "column" if col_count == 1 else "columns"
                
                print(f"{slice_prefix}{slice_name}: {action_count} {action_word}, {col_count} {col_word}")
        
        # Print totals
        print(f"\n  📊 Total number of slices: {len(self.slices_data)}")
        print(f"  📊 Total number of columns in regular tables: {self.regular_tables_column_total:,}")

# Example usage and testing
if __name__ == "__main__":
    import sys
    
    # Test with command line argument or sample HTML
    if len(sys.argv) > 1:
        html_path = sys.argv[1]
        parser = SliceParser(html_path=html_path)
    else:
        # Test with sample HTML snippet
        sample_html = '''
        <h5 id="slice_Latest">Latest</h5>
        <table>
            <tr><td>Slice Name</td><td>Latest</td></tr>
            <tr><td>Source Table</td><td>Pal Walker</td></tr>
            <tr><td>Row filter condition</td><td>=[Walk time] = MAX(Pal Walker[Walk time])</td></tr>
            <tr><td>Slice Columns</td><td>
                <ol>
                    <li>Order</li>
                    <li>Walk time</li>
                    <li>Current time</li>
                </ol>
            </td></tr>
            <tr><td>Slice Actions</td><td>Walk done2,Failure,Now,plus five group,minus five group</td></tr>
        </table>
        '''
        
        parser = SliceParser(html_string=sample_html)
        
    # Parse slices
    slices = parser.parse()
    
    # Save to CSV (in test mode, just print)
    if len(sys.argv) > 1:
        parser.save_to_csv()
    else:
        print("\n📄 Test Results:")
        if parser.slices_data:
            print("  Slice columns parsing:")
            for slice_data in parser.slices_data:
                print(f"    {slice_data['slice_name']}: '{slice_data.get('slice_columns', 'None')}'")
