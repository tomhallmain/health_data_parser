import csv
import dataclasses
import os

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from health_data_parser.analysis.summary import (
    OBSERVATIONS_JSON_FILENAME, load_observations_json, summary_lines,
    observation_counts_by_year, abnormal_counts_by_interpretation)
from health_data_parser.options import (
    ParseOptions, parse_boundary, parse_skip_dates, parse_start_year)
from health_data_parser.pipeline import DataParser
from health_data_parser.tkui.statistics_window import StatisticsWindow
from health_data_parser.tkui.symptom_window import SymptomWindow
from health_data_parser.utils.paths import default_user_data_dir

_DEFAULTS = {f.name: f.default for f in dataclasses.fields(ParseOptions)
             if f.default is not dataclasses.MISSING}

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
        # Blank start year means no start year
        self.start_year = tk.StringVar(value=_DEFAULTS["start_year"] or "")
        self.skip_dates = tk.StringVar(value=",".join(_DEFAULTS["skip_dates"]))
        self.skip_long_values = tk.BooleanVar(value=_DEFAULTS["skip_long_values"])
        self.json_add_all_vitals = tk.BooleanVar(value=_DEFAULTS["json_add_all_vitals"])
        self.filter_abnormal_in_range = tk.BooleanVar(value=_DEFAULTS["skip_in_range_abnormal_results"])
        self.in_range_abnormal_boundary = tk.StringVar(value=str(_DEFAULTS["in_range_abnormal_boundary"]))
        self.report_highlight_abnormal_results = tk.BooleanVar(
            value=_DEFAULTS["report_highlight_abnormal_results"])
        
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
            start_year = self.start_year.get().strip()
            options = ParseOptions(
                data_export_dir=self.export_dir.get(),
                start_year=parse_start_year(start_year) if start_year else None,
                skip_dates=parse_skip_dates(self.skip_dates.get()),
                skip_long_values=self.skip_long_values.get(),
                json_add_all_vitals=self.json_add_all_vitals.get(),
                skip_in_range_abnormal_results=self.filter_abnormal_in_range.get(),
                in_range_abnormal_boundary=parse_boundary(self.in_range_abnormal_boundary.get()),
                report_highlight_abnormal_results=self.report_highlight_abnormal_results.get(),
                symptom_data_csv=self.symptom_data.get() or None,
                food_data_csv=self.food_data.get() or None,
                extra_observations_csv=self.extra_observations.get() or None,
            )

            # Run parser
            parser = DataParser(options)
            parser.run()

            # Update statistics and graphs
            self.update_statistics(options.output_paths.directory)
            
            self.show_message("Success", "Report generated successfully!")
            
        except Exception as e:
            self.show_message("Error", f"Failed to generate report: {str(e)}", "error")
            
    def update_statistics(self, data_dir):
        # Clear existing content
        self.stats_text.delete(1.0, tk.END)
        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        # Read and display statistics from the generated files
        try:
            json_data = load_observations_json(data_dir)
            if not json_data:
                self.stats_text.insert(tk.END, f"No {OBSERVATIONS_JSON_FILENAME} found in {data_dir}\n")
                return

            self.stats_text.insert(tk.END, "Statistics:\n\n")
            self.stats_text.insert(tk.END, "\n".join(summary_lines(json_data)) + "\n")

            self.create_graphs(json_data)

        except Exception as e:
            self.stats_text.insert(tk.END, f"Error loading statistics: {str(e)}")

    def create_graphs(self, json_data):
        counts_by_year = observation_counts_by_year(json_data)
        abnormal_by_interpretation = abnormal_counts_by_interpretation(json_data)

        # A standalone Figure is not registered with pyplot, so figures from
        # previous report runs are freed when their canvas widget is destroyed.
        fig = Figure(figsize=(8, 8))
        ax1, ax2 = fig.subplots(2, 1)

        ax1.bar([year for year, _ in counts_by_year], [count for _, count in counts_by_year])
        ax1.set_title("Observations by Year")
        ax1.set_ylabel("Observations")
        if not counts_by_year:
            ax1.text(0.5, 0.5, "No observations", ha="center", va="center", transform=ax1.transAxes)

        ax2.bar([text for text, _ in abnormal_by_interpretation],
                [count for _, count in abnormal_by_interpretation], color="tab:red")
        ax2.set_title("Abnormal Results by Interpretation")
        ax2.set_ylabel("Results")
        ax2.tick_params(axis="x", labelrotation=20)
        if not abnormal_by_interpretation:
            ax2.text(0.5, 0.5, "No abnormal results", ha="center", va="center", transform=ax2.transAxes)

        fig.tight_layout()

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
            default_dir = str(default_user_data_dir())
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

def main():
    root = tk.Tk()
    app = HealthDataParserUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
