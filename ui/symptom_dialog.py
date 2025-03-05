from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from data.symptom_set import Symptom


class SymptomDialog:
    def __init__(self, parent, symptom=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Symptom Details")
        self.dialog.geometry("400x500")
        self.result = None
        
        # Variables
        self.name = tk.StringVar(value=symptom.name if symptom else '')
        self.start_date = tk.StringVar(value=symptom.start_date.strftime('%Y-%m-%d') if symptom and symptom.start_date else '')
        self.end_date = tk.StringVar(value=symptom.end_date.strftime('%Y-%m-%d') if symptom and symptom.end_date else '')
        self.medications = tk.StringVar(value=','.join(symptom.medications) if symptom else '')
        self.stimulants = tk.StringVar(value=','.join(symptom.stimulants) if symptom else '')
        self.comment = tk.StringVar(value=symptom.comment if symptom else '')
        self.severity = tk.StringVar(value=str(symptom.severity) if symptom else '1')
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create form
        form = ttk.Frame(self.dialog, padding="10")
        form.pack(fill=tk.BOTH, expand=True)
        
        # Name
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.name).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Start Date
        ttk.Label(form, text="Start Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.start_date).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # End Date
        ttk.Label(form, text="End Date (YYYY-MM-DD):").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.end_date).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Medications
        ttk.Label(form, text="Medications (comma-separated):").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.medications).grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Stimulants
        ttk.Label(form, text="Stimulants (comma-separated):").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.stimulants).grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Comment
        ttk.Label(form, text="Comment:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.comment).grid(row=5, column=1, sticky=tk.W, pady=5)
        
        # Severity
        ttk.Label(form, text="Severity (1-10):").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.severity).grid(row=6, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(form)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Make dialog modal
        self.dialog.transient(self.dialog.master)
        self.dialog.grab_set()
        
    def save(self):
        """Save the symptom data"""
        try:
            # Validate required fields
            if not self.name.get():
                messagebox.showerror("Error", "Name is required")
                return
                
            # Parse dates
            start_date = None
            end_date = None
            
            if self.start_date.get():
                start_date = datetime.strptime(self.start_date.get(), '%Y-%m-%d')
            if self.end_date.get():
                end_date = datetime.strptime(self.end_date.get(), '%Y-%m-%d')
                
            # Parse severity
            try:
                severity = int(self.severity.get())
                if severity < 1 or severity > 10:
                    raise ValueError("Severity must be between 1 and 10")
            except ValueError as e:
                messagebox.showerror("Error", str(e))
                return
                
            # Create symptom
            row = [
                self.name.get(),
                self.start_date.get(),
                self.end_date.get(),
                self.medications.get(),
                self.stimulants.get(),
                self.comment.get(),
                str(severity)
            ]
            
            self.result = Symptom(row)
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Invalid data: {str(e)}")
            
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy() 