import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from health_data_parser.analysis.summary import (
    OBSERVATIONS_JSON_FILENAME, load_observations_json, summary_lines,
    lab_result_rows, vital_sign_rows, observation_counts_by_date)
from health_data_parser.utils.logger import setup_logger

logger = setup_logger('statistics_window')

class StatisticsWindow:
    def __init__(self, parent, data_dir):
        self.data_dir = data_dir
        # Load before creating the window so a corrupt file raises without
        # leaving an empty window behind
        self.json_data = load_observations_json(data_dir)

        self.window = tk.Toplevel(parent)
        self.window.title("Health Data Statistics")
        self.window.geometry("1000x800")

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create tabs
        self.overview_tab = ttk.Frame(self.notebook)
        self.vitals_tab = ttk.Frame(self.notebook)
        self.lab_results_tab = ttk.Frame(self.notebook)
        self.trends_tab = ttk.Frame(self.notebook)

        # Add tabs to notebook
        self.notebook.add(self.overview_tab, text="Overview")
        self.notebook.add(self.vitals_tab, text="Vitals")
        self.notebook.add(self.lab_results_tab, text="Lab Results")
        self.notebook.add(self.trends_tab, text="Trends")

        # Setup each tab
        self.setup_overview_tab()
        self.setup_vitals_tab()
        self.setup_lab_results_tab()
        self.setup_trends_tab()

    def setup_overview_tab(self):
        """Setup the overview tab with summary statistics"""
        summary_frame = ttk.LabelFrame(self.overview_tab, text="Summary Statistics", padding="5")
        summary_frame.pack(fill=tk.X, padx=5, pady=5)

        if self.json_data:
            text = "\n".join(summary_lines(self.json_data))
        else:
            text = f"No {OBSERVATIONS_JSON_FILENAME} found in {self.data_dir}. Generate a report first."

        stats_label = ttk.Label(summary_frame, text=text, justify=tk.LEFT)
        stats_label.pack(anchor=tk.W, padx=5, pady=5)

    def _create_table(self, parent, columns, rows, abnormal_column=None):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        tree.tag_configure("abnormal", foreground="red")

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for row in rows:
            is_abnormal = (abnormal_column is not None
                           and row[abnormal_column] not in ("", "Normal"))
            tree.insert('', tk.END, values=row, tags=("abnormal",) if is_abnormal else ())
        return tree

    def setup_vitals_tab(self):
        """Setup the vitals tab with a summary row per vital sign"""
        columns = ('Vital', 'Unit', 'Most Recent', 'Date', 'Min', 'Max', 'Average', 'Count')
        self.vitals_tree = self._create_table(
            self.vitals_tab, columns, vital_sign_rows(self.json_data))

    def setup_lab_results_tab(self):
        """Setup the lab results tab with every observation, abnormal ones highlighted"""
        columns = ('Date', 'Test', 'Value', 'Range', 'Status')
        self.lab_tree = self._create_table(
            self.lab_results_tab, columns, lab_result_rows(self.json_data), abnormal_column=4)

    def setup_trends_tab(self):
        """Setup the trends tab with observation counts over time"""
        fig = Figure(figsize=(12, 8))
        fig.suptitle("Health Data Trends")
        axes = fig.subplots(2, 1, sharex=True)

        plots = [
            (axes[0], observation_counts_by_date(self.json_data), "tab:blue",
             "Observations per Date", "Observations"),
            (axes[1], observation_counts_by_date(self.json_data, abnormal_only=True), "tab:red",
             "Abnormal Results per Date", "Abnormal Results"),
        ]
        for ax, counts, color, title, ylabel in plots:
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            if counts:
                dates = [date for date, _ in counts]
                values = [count for _, count in counts]
                ax.vlines(dates, 0, values, color=color)
                ax.plot(dates, values, "o", color=color)
                ax.set_ylim(bottom=0)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

        fig.autofmt_xdate()
        fig.tight_layout()

        # Embed the figure in the Tkinter window
        canvas = FigureCanvasTkAgg(fig, master=self.trends_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
