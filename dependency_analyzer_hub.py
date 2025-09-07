#!/usr/bin/env python3
"""
Dependency Analyzer Hub - Central menu for all dependency analyzers
"""

import sys
from pathlib import Path

class DependencyAnalyzerHub:
    def __init__(self, base_path="."):
        self.base_path = Path(base_path)
        
    def show_main_menu(self):
        """Display the main dependency analysis menu."""
        while True:
            print("\n" + "="*70)
            print("DEPENDENCY ANALYSIS HUB")
            print("="*70)
            print("\nSelect analysis type:")
            print("  1. Column dependencies")
            print("  2. Action dependencies")  
            print("  3. View dependencies")
            print("  4. Exit")
            
            try:
                choice = input("\nEnter your choice (1-4): ").strip()
                
                if choice == '1':
                    self.run_column_analyzer()
                elif choice == '2':
                    self.run_action_analyzer()
                elif choice == '3':
                    self.run_view_analyzer()
                elif choice == '4':
                    print("\nExiting dependency analysis. Goodbye!")
                    break
                else:
                    print("Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n\nExiting dependency analysis. Goodbye!")
                break
                
    def run_column_analyzer(self):
        """Import and run the column dependency analyzer."""
        try:
            from column_dependency_analyzer import ColumnDependencyAnalyzer
            analyzer = ColumnDependencyAnalyzer(self.base_path)
            analyzer.run(return_to_hub=True)  # Modified to accept parameter
        except ImportError as e:
            print(f"\nError: Could not import column analyzer: {e}")
            input("Press Enter to continue...")
            
    def run_action_analyzer(self):
        """Import and run the action dependency analyzer."""
        try:
            from action_dependency_analyzer import ActionDependencyAnalyzer
            analyzer = ActionDependencyAnalyzer(self.base_path)
            analyzer.run(return_to_hub=True)  # Modified to accept parameter
        except ImportError as e:
            print(f"\nError: Could not import action analyzer: {e}")
            input("Press Enter to continue...")

    def run_view_analyzer(self):
        """Import and run the view dependency analyzer."""
        try:
            from view_dependency_analyzer import ViewDependencyAnalyzer
            analyzer = ViewDependencyAnalyzer(self.base_path)
            analyzer.run(return_to_hub=True)
        except ImportError as e:
            print(f"\nError: Could not import view analyzer: {e}")
            input("Press Enter to continue...")
            
    def run(self):
        """Main entry point."""
        self.show_main_menu()

def main():
    """Standalone entry point."""
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Validate path exists
    path = Path(base_path)
    if not path.exists():
        print(f"Error: Path '{base_path}' does not exist.")
        sys.exit(1)
        
    hub = DependencyAnalyzerHub(base_path)
    hub.run()

if __name__ == "__main__":
    main()