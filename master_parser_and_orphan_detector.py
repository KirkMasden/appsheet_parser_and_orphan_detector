#!/usr/bin/env python3
"""
Master Parser Script for AppSheet HTML Documentation
Ensures parsers are run in the correct order and manages dependencies.
"""

import os
import sys
import argparse
from datetime import datetime

# Import the parsers and orphan detectors
from slice_parser import SliceParser
from column_parser import ColumnParser
from format_rules_parser import FormatRulesParser
from actions_parser import ActionsParser
from views_parser import ViewsParser
from action_target_parser import NavigationExpressionParser
from column_orphan_detector import VirtualColumnOrphanDetector
from actions_orphan_detector import ActionOrphanDetector
from view_orphan_detector import ViewOrphanDetector
from format_rule_orphan_detector import FormatRuleOrphanDetector
from slice_orphan_detector import SliceOrphanDetector
from phantom_view_reference_detector import find_phantoms, write_results

def print_header(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")

def count_columns_by_type(csv_path):
    """Count physical vs virtual columns from the CSV file."""
    physical = 0
    virtual = 0
    
    if not os.path.exists(csv_path):
        return physical, virtual
    
    import csv
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Check if this is a virtual column
            if row.get('is_virtual', '').lower() == 'yes':
                virtual += 1
            else:
                physical += 1
    
    return physical, virtual

def count_actions_by_type(csv_path):
    """Count system-generated vs user-created actions from the CSV file."""
    system = 0
    user = 0
    unsure = 0
    unknown = 0
    
    if not os.path.exists(csv_path):
        return system, user, unsure, unknown
    
    import csv
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = row.get('is_system_generated', 'Unknown')
            if status == 'Yes':
                system += 1
            elif status == 'No':
                user += 1
            elif status == 'UNSURE':
                unsure += 1
            else:  # Unknown or any other value
                unknown += 1
    
    return system, user, unsure, unknown

def count_views_by_type(csv_path):
    """Count system-generated vs user-created views from the CSV file."""
    system = 0
    user = 0
    
    if not os.path.exists(csv_path):
        return system, user
    
    import csv
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('is_system_view', '').lower() == 'yes':
                system += 1
            else:
                user += 1
    
    return system, user

def count_tables_from_columns(csv_path):
    """Count unique tables from the columns CSV (excluding system tables)."""
    if not os.path.exists(csv_path):
        return 0
    
    tables = set()
    import csv
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            table = row.get('table_name', '')
            # Exclude system tables (starting with * or _) and process/bot tables
            if table and not table.startswith('*') and not table.startswith('_'):
                # Also exclude process/bot tables (containing "Process" or "Output")
                if 'Process' not in table and 'Output' not in table:
                    tables.add(table)
    
    return len(tables)

def run_slice_parser(html_path, output_dir):
    """Run the slice parser and save results."""
    print_header("PHASE 1: Parsing Tables and Slices")
    
    parser = SliceParser(html_path)
    slices = parser.parse()
    
    # Save to output directory
    csv_path = os.path.join(output_dir, 'appsheet_slices.csv')
    parser.save_to_csv(output_dir, 'appsheet_slices.csv')
    
    return len(slices), csv_path


def run_column_parser(html_path, output_dir, debug_mode=False):
    """Run the column parser (uses slice data if available)."""
    print_header("PHASE 2: Parsing Columns")
    
    # Check if slice data exists
    slice_csv = os.path.join(output_dir, 'appsheet_slices.csv')
    if not os.path.exists(slice_csv):
        print("  ℹ️  No slice data found - proceeding without slice mappings")
        print("     (Table references will be used as-is)")
    
    # Convert HTML path to absolute before changing directory
    abs_html_path = os.path.abspath(html_path)
    
    # Change to output directory so column parser can find the CSV if it exists
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        parser = ColumnParser(abs_html_path, debug_mode=debug_mode)
        columns = parser.parse()
        
        # Save results
        csv_path = 'appsheet_columns.csv'
        parser.save_to_csv(csv_path)
        
        return len(columns), os.path.join(output_dir, csv_path)
    finally:
        os.chdir(original_dir)


def run_format_rules_parser(html_path, output_dir, debug_mode=False):
    """Run the format rules parser (uses slice data if available)."""
    print_header("PHASE 3: Parsing Format Rules")
    
    # Check if slice data exists
    slice_csv = os.path.join(output_dir, 'appsheet_slices.csv')
    if not os.path.exists(slice_csv):
        print("  ℹ️  No slice data found - proceeding without slice mappings")
    
    # Convert HTML path to absolute before changing directory
    abs_html_path = os.path.abspath(html_path)
    
    # Change to output directory so parser can find the slice CSV if it exists
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        parser = FormatRulesParser(abs_html_path, debug_mode=debug_mode)
        format_rules = parser.parse()
        
        # Save results - use defaults to avoid path duplication
        parser.save_to_csv()  # This will use default filename in current directory
        
        csv_path = os.path.join(output_dir, 'appsheet_format_rules.csv')
        return len(format_rules), csv_path
    finally:
        os.chdir(original_dir)


def run_actions_parser(html_path, output_dir, debug_mode=False):
    """Run the actions parser (uses slice and column data if available)."""
    print_header("PHASE 4: Parsing Actions")
    
    # Check if required data exists
    slice_csv = os.path.join(output_dir, 'appsheet_slices.csv')
    columns_csv = os.path.join(output_dir, 'appsheet_columns.csv')
    
    if not os.path.exists(slice_csv):
        print("  ℹ️  No slice data found - proceeding without slice mappings")
    
    if not os.path.exists(columns_csv):
        print("  ⚠️  No column data found - system action detection will be limited")
    
    # Convert HTML path to absolute before changing directory
    abs_html_path = os.path.abspath(html_path)
    
    # Change to output directory so parser can find the CSV files if they exist
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        parser = ActionsParser(abs_html_path, debug_mode=debug_mode)
        actions = parser.parse()
        
        # Save results
        parser.save_to_csv()  # This will use default filename in current directory
        
        csv_path = os.path.join(output_dir, 'appsheet_actions.csv')
        return len(actions), csv_path
    finally:
        os.chdir(original_dir)


def run_views_parser(html_path, output_dir, debug_mode=False):
    """Run the views parser (uses slice data and views.txt if available)."""
    print_header("PHASE 5: Parsing Views")
    
    # Check if slice data exists
    slice_csv = os.path.join(output_dir, 'appsheet_slices.csv')
    if not os.path.exists(slice_csv):
        print("  ℹ️  No slice data found - proceeding without slice mappings")
    
    # Check if views.txt exists (should be in same directory as HTML file)
    html_dir = os.path.dirname(os.path.abspath(html_path))
    views_txt = os.path.join(html_dir, 'views.txt')
    
    if not os.path.exists(views_txt):
        # Also check in output directory in case user put it there
        views_txt_alt = os.path.join(output_dir, 'views.txt')
        if os.path.exists(views_txt_alt):
            views_txt = views_txt_alt
    
    # Convert HTML path to absolute before changing directory
    abs_html_path = os.path.abspath(html_path)
    
    # Change to output directory so parser can find the slice CSV if it exists
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        # If views.txt exists, copy it to working directory temporarily
        temp_views_txt = None
        if os.path.exists(views_txt):
            import shutil
            temp_views_txt = 'views.txt'
            if not os.path.exists(temp_views_txt):
                shutil.copy(views_txt, temp_views_txt)
        
        parser = ViewsParser(abs_html_path, debug_mode=debug_mode)
        views = parser.parse()
        
        # Save results
        parser.save_to_csv()  # This will use default filename in current directory
        
        # Clean up temporary file if we created one
        if temp_views_txt and os.path.exists(temp_views_txt) and os.path.exists(views_txt):
            os.remove(temp_views_txt)
        
        csv_path = os.path.join(output_dir, 'appsheet_views.csv')
        return len(views), csv_path
    finally:
        os.chdir(original_dir)

def run_action_target_parser(output_dir, debug_mode=False):
    """Run the action target parser on the actions CSV file."""
    print_header("PHASE 6: Parsing Navigation Targets")
    
    # Check if appsheet_actions.csv exists
    actions_csv = os.path.join(output_dir, 'appsheet_actions.csv')
    if not os.path.exists(actions_csv):
        print("  ⚠️  No actions data found - skipping navigation target parsing")
        print("     (Phase 4 must complete successfully first)")
        return 0, None
    
    print("  📂 Loading actions from appsheet_actions.csv")
    
    try:
        # Initialize and run the parser
        parser = NavigationExpressionParser()
        
        # Load views CSV to get table->detail view mappings
        views_csv = os.path.join(output_dir, 'appsheet_views.csv')
        parser.load_views_csv(views_csv)
        
        output_csv = os.path.join(output_dir, 'action_targets.csv')
        stats = parser.parse_actions_csv(actions_csv, output_csv)
        
        # Format the output
        action_counts = stats['action_counts']
        target_counts = stats['target_counts']
        context_counts = stats['context_counts']
        unparseable_counts = stats['unparseable_counts']
        
        print(f"  ✅ Loaded {action_counts['total']} actions")
        print(f"     ├─ Navigation actions: {action_counts['navigation']}")
        print(f"     ├─ Group actions: {action_counts['group']}")
        print(f"     └─ Other actions skipped: {action_counts['other'] + action_counts['external_url'] + action_counts['data_modifications']}")
        print(f"        ├─ External URLs: {action_counts['external_url']}")
        print(f"        ├─ Data modifications: {action_counts['data_modifications']}")
        print(f"        └─ Other types: {action_counts['other']}")
        
        print("\n  🎯 Extracting navigation targets...")
        print(f"  ✓ Processing {action_counts['navigation'] + action_counts['group']} actions ({action_counts['navigation']} navigation + {action_counts['group']} group)")
        
        uc = stats['unparseable_count']
        if uc:
            noun = "expression" if uc == 1 else "expressions"
            print(f"\n  ⚠️  Found {uc} unparseable navigation {noun}")
        
        print("\n  📊 Navigation Targets Extracted:")
        print(f"\n    Navigation targets: {stats['targets_count']}")
        print(f"      ├─ Direct (#control=, #page=): {target_counts['direct']}")
        print(f"      ├─ LINKTOVIEW: {target_counts['linktoview']}")
        print(f"      └─ LINKTOROW: {target_counts['linktorow']}")
        
        print("\n    💡 Note: Actions with IFS/IF conditions generate multiple targets")
        print("       (one per branch), so targets may be greater than actions")
        
        if unparseable_counts:
            print(f"\n    Unparseable expressions: {stats['unparseable_count']}")
            for reason, count in unparseable_counts.items():
                print(f"      ├─ {reason}: {count}")
        
        print(f"\n    Group actions recorded: {action_counts['group']}")
        
        print(f"\n    Context conditions detected: {context_counts['total']}")
        if context_counts['total'] > 0:
            print(f"      ├─ View-based (CONTEXT(\"View\")): {context_counts['view']}")
            print(f"      ├─ ViewType-based: {context_counts['viewtype']}")
            print(f"      └─ Table-based: {context_counts['table']}")
        
        print(f"\n  ✅ Navigation targets saved to: action_targets.csv")
        
        if unparseable_counts:
            print(f"  ⚠️  Unparseable expressions saved to: action_targets_unparseable.csv")
        
        return stats['targets_count'], output_csv
        
    except Exception as e:
        print(f"  ❌ Action target parser failed: {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return 0, None

def run_navigation_edge_generator(output_dir, debug_mode=False):
    """Run Phase 7: Navigation Edge Generation."""
    print_header("PHASE 7: Generating Navigation Edges")
    
    # Import the generator
    from navigation_edge_generator import NavigationEdgeGenerator
    
    try:
        generator = NavigationEdgeGenerator(output_dir)
        success = generator.run()
        
        if success:
            return len(generator.edges), os.path.join(output_dir, 'navigation_edges.csv')
        else:
            return 0, None
            
    except Exception as e:
        print(f"  ❌ Navigation edge generator failed: {e}")
        if debug_mode:
            import traceback
            traceback.print_exc()
        return 0, None

def run_all_parsers(html_path, output_dir, debug_mode=False):
    """Run all parsers in the correct order."""
    # The output directory should already be created by main()
    app_output_dir = output_dir
        
    # Track results
    results = {}
    
    # Phase 1: Slices (no dependencies)
    try:
        count, path = run_slice_parser(html_path, app_output_dir)
        results['slices'] = {'count': count, 'path': path, 'status': 'success'}
    except Exception as e:
        print(f"❌ Slice parser failed: {e}")
        results['slices'] = {'count': 0, 'path': None, 'status': 'failed', 'error': str(e)}
        # Don't return early - slices are optional
    
    # Phase 2: Columns (depends on slices if they exist)
    try:
        count, path = run_column_parser(html_path, app_output_dir, debug_mode=debug_mode)
        results['columns'] = {'count': count, 'path': path, 'status': 'success'}
    except Exception as e:
        print(f"❌ Column parser failed: {e}")
        results['columns'] = {'count': 0, 'path': None, 'status': 'failed', 'error': str(e)}
        # Columns are critical - if they fail, we should probably stop
        # But let's continue to see what else might work
    
    # Phase 3: Format Rules (depends on slices if they exist, but optional component)
    try:
        count, path = run_format_rules_parser(html_path, app_output_dir, debug_mode=debug_mode)
        results['format_rules'] = {'count': count, 'path': path, 'status': 'success'}
    except Exception as e:
        print(f"❌ Format rules parser failed: {e}")
        results['format_rules'] = {'count': 0, 'path': None, 'status': 'failed', 'error': str(e)}
        # Format rules are optional - continue
    
    # Phase 4: Actions (depends on slices and columns if they exist)
    try:
        count, path = run_actions_parser(html_path, app_output_dir, debug_mode=debug_mode)
        results['actions'] = {'count': count, 'path': path, 'status': 'success'}
    except Exception as e:
        print(f"❌ Actions parser failed: {e}")
        results['actions'] = {'count': 0, 'path': None, 'status': 'failed', 'error': str(e)}
        # Actions are important but not critical - continue
    
    # Phase 5: Views (depends on slices if they exist, benefits from views.txt)
    try:
        count, path = run_views_parser(html_path, app_output_dir, debug_mode=debug_mode)
        results['views'] = {'count': count, 'path': path, 'status': 'success'}
    except Exception as e:
        print(f"❌ Views parser failed: {e}")
        results['views'] = {'count': 0, 'path': None, 'status': 'failed', 'error': str(e)}
        # Views are important but not critical - continue
    
    # Phase 6: Action Targets (depends on actions)
    try:
        count, path = run_action_target_parser(app_output_dir, debug_mode=debug_mode)
        results['action_targets'] = {'count': count, 'path': path, 'status': 'success'}
    except Exception as e:
        print(f"❌ Action target parser failed: {e}")
        results['action_targets'] = {'count': 0, 'path': None, 'status': 'failed', 'error': str(e)}
    
    # Phase 7: Navigation Edges (placeholder)
    run_navigation_edge_generator(app_output_dir, debug_mode=debug_mode)
    
    # Future phases can be added here:
    # Phase 8: Bots/Events
    
    # Summary
    print_header("Parsing complete!")
    print("📊 Summary of data to be analyzed:")
    
    # Data Sources (Tables + Slices)
    if results.get('slices', {}).get('status') == 'success' and results.get('columns', {}).get('status') == 'success':
        table_count = count_tables_from_columns(results['columns']['path'])
        slice_count = results['slices']['count']
        total_data_sources = table_count + slice_count
        print(f"   ✅ Data Sources: {total_data_sources:,} total")
        print(f"      ├─ Tables: {table_count}")
        print(f"      └─ Slices: {slice_count}")
    elif results.get('slices', {}).get('status') == 'success':
        print(f"   ✅ Slices: {results['slices']['count']} items")
    
    # Columns with breakdown
    if results.get('columns', {}).get('status') == 'success':
        physical, virtual = count_columns_by_type(results['columns']['path'])
        total_columns = results['columns']['count']
        print(f"   ✅ Columns: {total_columns:,} total")
        print(f"      ├─ Physical: {physical}")
        print(f"      └─ Virtual: {virtual}")
    elif results.get('columns', {}).get('status') == 'failed':
        print(f"   ❌ Columns: Failed")
        print(f"      Error: {results['columns'].get('error', 'Unknown error')}")
    
    # Format rules (no breakdown needed)
    if results.get('format_rules', {}).get('status') == 'success':
        print(f"   ✅ Format rules: {results['format_rules']['count']}")
    elif results.get('format_rules', {}).get('status') == 'failed':
        print(f"   ❌ Format rules: Failed")
        print(f"      Error: {results['format_rules'].get('error', 'Unknown error')}")
    
    # Actions with breakdown
    if results.get('actions', {}).get('status') == 'success':
        system, user, unsure, unknown = count_actions_by_type(results['actions']['path'])
        total_actions = results['actions']['count']
        print(f"   ✅ Actions: {total_actions} total")
        print(f"      ├─ System-generated: {system}")
        print(f"      ├─ User-created: {user}")
        if unsure > 0 and unknown > 0:
            print(f"      ├─ UNSURE (duplicates): {unsure}")
            print(f"      └─ Unknown (not in actions.txt): {unknown}")
        elif unsure > 0:
            print(f"      └─ UNSURE (duplicates): {unsure}")
        elif unknown > 0:
            print(f"      └─ Unknown (not in actions.txt): {unknown}")
    elif results.get('actions', {}).get('status') == 'failed':
        print(f"   ❌ Actions: Failed")
        print(f"      Error: {results['actions'].get('error', 'Unknown error')}")
    
    # Views with breakdown
    if results.get('views', {}).get('status') == 'success':
        system, user = count_views_by_type(results['views']['path'])
        total_views = results['views']['count']
        print(f"   ✅ Views: {total_views} total")
        print(f"      ├─ System-generated: {system}")
        print(f"      └─ User-created: {user}")
    elif results.get('views', {}).get('status') == 'failed':
        print(f"   ❌ Views: Failed")
        print(f"      Error: {results['views'].get('error', 'Unknown error')}")

    # Action targets (no breakdown needed - count is sufficient)
    if results.get('action_targets', {}).get('status') == 'success':
        print(f"   ✅ Navigation targets: {results['action_targets']['count']}")
    elif results.get('action_targets', {}).get('status') == 'failed':
        print(f"   ❌ Navigation targets: Failed")
        print(f"      Error: {results['action_targets'].get('error', 'Unknown error')}")
    
    return results

def run_view_orphan_detector(output_dir):
    """Run the view orphan detector on parsed CSV files."""
    print_header("PHASE 8: View Orphan Detection")
    detector = ViewOrphanDetector(output_dir)
    detector.run_analysis()

def run_column_orphan_detector(output_dir):
    """Run the column orphan detector on parsed CSV files."""
    print_header("PHASE 9: Virtual Column Orphan Detection")
    detector = VirtualColumnOrphanDetector(output_dir)
    detector.run_analysis()  

def run_action_orphan_detector(output_dir):
    """Run the action orphan detector on parsed CSV files."""
    print_header("PHASE 10: Action Orphan Detection")
    detector = ActionOrphanDetector(output_dir)
    detector.run_analysis()

def run_format_rule_orphan_detector(output_dir):
    """Run the format rule orphan detector on parsed CSV files."""
    print_header("PHASE 11: Format Rule Orphan Detection")
    detector = FormatRuleOrphanDetector(output_dir)
    detector.run_analysis()

def run_slice_orphan_detector(output_dir):
    """Run the slice orphan detector on parsed CSV files."""
    print_header("PHASE 12: Slice Orphan Detection")
    detector = SliceOrphanDetector(output_dir)
    detector.run_analysis()

def run_phantom_view_detector(output_dir):
    """Run the phantom view reference detector on parsed CSV files."""
    print_header("PHASE 13: Phantom View Reference Detection")
    
    print("🔍 Starting Phantom View Reference Detection...")
    print(f"  📂 Directory: {output_dir}")
    
    print("\n  ✔ Validating required files...")
    
    phantoms = find_phantoms(output_dir, indent="  ")  # ADD INDENT
    
    if phantoms:
        print("\n  💾 Writing results...")
        write_results(output_dir, phantoms, indent="  ")
    else:
        print(f"\n  ✅ No phantom view references found!")
    
    # Return count for summary
    return len(phantoms)

def main():
    """Main entry point with command line argument handling."""
    parser = argparse.ArgumentParser(
        description='Parse AppSheet HTML documentation in the correct order'
    )
    parser.add_argument(
        'html_file',
        help='Path to the AppSheet HTML documentation file'
    )
    parser.add_argument(
        '-o', '--output',
        default='.',
        help='Output directory for CSV files (default: current directory)'
    )
    parser.add_argument(
        '-s', '--slice-only',
        action='store_true',
        help='Only run the slice parser'
    )
    parser.add_argument(
        '-c', '--column-only',
        action='store_true',
        help='Only run the column parser (requires existing slice data)'
    )
    parser.add_argument(
        '-f', '--format-rules-only',
        action='store_true',
        help='Only run the format rules parser'
    )
    parser.add_argument(
        '-a', '--actions-only',
        action='store_true',
        help='Only run the actions parser (best with existing slice and column data)'
    )
    parser.add_argument(
        '-v', '--views-only',
        action='store_true',
        help='Only run the views parser (best with existing slice data and views.txt)'
    )
    parser.add_argument(
        '-t', '--targets-only',
        action='store_true',
        help='Only run the navigation target parser (requires existing actions data)'
    )
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug mode for verbose output'
    )
    
    parser.add_argument (
        '-co', '--column-orphans', 
        action='store_true', 
        help='Run only column orphan detection')

    parser.add_argument(
        '-ao', '--action-orphans', 
        action='store_true', 
        help='Run only action orphan detection')

    parser.add_argument(
        '-vo', '--view-orphans', 
        action='store_true', 
        help='Run only view orphan detection')

    parser.add_argument(
        '-fo', '--format-rule-orphans', 
        action='store_true', 
        help='Run only format rule orphan detection')

    parser.add_argument(
        '-so', '--slice-orphans', 
        action='store_true', 
        help='Run only slice orphan detection')

    parser.add_argument(
    '-pv', '--phantom-views',
    action='store_true',
    help='Run only phantom view reference detection'
)

    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.html_file):
        print(f"❌ Error: File not found: {args.html_file}")
        sys.exit(1)
    
    # Create output directory FIRST (unless running orphan detectors only)
    timestamp = datetime.now()
    
    # For orphan detectors, use the provided directory as-is
    if args.column_orphans or args.action_orphans or args.view_orphans or args.format_rule_orphans or args.slice_orphans:
        actual_output_dir = args.output
    else:
        # For parsers, create timestamped subdirectory
        parent_dir = os.path.basename(os.path.dirname(os.path.abspath(args.html_file)))
        parent_dir_clean = parent_dir.replace(' ', '_')
        actual_output_dir = os.path.join(args.output, f'{timestamp.strftime("%Y%m%d_%H%M%S")}_{parent_dir_clean}_parse')
        os.makedirs(actual_output_dir, exist_ok=True)
    
    # Print header with both directories
    # Define colors
    BLUE = '\033[94m'
    YELLOW = '\033[30;103m'  # Black text on bright yellow background
    GREEN = '\033[92m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    print(f'\n{BLUE}{"="*60}{RESET}')
    print(f'        {BLUE}🛠️{RESET}  {BOLD}AppSheet HTML Documentation Parser{RESET}  ')
    print(f'                     {BOLD}and Orphan Detector{RESET}      🔍')
    print(f'{BLUE}{"="*60}{RESET}')
    print(f'')
    print(f'   Project director: Kirk Masden')
    print(f'   Chief coder: Claude Opus 4')
    print(f'')
    print(f'   Input directory: {os.path.dirname(os.path.abspath(args.html_file))}')
    if not (args.column_orphans or args.action_orphans or args.view_orphans or args.format_rule_orphans or args.slice_orphans):
        print(f'   Output directory: {os.path.abspath(actual_output_dir)}')
    print(f'   Time: {timestamp.strftime("%Y-%m-%d %H:%M:%S")}')
    if args.debug:
        print(f"   🐛 {YELLOW}Debug mode: ENABLED{RESET}")
        
    # Check if running orphan detectors only
    if args.column_orphans:
        run_column_orphan_detector(actual_output_dir)
        return

    if args.action_orphans:
        run_action_orphan_detector(actual_output_dir)
        return

    if args.view_orphans:
        run_view_orphan_detector(actual_output_dir)
        return

    if args.format_rule_orphans:
        run_format_rule_orphan_detector(actual_output_dir)
        return

    if args.slice_orphans:
        run_slice_orphan_detector(actual_output_dir)
        return

    if args.phantom_views:
        run_phantom_view_detector(actual_output_dir)
        return

    # Run requested parsers
    if args.slice_only:
        run_slice_parser(args.html_file, actual_output_dir)
    elif args.column_only:
        run_column_parser(args.html_file, actual_output_dir, debug_mode=args.debug)
    elif args.format_rules_only:
        run_format_rules_parser(args.html_file, actual_output_dir, debug_mode=args.debug)
    elif args.actions_only:
        run_actions_parser(args.html_file, actual_output_dir, debug_mode=args.debug)
    elif args.views_only:
        run_views_parser(args.html_file, actual_output_dir, debug_mode=args.debug)
    elif args.targets_only:
        run_action_target_parser(actual_output_dir, debug_mode=args.debug)
    else:
        results = run_all_parsers(args.html_file, actual_output_dir, debug_mode=args.debug)
        
        # Automatically run orphan detectors after full parse
        print("\n" + "="*60)
        print("📊 Starting orphan detection...")
        print("="*60)
        
        # Use the actual output directory we created
        parse_dir = actual_output_dir
        
        if results:  # Only proceed if we have results
            
            # Track orphan counts
            orphan_summary = {}

            # MUST run view orphan detector FIRST - it creates unused_system_views.csv
            run_view_orphan_detector(parse_dir)
            run_column_orphan_detector(parse_dir)
            run_action_orphan_detector(parse_dir)
            run_format_rule_orphan_detector(parse_dir)
            run_slice_orphan_detector(parse_dir)
            phantom_count = run_phantom_view_detector(parse_dir)
            
            # Count orphans from CSV files
            import csv
            
            # Count virtual column orphans
            try:
                with open(os.path.join(parse_dir, 'potential_virtual_column_orphans.csv'), 'r') as f:
                    orphan_summary['virtual_columns'] = sum(1 for _ in csv.DictReader(f))
            except:
                orphan_summary['virtual_columns'] = 0
                
            # Count action orphans
            try:
                with open(os.path.join(parse_dir, 'potential_action_orphans.csv'), 'r') as f:
                    orphan_summary['actions'] = sum(1 for _ in csv.DictReader(f))
            except:
                orphan_summary['actions'] = 0
                
            # Count view orphans
            try:
                with open(os.path.join(parse_dir, 'potential_view_orphans.csv'), 'r') as f:
                    orphan_summary['views'] = sum(1 for _ in csv.DictReader(f))
            except:
                orphan_summary['views'] = 0
                
            # Count format rule orphans
            try:
                with open(os.path.join(parse_dir, 'potential_format_rule_orphans.csv'), 'r') as f:
                    orphan_summary['format_rules'] = sum(1 for _ in csv.DictReader(f))
            except:
                orphan_summary['format_rules'] = 0
                
            # Count slice orphans
            try:
                with open(os.path.join(parse_dir, 'potential_slice_orphans.csv'), 'r') as f:
                    orphan_summary['slices'] = sum(1 for _ in csv.DictReader(f))
            except:
                orphan_summary['slices'] = 0

            # Count phantom view references  
            try:
                with open(os.path.join(parse_dir, 'potential_phantom_view_references.csv'), 'r') as f:
                    orphan_summary['phantom_references'] = sum(1 for _ in csv.DictReader(f))
            except:
                orphan_summary['phantom_references'] = 0
            
            # Print final summary
            print_header("Orphan detection complete!")
            print("📊 Summary of potential orphans found:")
            print(f"   ⚠️  Virtual columns: {orphan_summary['virtual_columns']}")
            print(f"   ⚠️  Actions: {orphan_summary['actions']}")
            print(f"   ⚠️  Views: {orphan_summary['views']}")
            print(f"   ⚠️  Format rules: {orphan_summary['format_rules']}")
            print(f"   ⚠️  Slices: {orphan_summary['slices']}")
            print(f"   ⚠️  Phantom view references: {orphan_summary['phantom_references']}")
            
            total_orphans = sum(orphan_summary.values())
            print(f"\n   📊 Total potential orphans: {total_orphans}")
            
            # Remove any ./ prefix for cleaner display
            clean_parse_dir = parse_dir.lstrip('./')
            print(f"\n   📁 Results saved to: {clean_parse_dir}")
            print()
            print(f"\n✨ Analysis complete! Your AppSheet app structure has been fully analyzed.")
            print()
            
        # Clean up __pycache__ directories
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        for root, dirs, files in os.walk(script_dir):
            if '__pycache__' in dirs:
                pycache_path = os.path.join(root, '__pycache__')
                try:
                    import shutil
                    shutil.rmtree(pycache_path)
                except Exception:
                    pass  # Silently ignore any errors
        
        # Offer to run dependency analysis
        print("\n" + "="*70)
        print("PARSING AND ORPHAN DETECTION COMPLETE")
        print("="*70)
        
        try:
            response = input("\nWould you like to explore dependencies now? (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                print("\nLaunching Dependency Analysis Hub...")
                print("-" * 40)
                
                # Import and run the dependency analyzer hub
                try:
                    from dependency_analyzer_hub import DependencyAnalyzerHub
                    hub = DependencyAnalyzerHub(actual_output_dir)
                    hub.run()
                except ImportError as e:
                    print(f"\nError: Could not load dependency analyzer hub: {e}")
                    print("Please ensure dependency_analyzer_hub.py is in the same directory.")
                except Exception as e:
                    print(f"\nError running dependency analyzer: {e}")
            else:
                # Build absolute paths so the command works from any directory
                script_dir = os.path.dirname(os.path.abspath(__file__))
                hub_path = os.path.join(script_dir, 'dependency_analyzer_hub.py')
                abs_parse_dir = os.path.abspath(actual_output_dir)

                print("\nYou can run dependency analysis later by:")
                print('  1. Activating your virtual environment if not running (e.g., source venv/bin/activate)')
                print('  2. Pasting the following command:')
                print(f'     python "{hub_path}" "{abs_parse_dir}"')

        except KeyboardInterrupt:
            print("\n\nExiting...")

if __name__ == "__main__":
    main()