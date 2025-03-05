import tkinter as tk
from tkinter import ttk

class ImportDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Import Options")
        self.dialog.geometry("300x150")
        self.result = None
        
        # Create options frame
        options_frame = ttk.Frame(self.dialog, padding="10")
        options_frame.pack(fill=tk.BOTH, expand=True)
        
        # Import mode selection
        ttk.Label(options_frame, text="Import Mode:").pack(pady=5)
        self.import_mode = tk.StringVar(value="append")
        ttk.Radiobutton(options_frame, text="Append to existing symptoms", 
                       variable=self.import_mode, value="append").pack()
        ttk.Radiobutton(options_frame, text="Replace existing symptoms", 
                       variable=self.import_mode, value="replace").pack()
        ttk.Radiobutton(options_frame, text="Merge with existing symptoms", 
                       variable=self.import_mode, value="merge").pack()
        
        # Buttons
        button_frame = ttk.Frame(options_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Continue", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.LEFT, padx=5)
        
        # Make dialog modal
        self.dialog.transient(self.dialog.master)
        self.dialog.grab_set()
        
    def save(self):
        """Save the selected import mode"""
        self.result = self.import_mode.get()
        self.dialog.destroy()
        
    def cancel(self):
        """Cancel the dialog"""
        self.dialog.destroy()