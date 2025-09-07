#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
phantom_view_reference_detector.py - Enhanced version using action_targets.csv
Uses pre-parsed action navigation targets while retaining regex parsing for other components
"""

import csv
import os
import sys
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

def normalize_text(text):
    """Normalize Unicode and clean up text"""
    if not text:
        return text
    text = unicodedata.normalize('NFKC', text)
    # Replace smart quotes with standard quotes
    text = text.replace('\u201C', '"').replace('\u201D', '"')  # “ ”
    text = text.replace('\u2018', "'").replace('\u2019', "'")  # ‘ ’
    return text.strip()

def resolve_view_name(name):
    """Clean and normalize a view name for comparison"""
    if not name:
        return name
    # Normalize Unicode and strip
    normalized = normalize_text(str(name))
    # Remove any surrounding quotes that might have been captured
    if (normalized.startswith('"') and normalized.endswith('"')) or \
       (normalized.startswith("'") and normalized.endswith("'")):
        normalized = normalized[1:-1]
    return normalized.strip()

def read_csv(filepath):
    """Read CSV and return list of dictionaries"""
    rows = []
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return rows

def get_known_views(views_csv_path):
    """Get set of all known view names from appsheet_views.csv"""
    views_normalized = set()  # For comparison (normalized, lowercase)
    views_original = {}  # Map normalized -> original name
    
    rows = read_csv(views_csv_path)
    for row in rows:
        view_name = row.get('view_name', '').strip()
        if view_name:
            # Normalize for comparison
            normalized = resolve_view_name(view_name).lower()
            views_normalized.add(normalized)
            views_original[normalized] = view_name
    
    return views_normalized, views_original

def extract_view_references(expression):
    """Extract view references using comprehensive regex patterns"""
    if not expression:
        return []
    
    expression = normalize_text(expression)
    references = []
    
    # Comprehensive patterns that properly handle quoted and unquoted view names
    patterns = [
        # LINKTOVIEW with quotes
        (r'LINKTOVIEW\s*\(\s*"([^"]+)"', 'LINKTOVIEW'),
        (r"LINKTOVIEW\s*\(\s*'([^']+)'", 'LINKTOVIEW'),
        # LINKTOVIEW without quotes - capture until closing paren
        (r'LINKTOVIEW\s*\(\s*([^)]+)\s*\)', 'LINKTOVIEW'),
        
        # LINKTOFORM with quotes
        (r'LINKTOFORM\s*\(\s*"([^"]+)"', 'LINKTOFORM'),
        (r"LINKTOFORM\s*\(\s*'([^']+)'", 'LINKTOFORM'),
        # LINKTOFORM without quotes - stop at first comma or closing paren
        (r'LINKTOFORM\s*\(\s*([^,)]+)', 'LINKTOFORM'),
        
        # LINKTOFILTEREDVIEW with quotes
        (r'LINKTOFILTEREDVIEW\s*\(\s*"([^"]+)"', 'LINKTOFILTEREDVIEW'),
        (r"LINKTOFILTEREDVIEW\s*\(\s*'([^']+)'", 'LINKTOFILTEREDVIEW'),
        # LINKTOFILTEREDVIEW without quotes - stop at first comma
        (r'LINKTOFILTEREDVIEW\s*\(\s*([^,)]+)', 'LINKTOFILTEREDVIEW'),
        
        # LINKTOROW - second argument is the view name
        (r'LINKTOROW\s*\([^,]+,\s*"([^"]+)"', 'LINKTOROW'),
        (r"LINKTOROW\s*\([^,]+,\s*'([^']+)'", 'LINKTOROW'),
        # LINKTOROW without quotes on second argument
        (r'LINKTOROW\s*\([^,]+,\s*([^)]+)\s*\)', 'LINKTOROW'),
        
        # CONTEXT("View") comparisons with quotes
        (r'CONTEXT\s*\(\s*["\']View["\']\s*\)\s*=\s*"([^"]+)"', 'CONTEXT'),
        (r"CONTEXT\s*\(\s*['\"]View['\"]\s*\)\s*=\s*'([^']+)'", 'CONTEXT'),
        # Reverse order comparisons
        (r'"([^"]+)"\s*=\s*CONTEXT\s*\(\s*["\']View["\']\s*\)', 'CONTEXT'),
        (r"'([^']+)'\s*=\s*CONTEXT\s*\(\s*['\"]View['\"]\s*\)", 'CONTEXT'),
    ]
    
    for pattern, func_type in patterns:
        for match in re.finditer(pattern, expression, re.IGNORECASE):
            view_name = match.group(1).strip()
            
            # Clean up the extracted name - remove quotes if they got captured
            if (view_name.startswith('"') and view_name.endswith('"')) or \
               (view_name.startswith("'") and view_name.endswith("'")):
                view_name = view_name[1:-1]
            
            # Additional cleanup for unquoted patterns
            view_name = view_name.strip()
            if func_type in ['LINKTOVIEW', 'LINKTOFORM', 'LINKTOFILTEREDVIEW']:
                # Remove trailing parentheses or commas if captured
                view_name = view_name.rstrip(',) ')
            
            # Skip empty, column references, or special keywords
            if view_name and not (view_name.startswith('[') and view_name.endswith(']')):
                if view_name.upper() not in ['VIEW', 'CONTEXT', 'TRUE', 'FALSE', 'NULL', '']:
                    references.append((func_type, view_name))
    
    return references

def find_action_phantoms_from_targets(parse_dir, known_views_normalized, indent=""):
    """Find phantom view references in actions using action_targets.csv"""
    phantoms = []
    action_targets_path = Path(parse_dir) / 'action_targets.csv'
    
    if not action_targets_path.exists():
        print(f"{indent}  ℹ️  No action_targets.csv found - using fallback regex parsing for actions")
        return None  # Signal to use fallback
    
    print(f"{indent}✔ Using pre-parsed action targets from action_targets.csv")
    
    rows = read_csv(str(action_targets_path))
    
    # Group phantoms by action to avoid duplicate entries
    action_phantoms = defaultdict(set)
    
    for row in rows:
        source_action = row.get('source_action', '')
        source_table = row.get('source_table', '')
        target_view = row.get('target_view', '')
        original_expression = row.get('original_expression', '')
        
        if not target_view:
            continue
            
        # Normalize for comparison
        normalized = resolve_view_name(target_view).lower()
        
        # Check if it's a phantom
        if normalized and normalized not in known_views_normalized:
            # Double-check it's not a false positive
            if target_view not in ['', 'VIEW', 'View']:
                action_phantoms[source_action].add(target_view)
    
    # Convert to the expected format
    for action_name, missing_views in action_phantoms.items():
        if missing_views:
            # Get the first row for this action to get table info
            action_rows = [r for r in rows if r.get('source_action') == action_name]
            if action_rows:
                first_row = action_rows[0]
                source_table = first_row.get('source_table', '')
                original_expr = first_row.get('original_expression', '')

                phantoms.append({
                    'name': action_name,
                    'type': 'Action',
                    'table': source_table,
                    'field': 'navigate_target',
                    'missing_view_names': '|||'.join(sorted(missing_views)),
                    'expression': original_expr
                })

    return phantoms


def find_phantoms(parse_dir, indent=""):
    """Main function to find phantom view references
    
    Args:
        parse_dir: Directory containing parsed CSV files
        indent: String to prepend to each output line (default: "")
    """
    
    # Get known views
    views_csv = os.path.join(parse_dir, 'appsheet_views.csv')
    if not os.path.exists(views_csv):
        print(f"{indent}ERROR: Cannot find {views_csv}")
        return []
    
    known_views_normalized, known_views_original = get_known_views(views_csv)
    print(f"{indent}\n{indent}✔ Found {len(known_views_normalized)} known views")
    
    phantoms = []
    total_expressions = 0
    
    # Try to use action_targets.csv for actions
    action_phantoms = find_action_phantoms_from_targets(parse_dir, known_views_normalized, indent)
    
    if action_phantoms is not None:
        # Successfully used action_targets.csv
        phantoms.extend(action_phantoms)
        total_expressions += len(action_phantoms)  # Count of action expressions with phantoms
        
        # Still need to scan only_if_condition from actions
        actions_csv = os.path.join(parse_dir, 'appsheet_actions.csv')
        if os.path.exists(actions_csv):
            rows = read_csv(actions_csv)
            print(f"{indent}✔ Scanning {len(rows)} action only_if conditions")
            
            for row in rows:
                action_name = row.get('action_name', '')
                table_name = row.get('source_table', '')  
                
                # Only scan only_if_condition since navigate_target is handled by action_targets.csv
                expression = row.get('only_if_condition', '')
                if not expression or expression.strip() in ['', '**auto**']:
                    continue
                
                total_expressions += 1
                
                # Extract view references
                refs = extract_view_references(expression)
                
                # Collect phantom references
                missing_views = []
                for func_type, view_name in refs:
                    normalized = resolve_view_name(view_name).lower()
                    if normalized and normalized not in known_views_normalized:
                        if view_name not in ['', 'VIEW', 'View']:
                            missing_views.append(view_name)
                
                if missing_views:
                    phantoms.append({
                        'name': action_name,
                        'type': 'Action',
                        'table': table_name,
                        'field': 'only_if_condition',
                        'missing_view_names': '|||'.join(missing_views),
                        'expression': expression
                    })


    else:
        # Fallback to regex parsing for all action fields
        print(f"{indent}  Using fallback regex parsing for actions")
        config = {
            'file': 'appsheet_actions.csv',
            'type': 'Action',
            'id_field': 'action_name',
            'table_field': 'table_name',
            'expression_fields': ['navigate_target', 'only_if_condition']
        }
        
        csv_path = os.path.join(parse_dir, config['file'])
        if os.path.exists(csv_path):
            rows = read_csv(csv_path)
            print(f"{indent}✔ Scanning {len(rows)} {config['type']}s")
            
            for row in rows:
                component_id = row.get(config['id_field'], '')
                component_table = row.get(config['table_field'], '')
                
                for field in config['expression_fields']:
                    expression = row.get(field, '')
                    if not expression or expression.strip() in ['', '**auto**']:
                        continue
                    
                    total_expressions += 1
                    
                    refs = extract_view_references(expression)
                    missing_views = []
                    
                    for func_type, view_name in refs:
                        normalized = resolve_view_name(view_name).lower()
                        if normalized and normalized not in known_views_normalized:
                            if view_name not in ['', 'VIEW', 'View']:
                                missing_views.append(view_name)
                    
                    if missing_views:
                        phantoms.append({
                            'name': action_name,
                            'type': 'Action',
                            'table': table_name,
                            'field': 'only_if_condition',
                            'missing_view_names': '|||'.join(missing_views),
                            'expression': expression
                        })
    
    # Scan other component types (columns, views, format rules)
    scan_config = [
        {
            'file': 'appsheet_columns.csv',
            'type': 'Column',
            'id_field': 'column_name',
            'table_field': 'table_name',
            'expression_fields': ['app_formula', 'show_if', 'valid_if', 'type_qualifier_formulas']
        },
        {
            'file': 'appsheet_views.csv',
            'type': 'View',
            'id_field': 'view_name',
            'table_field': 'data_source',
            'expression_fields': ['show_if']
        },
        {
            'file': 'appsheet_format_rules.csv',
            'type': 'Format Rule',
            'id_field': 'rule_name',
            'table_field': 'table_name',
            'expression_fields': ['condition']
        }
    ]
    
    for config in scan_config:
        csv_path = os.path.join(parse_dir, config['file'])
        if not os.path.exists(csv_path):
            continue
        
        rows = read_csv(csv_path)
        print(f"{indent}✔ Scanning {len(rows)} {config['type']}s")
        
        for row in rows:
            component_id = row.get(config['id_field'], '')
            component_table = row.get(config['table_field'], '')
            
            for field in config['expression_fields']:
                expression = row.get(field, '')
                if not expression or expression.strip() in ['', '**auto**']:
                    continue
                
                total_expressions += 1
                
                refs = extract_view_references(expression)
                missing_views = []
                
                for func_type, view_name in refs:
                    normalized = resolve_view_name(view_name).lower()
                    if normalized and normalized not in known_views_normalized:
                        if view_name not in ['', 'VIEW', 'View']:
                            missing_views.append(view_name)
                
                if missing_views:
                    phantoms.append({
                        'name': component_id,
                        'type': config['type'],      # 'Column' | 'View' | 'Format Rule'
                        'table': component_table,
                        'field': field,
                        'missing_view_names': '|||'.join(missing_views),
                        'expression': expression     # full expression, not truncated
                    })

    
    print(f"{indent}\n{indent}📊 Total expressions analyzed: {total_expressions}")
    return phantoms

def write_results(parse_dir, phantoms, indent=""):
    """Write phantom references to CSV
    
    Args:
        parse_dir: Directory to write results to
        phantoms: List of phantom references found
        indent: String to prepend to each output line (default: "")
    """
    
    output_file = os.path.join(parse_dir, 'potential_phantom_view_references.csv')
    
    if not phantoms:
        # Nothing to write — let the caller print the ✅ message
        return
    
    # Write CSV
    fieldnames = ['name', 'type', 'table',
                  'field', 'missing_view_names', 'expression']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(phantoms)
    
    phantom_text = "expression" if len(phantoms) == 1 else "expressions"
    print(f"{indent}\n{indent}⚠️  Found {len(phantoms)} {phantom_text} with phantom references")
    print(f"{indent}✅ Results saved to: potential_phantom_view_references.csv")
    
    # Print summary of unique phantom views
    phantom_counts = defaultdict(int)
    for p in phantoms:
        views = p['missing_view_names'].split('|||')
        for view in views:
            phantom_counts[view] += 1
    
    if phantom_counts:
        print(f"{indent}\n{indent}📊 Unique phantom views found (sorted by frequency):")
        for view, count in sorted(phantom_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{indent}   {count:3d}x {view}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python phantom_view_reference_detector.py <parse_directory>")
        sys.exit(1)
    
    parse_dir = sys.argv[1]
    
    print("=" * 60)
    print("PHASE 11: Phantom View Reference Detection")
    print("=" * 60)
    print("\n🔍 Starting Phantom View Reference Detection...")
    print(f"📂 Directory: {parse_dir}")
    
    print("\n✔ Validating required files...")
    
    phantoms = find_phantoms(parse_dir)  # No indent for standalone
    
    print("\n💾 Writing results...")
    write_results(parse_dir, phantoms)  # No indent for standalone
    
    print("\n" + "=" * 60)
    print("Phantom View Reference Detection Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()