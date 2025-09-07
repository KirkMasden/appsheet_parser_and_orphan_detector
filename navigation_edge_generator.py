#!/usr/bin/env python3
"""
AppSheet Navigation Edge Generator - Phase 7
Generates navigation_edges.csv from action_targets.csv and other parsed data

This script determines which views can navigate to which other views by:
1. Loading parsed navigation targets from action_targets.csv
2. Determining which actions are available on each view
3. Validating context conditions
4. Creating edges for valid navigation paths
"""

import csv
import json
import sys
import os
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional

class NavigationEdgeGenerator:
    """Generates navigation edges from parsed targets and view/action data."""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        
        # Data storage
        self.action_targets = []  # Rows from action_targets.csv
        self.actions = {}  # action_name -> action data
        self.views = {}  # view_name -> view data
        self.columns_by_table = defaultdict(set)  # table -> set of columns
        self.slices = {}  # slice_name -> slice data
        
        # Lookup indices for performance
        self.targets_by_action = defaultdict(list)  # action_name -> list of target rows
        self.views_by_name_lower = {}  # lowercase name -> canonical name
        
        # Output
        self.edges = []
        
        # Statistics
        self.stats = {
            'views_processed': 0,
            'actions_checked': 0,
            'groups_expanded': 0,
            'edges_created': 0,
            'edges_blocked_by_conditions': 0,
            'edges_blocked_by_visibility': 0
        }
    
    def load_action_targets(self) -> bool:
        """Load the parsed navigation targets from action_targets.csv."""
        filepath = self.output_dir / 'action_targets.csv'
        if not filepath.exists():
            print(f"  ❌ action_targets.csv not found")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.action_targets.append(row)
                    # Index by action name for quick lookup
                    action_name = row.get('source_action', '')
                    if action_name:
                        self.targets_by_action[action_name].append(row)
            
            print(f"  ✓ Loaded {len(self.action_targets)} navigation targets")
            return True
        except Exception as e:
            print(f"  ❌ Error loading action_targets.csv: {e}")
            return False
    
    def load_actions(self) -> bool:
        """Load actions data from appsheet_actions.csv."""
        filepath = self.output_dir / 'appsheet_actions.csv'
        if not filepath.exists():
            print(f"  ⚠️  appsheet_actions.csv not found - limited action availability checking")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    action_name = row.get('action_name', '')
                    if action_name:
                        self.actions[action_name] = row
            
            print(f"  ✓ Loaded {len(self.actions)} actions")
            return True
        except Exception as e:
            print(f"  ❌ Error loading appsheet_actions.csv: {e}")
            return False
    
    def load_views(self) -> bool:
        """Load views data from appsheet_views.csv."""
        filepath = self.output_dir / 'appsheet_views.csv'
        if not filepath.exists():
            print(f"  ❌ appsheet_views.csv not found")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    view_name = row.get('view_name', '')
                    if view_name:
                        self.views[view_name] = row
                        # Build case-insensitive lookup
                        self.views_by_name_lower[view_name.lower()] = view_name
            
            print(f"  ✓ Loaded {len(self.views)} views")
            return True
        except Exception as e:
            print(f"  ❌ Error loading appsheet_views.csv: {e}")
            return False
    
    def load_columns(self) -> bool:
        """Load columns data for inline action validation."""
        filepath = self.output_dir / 'appsheet_columns.csv'
        if not filepath.exists():
            print(f"  ⚠️  appsheet_columns.csv not found - column validation will be limited")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    table_name = row.get('table_name', '')
                    column_name = row.get('column_name', '')
                    if table_name and column_name:
                        self.columns_by_table[table_name].add(column_name)
            
            print(f"  ✓ Loaded columns for {len(self.columns_by_table)} tables")
            return True
        except Exception as e:
            print(f"  ⚠️  Warning loading appsheet_columns.csv: {e}")
            return False
    
    def load_slices(self) -> bool:
        """Load slices data for table resolution."""
        filepath = self.output_dir / 'appsheet_slices.csv'
        if not filepath.exists():
            print(f"  ⚠️  appsheet_slices.csv not found - slice resolution will be limited")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    slice_name = row.get('slice_name', '')
                    if slice_name:
                        self.slices[slice_name] = row
            
            print(f"  ✓ Loaded {len(self.slices)} slices")
            return True
        except Exception as e:
            print(f"  ⚠️  Warning loading appsheet_slices.csv: {e}")
            return False
    
    def get_view_table(self, view: Dict) -> str:
        """Get the underlying table for a view, resolving slices if needed."""
        data_source = view.get('data_source', '') or view.get('source_table', '')
        
        # Check if data source is a slice
        if data_source in self.slices:
            return self.slices[data_source].get('source_table', data_source)
        
        return data_source
    
    def is_action_visible_in_view(self, action: Dict, view: Dict) -> bool:
        """Check if an action is visible/accessible in a specific view."""
        action_name = action.get('source_action', '')
        prominence = action.get('action_prominence', '')
        attach_to_column = action.get('attach_to_column', '')
        view_type = view.get('view_type', '').lower()
        
        # Do_Not_Display actions are never visible
        if prominence == 'Do_Not_Display':
            self.stats['edges_blocked_by_visibility'] += 1
            return False
        
        # Check if action is in available_actions
        available_actions = view.get('available_actions', '').split('|||') if view.get('available_actions') else []
        available_actions = [a.strip() for a in available_actions if a.strip()]
        
        if action_name not in available_actions:
            self.stats['edges_blocked_by_visibility'] += 1
            return False
        
        # View-type-specific visibility rules
        if view_type == 'detail':
            return self.is_action_visible_in_detail_view(action, view)
        elif view_type == 'deck':
            return self.is_action_visible_in_deck_view(action, view)
        elif view_type == 'table':
            return self.is_action_visible_in_table_view(action, view)
        else:
            # For now, other view types just check available_actions
            return True
    
    def is_action_visible_in_detail_view(self, action: Dict, view: Dict) -> bool:
        """Check if an action is visible in a detail view."""
        prominence = action.get('action_prominence', '')
        attach_to_column = action.get('attach_to_column', '')
        
        # Primary, Display_Prominently, and Display_Inline all work in detail views
        if prominence in ['Primary', 'Display_Prominently', 'Display_Inline', 'Display_Overlay']:
            # For inline actions, check column visibility
            if prominence == 'Display_Inline' and attach_to_column:
                view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
                view_columns = [c.strip() for c in view_columns if c.strip()]
                
                if attach_to_column not in view_columns:
                    self.stats['edges_blocked_by_visibility'] += 1
                    return False
            
            return True
        
        # Unknown prominence - be conservative
        self.stats['edges_blocked_by_visibility'] += 1
        return False
    
    def is_action_visible_in_deck_view(self, action: Dict, view: Dict) -> bool:
        """Check if an action is visible in a deck view.
        
        For deck views:
        - Actions in the action bar (in both referenced_actions and available_actions) are valid
        - Prominence type doesn't matter if the action is in the action bar
        - Event actions are handled separately by process_event_actions
        """
        action_name = action.get('source_action', '')
        
        # Check if action is in referenced_actions (indicates it's in the action bar or events)
        referenced_actions = view.get('referenced_actions', '').split('|||') if view.get('referenced_actions') else []
        referenced_actions = [a.strip() for a in referenced_actions if a.strip()]
        
        # Check if action is in event_actions (these are handled elsewhere)
        event_actions = view.get('event_actions', '').split('|||') if view.get('event_actions') else []
        event_actions = [a.strip() for a in event_actions if a.strip()]
        
        # If action is in referenced_actions but NOT in event_actions, it's in the action bar
        # Action bar actions are valid regardless of prominence
        if action_name in referenced_actions and action_name not in event_actions:
            # It's in the action bar - this is valid for deck views
            return True
        
        # If we get here, the action is not in the action bar
        # Deck views don't support other display methods
        self.stats['edges_blocked_by_visibility'] += 1
        return False

    def is_action_visible_in_table_view(self, action: Dict, view: Dict) -> bool:
        """Check if an action is visible in a table view.
        
        Table views do NOT have action bars, so they only support:
        - Primary actions (row-level actions)
        - Display_Inline actions attached to visible columns
        - Event-triggered actions (handled separately)
        """
        prominence = action.get('action_prominence', '')
        attach_to_column = action.get('attach_to_column', '')
        action_name = action.get('source_action', '')
        
        # Do_Not_Display actions are never visible
        if prominence == 'Do_Not_Display':
            self.stats['edges_blocked_by_visibility'] += 1
            return False
        
        # Table views only support Primary (row actions) and Display_Inline (column actions)
        if prominence == 'Primary':
            # Primary actions appear as row-level actions in tables
            return True
        elif prominence == 'Display_Inline' and attach_to_column:
            # Inline actions must be attached to a visible column
            view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
            view_columns = [c.strip() for c in view_columns if c.strip()]
            
            if attach_to_column not in view_columns:
                self.stats['edges_blocked_by_visibility'] += 1
                return False
            return True
        else:
            # Table views don't support Display_Prominently or Display_Overlay
            # These would require an action bar, which tables don't have
            self.stats['edges_blocked_by_visibility'] += 1
            return False

    def check_context_conditions(self, target_row: Dict, view_name: str) -> bool:
        """Check if a view satisfies the context conditions in a target row."""
        view = self.views.get(view_name, {})
        view_type = view.get('view_type', '')
        view_table = self.get_view_table(view)
        
        # Check must_be_in_views (OR condition - view must be one of these)
        must_be_in = target_row.get('must_be_in_views', '')
        if must_be_in:
            allowed_views = [v.strip() for v in must_be_in.split('|||') if v.strip()]
            if allowed_views and view_name not in allowed_views:
                self.stats['edges_blocked_by_conditions'] += 1
                return False
        
        # Check must_not_be_in_views (OR condition - view must not be any of these)
        must_not_be_in = target_row.get('must_not_be_in_views', '')
        if must_not_be_in:
            blocked_views = [v.strip() for v in must_not_be_in.split('|||') if v.strip()]
            if view_name in blocked_views:
                self.stats['edges_blocked_by_conditions'] += 1
                return False
        
        # Check must_be_viewtype
        must_be_type = target_row.get('must_be_viewtype', '')
        if must_be_type:
            allowed_types = [t.strip() for t in must_be_type.split('|||') if t.strip()]
            if allowed_types and view_type not in allowed_types:
                self.stats['edges_blocked_by_conditions'] += 1
                return False
        
        # Check must_not_be_viewtype
        must_not_be_type = target_row.get('must_not_be_viewtype', '')
        if must_not_be_type:
            blocked_types = [t.strip() for t in must_not_be_type.split('|||') if t.strip()]
            if view_type in blocked_types:
                self.stats['edges_blocked_by_conditions'] += 1
                return False
        
        # Check must_be_table
        must_be_table = target_row.get('must_be_table', '')
        if must_be_table:
            allowed_tables = [t.strip() for t in must_be_table.split('|||') if t.strip()]
            if allowed_tables and view_table not in allowed_tables:
                self.stats['edges_blocked_by_conditions'] += 1
                return False
        
        # Check must_not_be_table
        must_not_be_table = target_row.get('must_not_be_table', '')
        if must_not_be_table:
            blocked_tables = [t.strip() for t in must_not_be_table.split('|||') if t.strip()]
            if view_table in blocked_tables:
                self.stats['edges_blocked_by_conditions'] += 1
                return False
        
        return True
    
    def combine_conditions(self, parent_row: Dict, child_row: Dict) -> Dict:
        """Combine conditions from parent and child actions (AND relationship)."""
        combined = child_row.copy()
        
        # Combine must_be_in_views (intersection if both present)
        parent_must_be = parent_row.get('must_be_in_views', '')
        child_must_be = child_row.get('must_be_in_views', '')
        if parent_must_be and child_must_be:
            parent_set = set(v.strip() for v in parent_must_be.split('|||') if v.strip())
            child_set = set(v.strip() for v in child_must_be.split('|||') if v.strip())
            intersection = parent_set & child_set
            combined['must_be_in_views'] = '|||'.join(sorted(intersection)) if intersection else ''
        elif parent_must_be:
            combined['must_be_in_views'] = parent_must_be
        
        # Combine must_not_be_in_views (union - can't be in any)
        parent_must_not = parent_row.get('must_not_be_in_views', '')
        child_must_not = child_row.get('must_not_be_in_views', '')
        if parent_must_not or child_must_not:
            parent_set = set(v.strip() for v in parent_must_not.split('|||') if v.strip()) if parent_must_not else set()
            child_set = set(v.strip() for v in child_must_not.split('|||') if v.strip()) if child_must_not else set()
            union = parent_set | child_set
            combined['must_not_be_in_views'] = '|||'.join(sorted(union))
        
        # Similar logic for viewtype and table conditions
        for field in ['must_be_viewtype', 'must_not_be_viewtype', 'must_be_table', 'must_not_be_table']:
            parent_val = parent_row.get(field, '')
            child_val = child_row.get(field, '')
            
            if 'must_not' in field:
                # Union for negative conditions
                if parent_val or child_val:
                    parent_set = set(v.strip() for v in parent_val.split('|||') if v.strip()) if parent_val else set()
                    child_set = set(v.strip() for v in child_val.split('|||') if v.strip()) if child_val else set()
                    union = parent_set | child_set
                    combined[field] = '|||'.join(sorted(union))
            else:
                # Intersection for positive conditions
                if parent_val and child_val:
                    parent_set = set(v.strip() for v in parent_val.split('|||') if v.strip())
                    child_set = set(v.strip() for v in child_val.split('|||') if v.strip())
                    intersection = parent_set & child_set
                    combined[field] = '|||'.join(sorted(intersection)) if intersection else ''
                elif parent_val:
                    combined[field] = parent_val
        
        return combined
    
    def process_group_action(self, group_row: Dict, view: Dict, parent_chain: List[str] = None, event_type: str = '') -> None:
        """Process a group action, expanding its children and creating edges."""
        if parent_chain is None:
            parent_chain = []
        
        group_name = group_row.get('source_action', '')
        referenced_actions = group_row.get('referenced_actions', '')
        
        if not referenced_actions:
            return
        
        # Prevent infinite recursion
        if group_name in parent_chain:
            return
        
        parent_chain = parent_chain + [group_name]
        self.stats['groups_expanded'] += 1
        
        # Check if group's conditions are satisfied
        if not self.check_context_conditions(group_row, view['view_name']):
            return
        
        # Process each child action
        child_actions = [a.strip() for a in referenced_actions.split('|||') if a.strip()]
        
        for child_name in child_actions:
            # Find child's target rows
            if child_name not in self.targets_by_action:
                continue
            
            child_targets = self.targets_by_action[child_name]
            
            for child_row in child_targets:
                # Handle nested groups
                if child_row.get('action_type') == 'execute_group':
                    # Combine conditions and recurse
                    combined_row = self.combine_conditions(group_row, child_row)
                    combined_row['source_action'] = child_name  # Keep child's name
                    self.process_group_action(combined_row, view, parent_chain, event_type)
                else:
                    # Regular navigation action
                    target_view = child_row.get('target_view', '')
                    if not target_view:
                        continue
                    
                    # Skip special markers
                    if target_view in ['DYNAMIC_COLUMN_VALUE', '**PARENT_VIEW**']:
                        continue
                    
                    # Combine parent and child conditions
                    combined_conditions = self.combine_conditions(group_row, child_row)
                    
                    # Check combined conditions
                    if not self.check_context_conditions(combined_conditions, view['view_name']):
                        continue
                    
                    # Create edge
                    edge = {
                        'source_view': view['view_name'],
                        'source_view_type': view.get('view_type', ''),
                        'target_view': target_view,
                        'source_action': child_name,
                        'parent_action': group_name,
                        'action_type': child_row.get('action_type', ''),
                        'action_availability_type': 'via_group',
                        'parent_prominence': group_row.get('action_prominence', ''),
                        'child_prominence': child_row.get('action_prominence', ''),
                        'event_type': event_type,
                        'is_self_loop': 'Yes' if view['view_name'] == target_view else 'No',
                        'must_be_in_views': combined_conditions.get('must_be_in_views', ''),
                        'must_not_be_in_views': combined_conditions.get('must_not_be_in_views', ''),
                        'must_be_viewtype': combined_conditions.get('must_be_viewtype', ''),
                        'must_not_be_viewtype': combined_conditions.get('must_not_be_viewtype', ''),
                        'must_be_table': combined_conditions.get('must_be_table', ''),
                        'must_not_be_table': combined_conditions.get('must_not_be_table', ''),
                        'available_actions': view.get('available_actions', ''),
                        'original_expression': child_row.get('original_expression', ''),
                        # Normalized columns
                        'source_view_normalized': view['view_name'].lower(),
                        'target_view_normalized': target_view.lower(),
                        'source_action_normalized': child_name.lower(),
                        'must_be_in_views_normalized': combined_conditions.get('must_be_in_views', '').lower(),
                        'must_not_be_in_views_normalized': combined_conditions.get('must_not_be_in_views', '').lower(),
                        'must_be_table_normalized': combined_conditions.get('must_be_table', '').lower(),
                        'must_not_be_table_normalized': combined_conditions.get('must_not_be_table', '').lower()
                    }
                    
                    self.edges.append(edge)
                    self.stats['edges_created'] += 1
    
    def process_regular_action(self, target_row: Dict, view: Dict) -> None:
        """Process a regular navigation action and create edge if valid."""
        action_name = target_row.get('source_action', '')
        target_view = target_row.get('target_view', '')

        # Check if action is visible in this view
        if not self.is_action_visible_in_view(target_row, view):
            return
        
        if not target_view:
            return
        
        # Skip special markers
        if target_view in ['DYNAMIC_COLUMN_VALUE', '**PARENT_VIEW**']:
            return
        
        # Check conditions
        if not self.check_context_conditions(target_row, view['view_name']):
            return
        
        # Create edge
        edge = {
            'source_view': view['view_name'],
            'source_view_type': view.get('view_type', ''),
            'target_view': target_view,
            'source_action': action_name,
            'parent_action': '',  # No parent for direct actions
            'action_type': target_row.get('action_type', ''),
            'action_availability_type': 'direct',
            'parent_prominence': target_row.get('action_prominence', ''),
            'child_prominence': '',
            'event_type': '',
            'is_self_loop': 'Yes' if view['view_name'] == target_view else 'No',
            'must_be_in_views': target_row.get('must_be_in_views', ''),
            'must_not_be_in_views': target_row.get('must_not_be_in_views', ''),
            'must_be_viewtype': target_row.get('must_be_viewtype', ''),
            'must_not_be_viewtype': target_row.get('must_not_be_viewtype', ''),
            'must_be_table': target_row.get('must_be_table', ''),
            'must_not_be_table': target_row.get('must_not_be_table', ''),
            'available_actions': view.get('available_actions', ''),
            'original_expression': target_row.get('original_expression', ''),
            # Normalized columns
            'source_view_normalized': view['view_name'].lower(),
            'target_view_normalized': target_view.lower(),
            'source_action_normalized': action_name.lower(),
            'must_be_in_views_normalized': target_row.get('must_be_in_views', '').lower(),
            'must_not_be_in_views_normalized': target_row.get('must_not_be_in_views', '').lower(),
            'must_be_table_normalized': target_row.get('must_be_table', '').lower(),
            'must_not_be_table_normalized': target_row.get('must_not_be_table', '').lower()
        }
        
        self.edges.append(edge)
        self.stats['edges_created'] += 1
    
    def process_event_actions(self, view: Dict) -> None:
        """Process event-triggered actions for a view."""
        event_actions = view.get('event_actions', '')
        if not event_actions or event_actions == '**auto**':
            return
        
        # Determine event type from view configuration
        event_type = 'row selected'  # Default
        config_str = view.get('view_configuration', '')
        if config_str:
            try:
                config = json.loads(config_str)
                events = config.get('Events', [])
                if events and isinstance(events, list) and events[0]:
                    raw_type = events[0].get('EventType', '')
                    if raw_type:
                        event_type = raw_type.lower()
            except:
                pass
        
        # Process each event action
        action_names = [a.strip() for a in event_actions.split('|||') if a.strip()]
        
        for action_name in action_names:
            if action_name not in self.targets_by_action:
                continue
            
            target_rows = self.targets_by_action[action_name]
            
            for target_row in target_rows:
                if target_row.get('action_type') == 'execute_group':
                    # Process group action
                    self.process_group_action(target_row, view, event_type=event_type)
                else:
                    # Process regular action as event-triggered
                    target_view = target_row.get('target_view', '')
                    if not target_view or target_view in ['DYNAMIC_COLUMN_VALUE', '**PARENT_VIEW**']:
                        continue
                    
                    if not self.check_context_conditions(target_row, view['view_name']):
                        continue
                    
                    edge = {
                        'source_view': view['view_name'],
                        'source_view_type': view.get('view_type', ''),
                        'target_view': target_view,
                        'source_action': action_name,
                        'parent_action': '',
                        'action_type': target_row.get('action_type', ''),
                        'action_availability_type': 'event',
                        'parent_prominence': target_row.get('action_prominence', ''),
                        'child_prominence': '',
                        'event_type': event_type,
                        'is_self_loop': 'Yes' if view['view_name'] == target_view else 'No',
                        'must_be_in_views': target_row.get('must_be_in_views', ''),
                        'must_not_be_in_views': target_row.get('must_not_be_in_views', ''),
                        'must_be_viewtype': target_row.get('must_be_viewtype', ''),
                        'must_not_be_viewtype': target_row.get('must_not_be_viewtype', ''),
                        'must_be_table': target_row.get('must_be_table', ''),
                        'must_not_be_table': target_row.get('must_not_be_table', ''),
                        'available_actions': view.get('available_actions', ''),
                        'original_expression': target_row.get('original_expression', ''),
                        # Normalized columns
                        'source_view_normalized': view['view_name'].lower(),
                        'target_view_normalized': target_view.lower(),
                        'source_action_normalized': action_name.lower(),
                        'must_be_in_views_normalized': target_row.get('must_be_in_views', '').lower(),
                        'must_not_be_in_views_normalized': target_row.get('must_not_be_in_views', '').lower(),
                        'must_be_table_normalized': target_row.get('must_be_table', '').lower(),
                        'must_not_be_table_normalized': target_row.get('must_not_be_table', '').lower()
                    }
                    
                    self.edges.append(edge)
                    self.stats['edges_created'] += 1
    
    def process_auto_navigation(self, view: Dict) -> None:
        """Process auto-navigation for table/deck/gallery views."""
        view_type = view.get('view_type', '')
        if view_type not in ['table', 'deck', 'gallery']:
            return
        
        config_str = view.get('view_configuration', '')
        if not config_str or '**auto**' not in config_str:
            return
        
        # Check if there's an explicit Row Selected event action configured
        # If so, don't create an auto-navigation edge
        if config_str:
            try:
                config = json.loads(config_str)
                events = config.get('Events', [])
                for event in events:
                    if (event.get('EventType', '').lower() == 'row selected' and 
                        event.get('EventAction', '') != '**auto**'):
                        # There's an explicit row selected action, skip auto-navigation
                        return
            except:
                pass
        
        data_source = view.get('data_source', '') or view.get('source_table', '')
        if not data_source:
            return
        
        # Find detail views with same data source
        detail_candidates = []
        for other_view in self.views.values():
            if (other_view.get('view_type') == 'detail' and 
                (other_view.get('data_source') == data_source or 
                 other_view.get('source_table') == data_source)):
                detail_candidates.append(other_view)
        
        if not detail_candidates:
            return
        
        # Prefer user views over system views
        user_details = [v for v in detail_candidates if v.get('is_system_view', '').lower() != 'yes']
        selected = user_details if user_details else detail_candidates
        
        # Sort alphabetically and take first
        selected.sort(key=lambda v: v['view_name'])
        target_view_name = selected[0]['view_name']
        
        # Create auto-navigation edge
        edge = {
            'source_view': view['view_name'],
            'target_view': target_view_name,
            'source_action': '**auto**',
            'parent_action': '',
            'action_type': 'auto_navigation',
            'action_availability_type': 'auto',
            'parent_prominence': '',
            'child_prominence': '',
            'event_type': 'row selected',
            'is_self_loop': 'No',
            'must_be_in_views': '',
            'must_not_be_in_views': '',
            'must_be_viewtype': '',
            'must_not_be_viewtype': '',
            'must_be_table': '',
            'must_not_be_table': '',
            'available_actions': view.get('available_actions', ''),
            'original_expression': '',
            # Normalized columns
            'source_view_normalized': view['view_name'].lower(),
            'target_view_normalized': target_view_name.lower(),
            'source_action_normalized': '**auto**',
            'must_be_in_views_normalized': '',
            'must_not_be_in_views_normalized': '',
            'must_be_table_normalized': '',
            'must_not_be_table_normalized': ''
        }
        
        self.edges.append(edge)
        self.stats['edges_created'] += 1

    def process_dashboard_containment(self, view: Dict) -> None:
        """Process dashboard containment relationships (dashboard contains child views)."""
        view_type = view.get('view_type', '')
        if view_type != 'dashboard':
            return
        
        dashboard_entries = view.get('dashboard_view_entries', '')
        if not dashboard_entries:
            return
        
        # Parse the pipe-delimited list of contained views
        contained_views = [v.strip() for v in dashboard_entries.split('|||') if v.strip()]
        
        for target_view in contained_views:
            # Create dashboard containment edge
            edge = {
                'source_view': view['view_name'],
                'source_view_type': 'dashboard',
                'target_view': target_view,
                'source_action': '',
                'parent_action': '',
                'action_type': '',
                'action_availability_type': 'dashboard',
                'parent_prominence': '',
                'child_prominence': '',
                'event_type': '',
                'is_self_loop': 'Yes' if view['view_name'] == target_view else 'No',
                'must_be_in_views': '',
                'must_not_be_in_views': '',
                'must_be_viewtype': '',
                'must_not_be_viewtype': '',
                'must_be_table': '',
                'must_not_be_table': '',
                'available_actions': '',
                'original_expression': '',
                # Normalized columns
                'source_view_normalized': view['view_name'].lower(),
                'target_view_normalized': target_view.lower(),
                'source_action_normalized': '',
                'must_be_in_views_normalized': '',
                'must_not_be_in_views_normalized': '',
                'must_be_table_normalized': '',
                'must_not_be_table_normalized': ''
            }
            
            self.edges.append(edge)
            self.stats['edges_created'] += 1
    
    def process_view(self, view: Dict) -> None:
        """Process all navigation possibilities from a single view."""
        view_name = view['view_name']
        self.stats['views_processed'] += 1
        
        # 1. Process visible actions (those in available_actions that are actually displayed)
        available_actions = view.get('available_actions', '').split('|||') if view.get('available_actions') else []
        available_actions = [a.strip() for a in available_actions if a.strip()]
        
        # Also get referenced_actions from the view to check what's actually visible
        referenced_actions = view.get('referenced_actions', '').split('|||') if view.get('referenced_actions') else []
        referenced_actions = [a.strip() for a in referenced_actions if a.strip()]
        
        # Process all available actions (visibility will be checked per action)
        for action_name in available_actions:
            self.stats['actions_checked'] += 1
            
            # Get target rows for this action
            if action_name not in self.targets_by_action:
                continue
            
            target_rows = self.targets_by_action[action_name]
            
            for target_row in target_rows:
                if target_row.get('action_type') == 'execute_group':
                    # Check if group action is visible before processing
                    if not self.is_action_visible_in_view(target_row, view):
                        continue
                    # Process group action
                    self.process_group_action(target_row, view)
                else:
                    # Process regular action
                    self.process_regular_action(target_row, view)
        
        # 2. Process event actions
        self.process_event_actions(view)
        
        # 3. Process auto-navigation
        self.process_auto_navigation(view)

        # 4. Process dashboard containment
        self.process_dashboard_containment(view)
    
    def write_edges_csv(self) -> None:
        """Write the generated edges to navigation_edges.csv."""
        output_file = self.output_dir / 'navigation_edges.csv'
        
        if not self.edges:
            print(f"  ⚠️  No edges generated")
            return
        
        # Define field order
        fieldnames = [
            # Primary columns
            'source_view',
            'source_view_type',
            'target_view',
            'source_action',
            'parent_action',
            'action_type',
            'action_availability_type',
            'parent_prominence',
            'child_prominence',
            'event_type',
            'is_self_loop',
            # Context conditions
            'must_be_in_views',
            'must_not_be_in_views',
            'must_be_viewtype',
            'must_not_be_viewtype',
            'must_be_table',
            'must_not_be_table',
            'available_actions',
            # Reference
            'original_expression',
            # Normalized columns
            'source_view_normalized',
            'target_view_normalized',
            'source_action_normalized',
            'must_be_in_views_normalized',
            'must_not_be_in_views_normalized',
            'must_be_table_normalized',
            'must_not_be_table_normalized'
        ]
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(self.edges)

        print()
        
        print(f"  ✅ Wrote {len(self.edges)} navigation edges to navigation_edges.csv")
    
    def generate_edges(self) -> Dict:
        """Main method to generate all navigation edges."""
        print("  🎯 Generating navigation edges...")
        
        # Process each view
        for view_name, view in self.views.items():
            self.process_view(view)
        
        # Write output
        self.write_edges_csv()
        
        return self.stats
    
    def run(self) -> bool:
        """Execute the complete edge generation process."""
        print("  📂 Loading required data files...")
        
        # Load required files
        if not self.load_action_targets():
            return False
        
        if not self.load_views():
            return False
        
        # Load optional files (enhance analysis but not required)
        self.load_actions()
        self.load_columns()
        self.load_slices()
        
        # Generate edges
        stats = self.generate_edges()
        
        # Report statistics
        print("\n  📊 Edge Generation Statistics:")
        print(f"     ├─ Views processed: {stats['views_processed']}")
        print(f"     ├─ Actions checked: {stats['actions_checked']}")
        print(f"     ├─ Group actions expanded: {stats['groups_expanded']}")
        print(f"     ├─ Edges created: {stats['edges_created']}")
        print(f"     ├─ Edges blocked by conditions: {stats['edges_blocked_by_conditions']}")
        print(f"     └─ Edges blocked by visibility: {stats['edges_blocked_by_visibility']}")
        
        return True


def run_navigation_edge_generator(output_dir: str, debug_mode: bool = False) -> Dict:
    """Entry point for integration with master parser."""
    generator = NavigationEdgeGenerator(output_dir)
    success = generator.run()
    
    if success:
        return {
            'edges_count': len(generator.edges),
            'stats': generator.stats
        }
    else:
        return {
            'edges_count': 0,
            'stats': generator.stats
        }


def main():
    """Standalone entry point."""
    if len(sys.argv) < 2:
        print("Usage: python navigation_edge_generator.py <output_directory>")
        print("Example: python navigation_edge_generator.py ./20241230_parse/")
        sys.exit(1)
    
    output_dir = sys.argv[1]
    
    if not os.path.exists(output_dir):
        print(f"Error: Directory not found: {output_dir}")
        sys.exit(1)
    
    print("=" * 60)
    print("  PHASE 7: Navigation Edge Generation")
    print("=" * 60)
    
    generator = NavigationEdgeGenerator(output_dir)
    success = generator.run()
    
    if success:
        print("\n  ✅ Navigation edge generation complete!")
    else:
        print("\n  ❌ Navigation edge generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()