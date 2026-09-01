#!/usr/bin/env python3
"""
Action visibility — CONSOLIDATION_PLAN.md step 1.

A behavior-preserving extraction of the three existing "is this action visible
in this view" implementations: navigation_edge_generator.py (NEG),
actions_orphan_detector.py (AOD), and action_dependency_analyzer.py (ADA). Each
function below is a direct translation of one file's original method — `self`
and instance state replaced by explicit parameters, nothing else changed,
EXCEPT the Do_Not_Display case bug in the AOD strategy
(CONSOLIDATION_PLAN.md section 3's `.replace('_', ' ')` mismatch), fixed by
step 2. The ADA strategy still carries that same bug deliberately — see its
own docstring — and the NEG strategy never had it (it compares the raw
underscored `action_prominence` directly and needed no fix).

All three callers — `action_dependency_analyzer.py` (step 1),
`actions_orphan_detector.py` (step 2), and `navigation_edge_generator.py`
(step 3) — have been switched to this module. The NEG, AOD, and ADA
functions below are each in production use.

Hard constraint carried over from CONSOLIDATION_PLAN.md section 1/section 6:
none of this is called from navigation_edge_generator.py's
`process_group_action` child-edge loop, and it must not be — that loop's
current, deliberate lack of a visibility check is what lets group-membership
invocation routes (STATUS.md, `48eead1`/`f4d931a`) produce edges at all.
"""

from typing import Callable, Dict, Iterable, List, Optional


# --- navigation_edge_generator.py (NEG) -------------------------------------

def _neg_bump(stats: Optional[Dict]) -> None:
    if stats is not None:
        stats['edges_blocked_by_visibility'] = stats.get('edges_blocked_by_visibility', 0) + 1


def is_visible_in_detail_view_neg(action: Dict, view: Dict, stats: Optional[Dict] = None) -> bool:
    """navigation_edge_generator.py's is_action_visible_in_detail_view, unchanged."""
    prominence = action.get('action_prominence', '')
    attach_to_column = action.get('attach_to_column', '')

    # Primary, Display_Prominently, and Display_Inline all work in detail views
    if prominence in ['Primary', 'Display_Prominently', 'Display_Inline', 'Display_Overlay']:
        # For inline actions, check column visibility
        if prominence == 'Display_Inline' and attach_to_column:
            view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
            view_columns = [c.strip() for c in view_columns if c.strip()]

            if attach_to_column not in view_columns:
                _neg_bump(stats)
                return False

        return True

    # Unknown prominence - be conservative
    _neg_bump(stats)
    return False


def is_visible_in_deck_view_neg(action: Dict, view: Dict, stats: Optional[Dict] = None) -> bool:
    """navigation_edge_generator.py's is_action_visible_in_deck_view, unchanged.

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
        return True

    # If we get here, the action is not in the action bar
    # Deck views don't support other display methods
    _neg_bump(stats)
    return False


def is_visible_in_table_view_neg(action: Dict, view: Dict, stats: Optional[Dict] = None) -> bool:
    """navigation_edge_generator.py's is_action_visible_in_table_view, unchanged.

    Table views do NOT have action bars, so they only support:
    - Display_Overlay (editor Position "Primary"), as a floating button over the rows
    - Display_Inline actions attached to visible columns
    - Event-triggered actions (handled separately)
    """
    prominence = action.get('action_prominence', '')
    attach_to_column = action.get('attach_to_column', '')

    # Do_Not_Display actions are never visible
    if prominence == 'Do_Not_Display':
        _neg_bump(stats)
        return False

    # Display_Overlay (editor Position "Primary") displays on table views as a
    # floating button, confirmed by live app test 2026-08-31 — see
    # APPSHEET_BEHAVIOR.md's "Observed behavior" section.
    if prominence == 'Display_Overlay':
        return True
    elif prominence == 'Display_Inline' and attach_to_column:
        # Inline actions must be attached to a visible column
        view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
        view_columns = [c.strip() for c in view_columns if c.strip()]

        if attach_to_column not in view_columns:
            _neg_bump(stats)
            return False
        return True
    else:
        # Table views don't support Display_Prominently
        _neg_bump(stats)
        return False


def is_visible_in_view_neg(action: Dict, view: Dict, stats: Optional[Dict] = None) -> bool:
    """navigation_edge_generator.py's is_action_visible_in_view, unchanged.

    `stats`, if given, is mutated the way the original mutated
    `self.stats['edges_blocked_by_visibility']` — a dict-like object supporting
    `.get`/`__setitem__` is sufficient; pass `self.stats` itself to reproduce the
    original side effect exactly.
    """
    action_name = action.get('source_action', '')
    prominence = action.get('action_prominence', '')
    view_type = view.get('view_type', '').lower()

    # Do_Not_Display actions are never visible, except when this specific view's
    # own custom-canvas Layout binds the action directly via an onClick handler
    # (the action is the button, so it has no separate on-screen prominence).
    if prominence == 'Do_Not_Display':
        onclick_actions = view.get('onclick_actions', '').split('|||') if view.get('onclick_actions') else []
        onclick_actions = [a.strip() for a in onclick_actions if a.strip()]
        if action_name not in onclick_actions:
            _neg_bump(stats)
            return False

    # Check if action is in available_actions
    available_actions = view.get('available_actions', '').split('|||') if view.get('available_actions') else []
    available_actions = [a.strip() for a in available_actions if a.strip()]

    if action_name not in available_actions:
        _neg_bump(stats)
        return False

    # View-type-specific visibility rules
    if view_type == 'detail':
        return is_visible_in_detail_view_neg(action, view, stats)
    elif view_type == 'deck':
        return is_visible_in_deck_view_neg(action, view, stats)
    elif view_type == 'table':
        return is_visible_in_table_view_neg(action, view, stats)
    else:
        # For now, other view types just check available_actions
        return True


# --- action_dependency_analyzer.py (ADA) ------------------------------------

def is_visible_in_view_ada(action: Dict, view: Dict) -> bool:
    """action_dependency_analyzer.py's is_action_visible_in_view, unchanged.

    Carries the '.replace('_', ' ')' Do_Not_Display case bug as-is
    (CONSOLIDATION_PLAN.md section 3). Deliberately NOT fixed by step 2:
    ADA has been live on this module since step 1 (`84a651d`), so fixing its
    copy now would change what the interactive dependency browser reports —
    a real behavior change outside what step 2 predicts, and outside what
    step 2's verification would catch, since ADA writes no CSV. Left for its
    own, later step, with its own before/after verification.

    Note ADA's function boundary (CONSOLIDATION_PLAN.md section 2's Pre-gates):
    unlike NEG and AOD, the available_actions gate is in ADA's *caller*
    (analyze_view_dependencies), not in this function. Preserved here rather
    than folded in, so the extraction changes no verdict and no boundary.
    """
    action_name = action.get('action_name', '')
    prominence = action.get('action_prominence', '').replace('_', ' ')
    attach_to_column = action.get('attach_to_column', '')

    # Check if view is actually shown
    show_if = view.get('show_if', '').strip()
    if show_if.lower() == 'false':
        return False

    view_type = view.get('view_type', '').lower()

    # Check visibility based on view type and prominence
    if view_type == 'detail':
        if prominence in ['Display Prominently', 'Display Overlay']:
            return True
        elif prominence == 'Display Inline' and attach_to_column:
            # Check if column is visible in view - EXACT MATCH
            view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
            view_columns = [col.strip() for col in view_columns]
            return attach_to_column in view_columns  # Exact match, not substring

    elif view_type == 'table':
        if prominence == 'Display Inline' and attach_to_column:
            # Check if column is visible in view - EXACT MATCH
            view_columns = view.get('view_columns', '').split('|||') if view.get('view_columns') else []
            view_columns = [col.strip() for col in view_columns]
            return attach_to_column in view_columns  # Exact match, not substring

    elif view_type in ['deck', 'gallery']:
        if view.get('show_action_bar', '').lower() == 'true':
            if prominence != 'Do not display':
                if view.get('action_display_mode', '') == 'Manual':
                    # For Manual mode, must also be in referenced_actions
                    ref_actions = view.get('referenced_actions', '').split('|||') if view.get('referenced_actions') else []
                    return action_name in [r.strip() for r in ref_actions]
                else:  # Automatic mode
                    return True

    return False


# --- actions_orphan_detector.py (AOD) ---------------------------------------

def is_visible_in_views_aod(
    action: Dict,
    views: Iterable[Dict],
    unused_system_views,
    column_exists: Callable[[str, str], bool],
) -> bool:
    """actions_orphan_detector.py's is_action_visible_in_views, with the
    Do_Not_Display case bug fixed (CONSOLIDATION_PLAN.md step 2).

    Existential, not pointwise: loops every view and returns True at the first
    match (CONSOLIDATION_PLAN.md section 1). `column_exists` replaces the
    original's lazily-cached `self.column_exists` method — pass a callable with
    the same `(column_name, table_name) -> bool` signature.

    CONSOLIDATION_PLAN.md section 3: the original compared
    `action_prominence.replace('_', ' ')` against spaced literals
    ('Display Prominently', etc.). Three of four values round-trip correctly
    through that transform; 'Do_Not_Display' does not — it becomes 'Do Not
    Display' (title case), which never matches the comparison target 'Do not
    display' (sentence case), so the intended Hide exclusion on deck/gallery
    never fired. Per section 4's second exclusion, the fix is to stop
    transforming the string, not to compare loosely: `prominence` is now
    compared against the real underscored values directly, and the four
    literals below are underscored to match — not a new rule, the same
    literal comparison the original always meant to make.
    """
    action_name = action.get('action_name', '')
    action_name_lower = action_name.lower()
    prominence = action.get('action_prominence', '')
    attach_to_column = action.get('attach_to_column', '')
    source_table = action.get('source_table', '')  # Add this

    # If only_if_condition is explicitly false, action is never visible
    only_if = action.get('only_if_condition', '').strip().lower()
    if only_if == 'false':
        return False

    for view in views:
        # Skip unused system views
        if view['view_name'].lower() in unused_system_views:
            continue

        # Check if view is actually shown
        show_if = view.get('show_if', '').strip()
        if show_if.lower() == 'false':
            continue

        # Get available actions for this view
        available_actions = [a.strip().lower() for a in view['available_actions'].split('|||') if a.strip()]

        # Action must be in available_actions
        if action_name_lower not in available_actions:
            continue

        # NEW: Check if view's data source matches action's source table
        view_source = view.get('source_table', '') or view.get('data_source', '')
        if source_table and view_source and source_table != view_source:
            # Action is for a different table than this view
            continue

        view_type = view['view_type'].lower()

        # Check visibility based on view type and prominence
        if view_type == 'detail':
            if prominence in ['Display_Prominently', 'Display_Overlay']:
                return True
            elif prominence == 'Display_Inline' and attach_to_column:
                # Check if column is visible in view
                view_columns = [c.strip() for c in view['view_columns'].split('|||') if c.strip()]

                # NEW: Also verify the column actually exists in the table
                if attach_to_column in view_columns:
                    # Should also check if column exists in appsheet_columns.csv
                    if column_exists(attach_to_column, source_table):
                        return True

        elif view_type == 'table':
            # Display_Overlay (editor Position "Primary") displays on table
            # views regardless of action type, confirmed by live app test
            # 2026-08-31 — see APPSHEET_BEHAVIOR.md's "Observed behavior" section.
            if prominence == 'Display_Overlay':
                return True
            if prominence == 'Display_Inline' and attach_to_column:
                # Check if column is visible in view
                view_columns = [c.strip() for c in view['view_columns'].split('|||') if c.strip()]
                if attach_to_column in view_columns:
                    # Should also check if column exists in appsheet_columns.csv
                    if column_exists(attach_to_column, source_table):
                        return True

        elif view_type in ['deck', 'gallery']:
            if view.get('show_action_bar', '').lower() == 'true':
                if prominence != 'Do_Not_Display':
                    if view.get('action_display_mode', '') == 'Manual':
                        # For Manual mode, must also be in referenced_actions
                        ref_actions = [a.strip().lower() for a in view['referenced_actions'].split('|||') if a.strip()]
                        if action_name_lower in ref_actions:
                            return True
                    else:  # Automatic mode
                        return True

    return False
