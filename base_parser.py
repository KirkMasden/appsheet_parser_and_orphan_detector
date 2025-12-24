#!/usr/bin/env python3
"""
Base Parser for AppSheet HTML Documentation - Enhanced with Debug Logging
Provides shared utilities and base functionality for all component parsers.
Fixes reference extraction to handle table names with spaces and resolve slice references.
"""

import re
import json
from bs4 import BeautifulSoup
from collections import defaultdict
from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Base class for all AppSheet component parsers."""
    
    def __init__(self, html_path=None, html_string=None, soup=None, debug_mode=False):
        """
        Initialize parser with HTML content.
        Can accept either a file path, HTML string, or pre-parsed BeautifulSoup object.
        """
        self.soup = soup
        self.debug_mode = debug_mode  # Enable debug logging
        self.lite_debug_mode = not debug_mode  # Enable minimal debug output

        if html_path:
            self.load_html_from_file(html_path)
        elif html_string:
            self.soup = BeautifulSoup(html_string, 'html.parser')
            
        # Shared data structures
        self.processed_elements = set()
        self.all_references = []
        
        # Slice name to source table mapping (populated by slice parser)
        self.slice_to_table_map = {}
        
        # Table and column information (can be populated by column parser)
        self.table_column_map = defaultdict(list)
        
        # Known JSON fields that contain formulas or references
        self.json_formula_fields = {
            'with_these_properties', 'type_qualifier', 'view_configuration',
            'parsed_data', 'settings', 'configuration', 'properties',
            'actiontype', 'action_settings', 'assignments'
        }
        
    def normalize_string(self, s: str) -> str:
        """
        Normalize Unicode curly quotes to straight ASCII quotes,
        then strip leading/trailing whitespace.
        """
        return (
            s
            .replace('“', '"')
            .replace('”', '"')
            .strip()
        )

    def load_html_from_file(self, html_path):
        """Load and parse HTML from file."""
        with open(html_path, 'r', encoding='utf-8') as f:
            self.soup = BeautifulSoup(f, 'html.parser')
            
    def normalize_identifier(self, identifier):
        """Normalize identifier for case-insensitive matching."""
        return identifier.lower().strip()
        
    def extract_references_from_text(self, text, context_table=None):
        """
        Extract column references from text (formulas, conditions, etc.).
        Fixed to handle table names with spaces and resolve slice references.
        """
        references = []
        
        if not isinstance(text, str):
            return references
        
            
        # Pattern 1: Table/Slice[Column] references
        # Updated pattern to handle table names with spaces
        # Matches: Table Name[Column], Table_Name[Column], TableName[Column]
        table_col_pattern = r'([A-Za-z0-9_]+(?:\s+[A-Za-z0-9_]+)*)\s*\[\s*([^\[\]]+)\s*\]'
        
        for match in re.finditer(table_col_pattern, text):
            table_or_slice = match.group(1).strip()
            column_name = match.group(2).strip()

            # Check if this is a slice reference and resolve to actual table
            actual_table = self.resolve_table_reference(table_or_slice)
            
            references.append({
                'type': 'explicit',
                'table': actual_table,
                'original_table': table_or_slice,  # Keep original for debugging
                'column': column_name,
                'raw': match.group(0),
                'context_table': context_table,
                'is_slice_ref': actual_table != table_or_slice
            })
            
        # Pattern 2: Bare [Column] references (use context table)
        # Negative lookbehind/ahead to avoid matching already captured Table[Column]
        bare_col_pattern = r'(?<![A-Za-z0-9_])\[\s*([^\]]+)\s*\](?![A-Za-z0-9_])'
        
        for match in re.finditer(bare_col_pattern, text):
            # Skip if this was already captured as Table[Column]
            if not any(ref['raw'] in match.group(0) for ref in references):
                column_name = match.group(1).strip()
                
                # Skip JSON arrays like ["value1","value2"] - they start with a quote
                if column_name.startswith('"') or column_name.startswith("'"):
                    continue
                
                # Use context table if available
                actual_table = self.resolve_table_reference(context_table) if context_table else None
                
                references.append({
                    'type': 'implicit',
                    'table': actual_table,
                    'column': column_name,
                    'raw': match.group(0),
                    'context_table': context_table
                })
        
        # Pattern 3: USERSETTINGS("ColumnName") references
        # Maps to _Per User Settings table
        usersettings_pattern = r'USERSETTINGS\s*\(\s*["\']([^"\']+)["\']\s*\)'
        
        for match in re.finditer(usersettings_pattern, text, re.IGNORECASE):
            column_name = match.group(1).strip()
            references.append({
                'type': 'usersettings',
                'table': '_Per User Settings',
                'column': column_name,
                'raw': match.group(0),
                'context_table': context_table,
                'is_slice_ref': False
            })
        
        # Pattern 4: [_THISUSER].[ColumnName] references
        # Alternative syntax for accessing User Settings
        thisuser_pattern = r'\[_THISUSER\]\.\[([^\]]+)\]'
        
        for match in re.finditer(thisuser_pattern, text, re.IGNORECASE):
            column_name = match.group(1).strip()
            references.append({
                'type': 'usersettings',
                'table': '_Per User Settings',
                'column': column_name,
                'raw': match.group(0),
                'context_table': context_table,
                'is_slice_ref': False
            })
                
        return references
        
    def resolve_table_reference(self, table_or_slice_name):
        """
        Resolve a table/slice name to the actual table name.
        If it's a slice, return the source table. Otherwise return as-is.
        """
        if not table_or_slice_name:
            return None
                    
        # Check if this is a known slice
        normalized = self.normalize_identifier(table_or_slice_name)
        for slice_name, source_table in self.slice_to_table_map.items():
            if self.normalize_identifier(slice_name) == normalized:
                return source_table
        
        # Not a slice, return original name
        return table_or_slice_name
        
    def extract_references_from_json(self, json_str, context_table=None):
        """Extract references from JSON configuration."""
        references = []

        try:
            data = json.loads(json_str)

            def find_references(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, str):
                            refs = self.extract_references_from_text(value, context_table)
                            for ref in refs:
                                ref['json_path'] = f"{path}.{key}" if path else key
                            references.extend(refs)
                        else:
                            find_references(value, f"{path}.{key}" if path else key)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        if isinstance(item, str):
                            refs = self.extract_references_from_text(item, context_table)
                            for ref in refs:
                                ref['json_path'] = f"{path}[{i}]"
                            references.extend(refs)
                        else:
                            find_references(item, f"{path}[{i}]")

            find_references(data)

        except json.JSONDecodeError as e:
            refs = self.extract_references_from_text(json_str, context_table)
            references.extend(refs)

        return references
        
    def build_absolute_references(self, references):
        """
        Convert all references to absolute format (Table[Column]).
        Returns a list of unique absolute references.
        """
        absolute_refs = []
        seen = set()
        
        for ref in references:
            if ref.get('table') and ref.get('column'):
                abs_ref = f"{ref['table']}[{ref['column']}]"
                if abs_ref not in seen:
                    seen.add(abs_ref)
                    absolute_refs.append(abs_ref)
                    
        return sorted(absolute_refs)  # Sort for consistency
        
    def extract_component_data(self, table_element, component_type, context_info=None):
        """
        Extract data from a component table with reference tracking.
        Returns a dictionary with all component data and references.
        """
        component_info = {'component_type': component_type}
        
        # Add context information
        context_table = None
        if context_info:
            if isinstance(context_info, dict):
                component_info.update(context_info)
                context_table = context_info.get('_context_table')
            else:
                # Assume it's a table name
                component_info['_context_table'] = context_info
                context_table = context_info
                
        # Store raw references found
        raw_references = []
        all_refs = []
        
        # Extract data from table rows
        for row in table_element.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) == 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                
                # Clean up the label
                clean_label = label.replace('?', '').replace(' ', '_').lower()
                
                # Store the original value
                component_info[clean_label] = value
                
                # Extract references from the value
                refs = self.extract_references_from_text(value, context_table)
                
                # Check if this might be a JSON field
                if (clean_label in self.json_formula_fields or 
                    (isinstance(value, str) and value.strip().startswith('{'))):
                    json_refs = self.extract_references_from_json(value, context_table)
                    refs.extend(json_refs)
                    
                # Collect all references
                for ref in refs:
                    raw_references.append(ref['raw'])
                    all_refs.append(ref)
                    
        # Add reference summary to component
        if raw_references:
            component_info['raw_references'] = ' | '.join(raw_references)
            
        # Build absolute references only
        if all_refs:
            absolute_refs = self.build_absolute_references(all_refs)
            component_info['referenced_columns'] = '|||'.join(absolute_refs)
        else:
            component_info['referenced_columns'] = ''
            
        # Store context table for formulas
        if context_table:
            component_info['formula_context_table'] = context_table
            
        return component_info
        
    def mark_element_processed(self, element_id):
        """Mark an element as processed to avoid duplicates."""
        if element_id:
            self.processed_elements.add(element_id)
            
    def is_element_processed(self, element_id):
        """Check if an element has been processed."""
        return element_id in self.processed_elements if element_id else False
        
    @abstractmethod
    def parse(self):
        """
        Abstract method that each component parser must implement.
        Should return a list of dictionaries representing the parsed components.
        """
        pass
        
    def get_standard_fields(self):
        """
        Return standard fields that should appear in all component CSVs.
        Subclasses can override to customize field order.
        """
        return [
            'component_type',
            'formula_context_table', 
            'raw_references',
            'referenced_columns'
        ]