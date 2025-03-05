import csv
from datetime import datetime
import os

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry

from data.symptom_set import Symptom
from ui.symptom_dialog import SymptomDialog
from ui.symptom_import_dialog import ImportDialog

class SymptomWindow:
    def __init__(self, parent, symptom_file):
        self.window = tk.Toplevel(parent)
        self.window.title("Symptom Management")
        self.window.geometry("1000x600")
        
        # Track active window for focus management
        self.active_window = None
        
        self.symptom_file = symptom_file
        self.symptoms = []
        self.load_symptoms()
        
        # Sorting variables
        self.sort_column = None
        self.sort_reverse = False
        
        # Search and filter variables
        self.search_text = tk.StringVar()
        self.show_resolved = tk.BooleanVar(value=False)
        self.search_text.trace('w', self.apply_filters)
        
        # Date range variables
        self.start_date = None
        self.end_date = None
        
        self.setup_ui()
        
    def show_message(self, title, message, type="info"):
        """Show a message box while maintaining window focus"""
        # Store current focus
        self.active_window = self.window.focus_get()
        
        # Show message box
        if type == "error":
            messagebox.showerror(title, message)
        elif type == "warning":
            messagebox.showwarning(title, message)
        else:
            messagebox.showinfo(title, message)
            
        # Restore focus if possible
        if self.active_window and self.active_window.winfo_exists():
            self.active_window.focus_set()
            
    def load_symptoms(self):
        """Load symptoms from CSV file"""
        if os.path.exists(self.symptom_file):
            try:
                with open(self.symptom_file, 'r') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        try:
                            symptom = Symptom(row)
                            self.symptoms.append(symptom)
                        except Exception as e:
                            print(f"Error loading symptom: {str(e)}")
            except Exception as e:
                print(f"Error reading symptom file: {str(e)}")
                
    def save_symptoms(self):
        """Save symptoms to CSV file"""
        try:
            with open(self.symptom_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Name', 'Start Date', 'End Date', 'Medications', 'Stimulants', 'Comment', 'Severity'])
                
                for symptom in self.symptoms:
                    writer.writerow([
                        symptom.name,
                        symptom.start_date.strftime('%Y-%m-%d') if symptom.start_date else '',
                        symptom.end_date.strftime('%Y-%m-%d') if symptom.end_date else '',
                        ','.join(symptom.medications),
                        ','.join(symptom.stimulants),
                        symptom.comment,
                        str(symptom.severity)
                    ])
        except Exception as e:
            self.show_message("Error", f"Failed to save symptoms: {str(e)}", "error")
            
    def setup_ui(self):
        # Create main container
        main_container = ttk.Frame(self.window, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create toolbar
        toolbar = ttk.Frame(main_container)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # Left side buttons
        left_buttons = ttk.Frame(toolbar)
        left_buttons.pack(side=tk.LEFT)
        
        ttk.Button(left_buttons, text="Add Symptom", command=self.add_symptom).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_buttons, text="Edit Symptom", command=self.edit_symptom).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_buttons, text="Delete Symptom", command=self.delete_symptom).pack(side=tk.LEFT, padx=5)
        ttk.Button(left_buttons, text="Save Changes", command=self.save_symptoms).pack(side=tk.LEFT, padx=5)
        
        # Right side buttons (Import/Export)
        right_buttons = ttk.Frame(toolbar)
        right_buttons.pack(side=tk.RIGHT)
        
        ttk.Button(right_buttons, text="Import CSV", command=self.import_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons, text="Export CSV", command=self.export_csv).pack(side=tk.LEFT, padx=5)
        
        # Create search and filter frame
        search_frame = ttk.Frame(main_container)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search box
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_text, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)
        
        # Date range frame
        date_frame = ttk.LabelFrame(search_frame, text="Date Range", padding="5")
        date_frame.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(date_frame, text="From:").pack(side=tk.LEFT, padx=2)
        self.start_date_picker = DateEntry(date_frame, width=12, background='darkblue',
                                         foreground='white', borderwidth=2,
                                         date_pattern='yyyy-mm-dd')
        self.start_date_picker.pack(side=tk.LEFT, padx=2)
        self.start_date_picker.bind('<<DateEntrySelected>>', self.apply_filters)
        
        ttk.Label(date_frame, text="To:").pack(side=tk.LEFT, padx=2)
        self.end_date_picker = DateEntry(date_frame, width=12, background='darkblue',
                                       foreground='white', borderwidth=2,
                                       date_pattern='yyyy-mm-dd')
        self.end_date_picker.pack(side=tk.LEFT, padx=2)
        self.end_date_picker.bind('<<DateEntrySelected>>', self.apply_filters)
        
        # Show resolved checkbox
        ttk.Checkbutton(search_frame, text="Show Resolved Symptoms", 
                       variable=self.show_resolved,
                       command=self.apply_filters).pack(side=tk.LEFT, padx=5)
        
        # Create treeview for symptoms
        columns = ('Name', 'Start Date', 'End Date', 'Medications', 'Stimulants', 'Comment', 'Severity')
        self.tree = ttk.Treeview(main_container, columns=columns, show='headings')
        
        # Set column headings and bind click events
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by_column(c))
            self.tree.column(col, width=100)
            
        # Add scrollbar
        scrollbar = ttk.Scrollbar(main_container, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate treeview
        self.refresh_symptoms()
        
    def apply_filters(self, *args):
        """Apply search and resolved filters"""
        search_term = self.search_text.get().lower()
        
        # Get date range
        try:
            start_date = self.start_date_picker.get_date()
            end_date = self.end_date_picker.get_date()
        except Exception:
            start_date = None
            end_date = None
        
        # Filter symptoms based on search term, resolved status, and date range
        filtered_symptoms = []
        for symptom in self.symptoms:
            # Check if symptom matches resolved filter
            if not self.show_resolved.get() and symptom.is_resolved:
                continue
                
            # Check if symptom matches date range
            if start_date and end_date:
                symptom_start = symptom.start_date if symptom.start_date else datetime.min
                symptom_end = symptom.end_date if symptom.end_date else datetime.max
                
                # Check if symptom overlaps with date range
                if not (symptom_start <= end_date and symptom_end >= start_date):
                    continue
            
            # Check if symptom matches search term
            if search_term:
                # Search in all relevant fields
                if (search_term in symptom.name.lower() or
                    search_term in ','.join(symptom.medications).lower() or
                    search_term in ','.join(symptom.stimulants).lower() or
                    search_term in symptom.comment.lower()):
                    filtered_symptoms.append(symptom)
            else:
                filtered_symptoms.append(symptom)
                
        # Apply current sort if any
        if self.sort_column:
            col_idx = self.tree['columns'].index(self.sort_column)
            filtered_symptoms.sort(key=lambda x: self.get_sort_key(x, col_idx), 
                                 reverse=self.sort_reverse)
            
        # Update display with filtered symptoms
        self.refresh_symptoms(filtered_symptoms)
        
    def sort_by_column(self, column):
        """Sort the treeview by the specified column"""
        # Get the column index
        col_idx = self.tree['columns'].index(column)
        
        # If clicking the same column, reverse the sort
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
            
        # Update column heading to show sort direction
        for col in self.tree['columns']:
            self.tree.heading(col, text=col)
        self.tree.heading(column, text=f"{column} {'↓' if self.sort_reverse else '↑'}")
        
        # Apply filters and sort
        self.apply_filters()
        
    def get_sort_key(self, symptom, col_idx):
        """Get the sort key for a symptom based on column index"""
        if col_idx == 0:  # Name
            return symptom.name
        elif col_idx == 1:  # Start Date
            return symptom.start_date if symptom.start_date else datetime.min
        elif col_idx == 2:  # End Date
            return symptom.end_date if symptom.end_date else datetime.max
        elif col_idx == 3:  # Medications
            return ','.join(symptom.medications)
        elif col_idx == 4:  # Stimulants
            return ','.join(symptom.stimulants)
        elif col_idx == 5:  # Comment
            return symptom.comment
        elif col_idx == 6:  # Severity
            return symptom.severity
        return ''
        
    def refresh_symptoms(self, symptoms_to_show=None):
        """Refresh the symptom list in the treeview"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Use provided symptoms list or apply filters
        symptoms = symptoms_to_show if symptoms_to_show is not None else self.symptoms
            
        # Add symptoms to treeview
        for symptom in symptoms:
            self.tree.insert('', tk.END, values=(
                symptom.name,
                symptom.start_date.strftime('%Y-%m-%d') if symptom.start_date else '',
                symptom.end_date.strftime('%Y-%m-%d') if symptom.end_date else '',
                ','.join(symptom.medications),
                ','.join(symptom.stimulants),
                symptom.comment,
                str(symptom.severity)
            ))
            
    def add_symptom(self):
        """Open dialog to add a new symptom"""
        dialog = SymptomDialog(self.window)
        if dialog.result:
            self.symptoms.append(dialog.result)
            self.refresh_symptoms()
            
    def edit_symptom(self):
        """Open dialog to edit selected symptom"""
        selection = self.tree.selection()
        if not selection:
            self.show_message("Warning", "Please select a symptom to edit", "warning")
            return
            
        # Get selected symptom
        item = self.tree.item(selection[0])
        values = item['values']
        
        # Find matching symptom
        for symptom in self.symptoms:
            if (symptom.name == values[0] and
                (symptom.start_date.strftime('%Y-%m-%d') if symptom.start_date else '') == values[1] and
                (symptom.end_date.strftime('%Y-%m-%d') if symptom.end_date else '') == values[2]):
                dialog = SymptomDialog(self.window, symptom)
                if dialog.result:
                    # Update symptom
                    symptom.name = dialog.result.name
                    symptom.start_date = dialog.result.start_date
                    symptom.end_date = dialog.result.end_date
                    symptom.medications = dialog.result.medications
                    symptom.stimulants = dialog.result.stimulants
                    symptom.comment = dialog.result.comment
                    symptom.severity = dialog.result.severity
                    self.refresh_symptoms()
                break
                
    def delete_symptom(self):
        """Delete selected symptom"""
        selection = self.tree.selection()
        if not selection:
            self.show_message("Warning", "Please select a symptom to delete", "warning")
            return
            
        if messagebox.askyesno("Confirm", "Are you sure you want to delete this symptom?"):
            # Get selected symptom
            item = self.tree.item(selection[0])
            values = item['values']
            
            # Find and remove matching symptom
            for symptom in self.symptoms[:]:
                if (symptom.name == values[0] and
                    (symptom.start_date.strftime('%Y-%m-%d') if symptom.start_date else '') == values[1] and
                    (symptom.end_date.strftime('%Y-%m-%d') if symptom.end_date else '') == values[2]):
                    self.symptoms.remove(symptom)
                    break
                    
            self.refresh_symptoms()

    def import_csv(self):
        """Import symptoms from a CSV file"""
        file_path = filedialog.askopenfilename(
            title="Import Symptoms",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        # Show import options dialog
        import_dialog = ImportDialog(self.window)
        self.window.wait_window(import_dialog.dialog)
        
        if not import_dialog.result:
            return
            
        import_mode = import_dialog.result
            
        try:
            new_symptoms = []
            error_count = 0
            
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)  # Skip header
                
                # Validate header
                expected_header = ['Name', 'Start Date', 'End Date', 'Medications', 'Stimulants', 'Comment', 'Severity']
                if header != expected_header:
                    self.show_message("Error", "Invalid CSV format. Expected columns: " + ", ".join(expected_header), "error")
                    return
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        symptom = Symptom(row)
                        new_symptoms.append(symptom)
                    except Exception as e:
                        error_count += 1
                        print(f"Error in row {row_num}: {str(e)}")
            
            if error_count > 0:
                if messagebox.askyesno("Warning", 
                    f"Found {error_count} invalid rows. Continue importing valid rows?"):
                    self.process_import(new_symptoms, import_mode)
            else:
                self.process_import(new_symptoms, import_mode)
                
        except Exception as e:
            self.show_message("Error", f"Failed to import CSV: {str(e)}", "error")
            
    def process_import(self, new_symptoms, import_mode):
        """Process the imported symptoms based on the selected mode"""
        if import_mode == "append":
            self.symptoms.extend(new_symptoms)
            self.show_message("Success", f"Appended {len(new_symptoms)} symptoms successfully.")
        elif import_mode == "replace":
            self.symptoms = new_symptoms
            self.show_message("Success", f"Replaced all symptoms with {len(new_symptoms)} new symptoms.")
        elif import_mode == "merge":
            # Merge based on name and dates
            merged_count = 0
            for new_symptom in new_symptoms:
                found = False
                for existing_symptom in self.symptoms:
                    if (existing_symptom.name == new_symptom.name and
                        existing_symptom.start_date == new_symptom.start_date and
                        existing_symptom.end_date == new_symptom.end_date):
                        # Update existing symptom
                        existing_symptom.medications = new_symptom.medications
                        existing_symptom.stimulants = new_symptom.stimulants
                        existing_symptom.comment = new_symptom.comment
                        existing_symptom.severity = new_symptom.severity
                        found = True
                        merged_count += 1
                        break
                if not found:
                    self.symptoms.append(new_symptom)
            self.show_message("Success", 
                f"Merged {merged_count} existing symptoms and added {len(new_symptoms) - merged_count} new symptoms.")
        
        self.refresh_symptoms()

    def export_csv(self):
        """Export symptoms to a CSV file"""
        file_path = filedialog.asksaveasfilename(
            title="Export Symptoms",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Name', 'Start Date', 'End Date', 'Medications', 'Stimulants', 'Comment', 'Severity'])
                
                for symptom in self.symptoms:
                    writer.writerow([
                        symptom.name,
                        symptom.start_date.strftime('%Y-%m-%d') if symptom.start_date else '',
                        symptom.end_date.strftime('%Y-%m-%d') if symptom.end_date else '',
                        ','.join(symptom.medications),
                        ','.join(symptom.stimulants),
                        symptom.comment,
                        str(symptom.severity)
                    ])
                    
            self.show_message("Success", f"Exported {len(self.symptoms)} symptoms successfully.")
            
        except Exception as e:
            self.show_message("Error", f"Failed to export CSV: {str(e)}", "error")
