import os
import json
import csv

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from parse_data import HealthDataParseArgs, DataParser
from ui.statistics_window import StatisticsWindow
from ui.symptom_window import SymptomWindow

class HealthDataParserUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Apple Health Data Parser")
        self.root.geometry("1200x800")
        
        # Variables
        self.export_dir = tk.StringVar()
        self.symptom_data = tk.StringVar()
        self.food_data = tk.StringVar()
        self.extra_observations = tk.StringVar()
        self.start_year = tk.StringVar(value="2000")
        self.skip_dates = tk.StringVar()
        self.skip_long_values = tk.BooleanVar(value=True)
        self.json_add_all_vitals = tk.BooleanVar(value=False)
        self.filter_abnormal_in_range = tk.BooleanVar(value=False)
        self.in_range_abnormal_boundary = tk.StringVar(value="0.15")
        self.report_highlight_abnormal_results = tk.BooleanVar(value=True)
        
        # Track active window
        self.active_window = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create main container with two columns
        main_container = ttk.Frame(self.root, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Left column - Input and Configuration
        left_frame = ttk.LabelFrame(main_container, text="Input & Configuration", padding="5")
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Apple Health Export Directory
        ttk.Label(left_frame, text="Apple Health Export Directory:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(left_frame, textvariable=self.export_dir, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(left_frame, text="Browse", command=self.browse_export_dir).grid(row=0, column=2)
        
        # Supplementary Data Files
        ttk.Label(left_frame, text="Supplementary Data Files", font=('Helvetica', 10, 'bold')).grid(row=1, column=0, columnspan=3, pady=10)
        
        ttk.Label(left_frame, text="Symptom Data:").grid(row=2, column=0, sticky=tk.W)
        symptom_frame = ttk.Frame(left_frame)
        symptom_frame.grid(row=2, column=1, columnspan=2, sticky=tk.W)
        ttk.Entry(symptom_frame, textvariable=self.symptom_data, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(symptom_frame, text="Browse", command=lambda: self.browse_file(self.symptom_data)).pack(side=tk.LEFT)
        ttk.Button(symptom_frame, text="Manage", command=self.manage_symptoms).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(left_frame, text="Food Data:").grid(row=3, column=0, sticky=tk.W)
        ttk.Entry(left_frame, textvariable=self.food_data, width=50).grid(row=3, column=1, padx=5)
        ttk.Button(left_frame, text="Browse", command=lambda: self.browse_file(self.food_data)).grid(row=3, column=2)
        
        ttk.Label(left_frame, text="Extra Observations:").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(left_frame, textvariable=self.extra_observations, width=50).grid(row=4, column=1, padx=5)
        ttk.Button(left_frame, text="Browse", command=lambda: self.browse_file(self.extra_observations)).grid(row=4, column=2)
        
        # Configuration Options
        ttk.Label(left_frame, text="Configuration Options", font=('Helvetica', 10, 'bold')).grid(row=5, column=0, columnspan=3, pady=10)
        
        ttk.Label(left_frame, text="Start Year:").grid(row=6, column=0, sticky=tk.W)
        ttk.Entry(left_frame, textvariable=self.start_year, width=10).grid(row=6, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(left_frame, text="Skip Dates (YYYY-MM-DD,YYYY-MM-DD):").grid(row=7, column=0, sticky=tk.W)
        ttk.Entry(left_frame, textvariable=self.skip_dates, width=50).grid(row=7, column=1, padx=5)
        
        ttk.Checkbutton(left_frame, text="Skip Long Values", variable=self.skip_long_values).grid(row=8, column=0, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(left_frame, text="Add All Vitals to JSON", variable=self.json_add_all_vitals).grid(row=9, column=0, columnspan=2, sticky=tk.W)
        ttk.Checkbutton(left_frame, text="Filter Abnormal In Range", variable=self.filter_abnormal_in_range).grid(row=10, column=0, columnspan=2, sticky=tk.W)
        
        ttk.Label(left_frame, text="In Range Abnormal Boundary:").grid(row=11, column=0, sticky=tk.W)
        ttk.Entry(left_frame, textvariable=self.in_range_abnormal_boundary, width=10).grid(row=11, column=1, sticky=tk.W, padx=5)
        
        ttk.Checkbutton(left_frame, text="Highlight Abnormal Results", variable=self.report_highlight_abnormal_results).grid(row=12, column=0, columnspan=2, sticky=tk.W)
        
        # Button Frame
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=13, column=0, columnspan=3, pady=20)
        
        # Generate Report Button
        ttk.Button(button_frame, text="Generate Report", command=self.generate_report).pack(side=tk.LEFT, padx=5)
        
        # View Statistics Button
        ttk.Button(button_frame, text="View Statistics", command=self.open_statistics).pack(side=tk.LEFT, padx=5)
        
        # Right column - Statistics and Graphs
        right_frame = ttk.LabelFrame(main_container, text="Statistics & Graphs", padding="5")
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Add placeholder for statistics
        self.stats_text = tk.Text(right_frame, height=10, width=50)
        self.stats_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Add placeholder for graphs
        self.graph_frame = ttk.Frame(right_frame)
        self.graph_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Configure grid weights
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=2)
        left_frame.columnconfigure(1, weight=1)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
    def browse_export_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.export_dir.set(directory)
            
    def browse_file(self, variable):
        filename = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if filename:
            variable.set(filename)
            
    def show_message(self, title, message, type="info"):
        """Show a message box while maintaining window focus"""
        # Store current focus
        self.active_window = self.root.focus_get()
        
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
            
    def generate_report(self):
        if not self.export_dir.get():
            self.show_message("Error", "Please select an Apple Health export directory", "error")
            return
            
        try:
            # Create parse arguments
            parse_args = HealthDataParseArgs(self.export_dir.get())
            
            # Set additional arguments from UI
            parse_args.start_year = int(self.start_year.get())
            parse_args.skip_dates = self.skip_dates.get().split(",") if self.skip_dates.get() else []
            parse_args.skip_long_values = self.skip_long_values.get()
            parse_args.json_add_all_vitals = self.json_add_all_vitals.get()
            parse_args.skip_in_range_abnormal_results = self.filter_abnormal_in_range.get()
            parse_args.in_range_abnormal_boundary = float(self.in_range_abnormal_boundary.get())
            parse_args.report_highlight_abnormal_results = self.report_highlight_abnormal_results.get()
            
            if self.symptom_data.get():
                parse_args.symptom_data_csv = self.symptom_data.get()
            if self.food_data.get():
                parse_args.food_data_csv = self.food_data.get()
            if self.extra_observations.get():
                parse_args.extra_observations_csv = self.extra_observations.get()
            
            # Run parser
            parser = DataParser(parse_args)
            parser.run()
            
            # Update statistics and graphs
            self.update_statistics()
            
            self.show_message("Success", "Report generated successfully!")
            
        except Exception as e:
            self.show_message("Error", f"Failed to generate report: {str(e)}", "error")
            
    def update_statistics(self):
        # Clear existing content
        self.stats_text.delete(1.0, tk.END)
        
        # Read and display statistics from the generated files
        try:
            if os.path.exists(parse_args.all_data_json):
                with open(parse_args.all_data_json, 'r') as f:
                    data = json.load(f)
                    self.stats_text.insert(tk.END, "Statistics:\n\n")
                    self.stats_text.insert(tk.END, f"Total Observations: {len(data.get('observations', []))}\n")
                    # Add more statistics as needed
                    
            # Clear existing graphs
            for widget in self.graph_frame.winfo_children():
                widget.destroy()
                
            # Create and display new graphs
            self.create_graphs()
            
        except Exception as e:
            self.stats_text.insert(tk.END, f"Error loading statistics: {str(e)}")
            
    def create_graphs(self):
        # Create a sample figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8))
        
        # Add sample data visualization
        # This should be replaced with actual data visualization from the parsed files
        ax1.plot([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        ax1.set_title("Sample Graph 1")
        
        ax2.plot([1, 2, 3, 4, 5], [1, 3, 5, 7, 9])
        ax2.set_title("Sample Graph 2")
        
        # Embed the figure in the Tkinter window
        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def open_statistics(self):
        """Open the statistics window"""
        if not self.export_dir.get():
            self.show_message("Error", "Please select an Apple Health export directory first", "error")
            return
            
        try:
            StatisticsWindow(self.root, self.export_dir.get())
        except Exception as e:
            self.show_message("Error", f"Failed to open statistics window: {str(e)}", "error")

    def manage_symptoms(self):
        """Open the symptom management window"""
        if not self.symptom_data.get():
            # Use default file path in data/my_data directory
            default_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "my_data")
            os.makedirs(default_dir, exist_ok=True)
            default_file = os.path.join(default_dir, "symptom_set.csv")
            self.symptom_data.set(default_file)
            
            # Create the file with header if it doesn't exist
            if not os.path.exists(default_file):
                try:
                    with open(default_file, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Name', 'Start Date', 'End Date', 'Medications', 'Stimulants', 'Comment', 'Severity'])
                except Exception as e:
                    self.show_message("Error", f"Failed to create symptom file: {str(e)}", "error")
                    return
            
        try:
            SymptomWindow(self.root, self.symptom_data.get())
        except Exception as e:
            self.show_message("Error", f"Failed to open symptom management window: {str(e)}", "error")

if __name__ == "__main__":
    root = tk.Tk()
    app = HealthDataParserUI(root)
    root.mainloop()
