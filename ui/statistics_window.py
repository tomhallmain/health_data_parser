from datetime import datetime
import json
import os

import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd

class StatisticsWindow:
    def __init__(self, parent, data_dir):
        self.window = tk.Toplevel(parent)
        self.window.title("Health Data Statistics")
        self.window.geometry("1000x800")
        
        self.data_dir = data_dir
        
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
        
        # Initialize data
        self.load_data()
        
        # Setup each tab
        self.setup_overview_tab()
        self.setup_vitals_tab()
        self.setup_lab_results_tab()
        self.setup_trends_tab()
        
    def load_data(self):
        """Load data from JSON and CSV files"""
        try:
            # Load JSON data
            json_path = os.path.join(self.data_dir, "observations.json")
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    self.json_data = json.load(f)
            else:
                self.json_data = {}
                
            # Load CSV data
            csv_path = os.path.join(self.data_dir, "observations.csv")
            if os.path.exists(csv_path):
                self.df = pd.read_csv(csv_path)
            else:
                self.df = pd.DataFrame()
                
            # Load abnormal results
            abnormal_path = os.path.join(self.data_dir, "abnormal_results.csv")
            if os.path.exists(abnormal_path):
                self.abnormal_df = pd.read_csv(abnormal_path)
            else:
                self.abnormal_df = pd.DataFrame()
                
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            self.json_data = {}
            self.df = pd.DataFrame()
            self.abnormal_df = pd.DataFrame()
            
    def setup_overview_tab(self):
        """Setup the overview tab with summary statistics"""
        # Create frames for different sections
        summary_frame = ttk.LabelFrame(self.overview_tab, text="Summary Statistics", padding="5")
        summary_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Add summary statistics
        if not self.df.empty:
            total_obs = len(self.df)
            unique_dates = self.df['date'].nunique()
            unique_codes = self.df['code'].nunique()
            
            stats_text = f"""
            Total Observations: {total_obs}
            Unique Dates: {unique_dates}
            Unique Test Codes: {unique_codes}
            Date Range: {self.df['date'].min()} to {self.df['date'].max()}
            """
            
            stats_label = ttk.Label(summary_frame, text=stats_text, justify=tk.LEFT)
            stats_label.pack(padx=5, pady=5)
            
        # Add abnormal results summary
        if not self.abnormal_df.empty:
            abnormal_frame = ttk.LabelFrame(self.overview_tab, text="Abnormal Results Summary", padding="5")
            abnormal_frame.pack(fill=tk.X, padx=5, pady=5)
            
            abnormal_count = len(self.abnormal_df)
            abnormal_text = f"Total Abnormal Results: {abnormal_count}"
            
            abnormal_label = ttk.Label(abnormal_frame, text=abnormal_text, justify=tk.LEFT)
            abnormal_label.pack(padx=5, pady=5)
            
    def setup_vitals_tab(self):
        """Setup the vitals tab with vital signs visualization"""
        # Create figure for vitals
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("Vital Signs Over Time")
        
        if not self.df.empty:
            # Filter for vital signs
            vitals_df = self.df[self.df['code'].str.contains('vital', case=False, na=False)]
            
            # Plot heart rate
            if 'heart_rate' in vitals_df['code'].values:
                hr_data = vitals_df[vitals_df['code'] == 'heart_rate']
                axes[0, 0].plot(pd.to_datetime(hr_data['date']), hr_data['value'], 'b-')
                axes[0, 0].set_title("Heart Rate")
                axes[0, 0].set_xlabel("Date")
                axes[0, 0].set_ylabel("BPM")
                
            # Plot blood pressure
            if 'blood_pressure' in vitals_df['code'].values:
                bp_data = vitals_df[vitals_df['code'] == 'blood_pressure']
                axes[0, 1].plot(pd.to_datetime(bp_data['date']), bp_data['value'], 'r-')
                axes[0, 1].set_title("Blood Pressure")
                axes[0, 1].set_xlabel("Date")
                axes[0, 1].set_ylabel("mmHg")
                
            # Plot temperature
            if 'temperature' in vitals_df['code'].values:
                temp_data = vitals_df[vitals_df['code'] == 'temperature']
                axes[1, 0].plot(pd.to_datetime(temp_data['date']), temp_data['value'], 'g-')
                axes[1, 0].set_title("Temperature")
                axes[1, 0].set_xlabel("Date")
                axes[1, 0].set_ylabel("°C")
                
            # Plot respiratory rate
            if 'respiratory_rate' in vitals_df['code'].values:
                rr_data = vitals_df[vitals_df['code'] == 'respiratory_rate']
                axes[1, 1].plot(pd.to_datetime(rr_data['date']), rr_data['value'], 'm-')
                axes[1, 1].set_title("Respiratory Rate")
                axes[1, 1].set_xlabel("Date")
                axes[1, 1].set_ylabel("breaths/min")
                
        plt.tight_layout()
        
        # Embed the figure in the Tkinter window
        canvas = FigureCanvasTkAgg(fig, master=self.vitals_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def setup_lab_results_tab(self):
        """Setup the lab results tab with detailed lab test visualization"""
        # Create frame for lab results
        lab_frame = ttk.Frame(self.lab_results_tab)
        lab_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create treeview for lab results
        columns = ('Date', 'Code', 'Description', 'Value', 'Range', 'Status')
        self.lab_tree = ttk.Treeview(lab_frame, columns=columns, show='headings')
        
        # Set column headings
        for col in columns:
            self.lab_tree.heading(col, text=col)
            self.lab_tree.column(col, width=100)
            
        # Add scrollbar
        scrollbar = ttk.Scrollbar(lab_frame, orient=tk.VERTICAL, command=self.lab_tree.yview)
        self.lab_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack treeview and scrollbar
        self.lab_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate lab results
        if not self.df.empty:
            lab_df = self.df[self.df['code'].str.contains('lab', case=False, na=False)]
            for _, row in lab_df.iterrows():
                status = "Normal"
                if not self.abnormal_df.empty:
                    if row['code'] in self.abnormal_df['code'].values:
                        status = "Abnormal"
                        
                self.lab_tree.insert('', tk.END, values=(
                    row['date'],
                    row['code'],
                    row.get('description', ''),
                    row['value'],
                    row.get('range', ''),
                    status
                ))
                
    def setup_trends_tab(self):
        """Setup the trends tab with time-based analysis"""
        # Create figure for trends
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))
        fig.suptitle("Health Data Trends")
        
        if not self.df.empty:
            # Convert date column to datetime
            self.df['date'] = pd.to_datetime(self.df['date'])
            
            # Plot 1: Number of observations over time
            daily_obs = self.df.groupby('date').size()
            axes[0].plot(daily_obs.index, daily_obs.values, 'b-')
            axes[0].set_title("Number of Observations Over Time")
            axes[0].set_xlabel("Date")
            axes[0].set_ylabel("Number of Observations")
            
            # Plot 2: Abnormal results over time
            if not self.abnormal_df.empty:
                self.abnormal_df['date'] = pd.to_datetime(self.abnormal_df['date'])
                daily_abnormal = self.abnormal_df.groupby('date').size()
                axes[1].plot(daily_abnormal.index, daily_abnormal.values, 'r-')
                axes[1].set_title("Number of Abnormal Results Over Time")
                axes[1].set_xlabel("Date")
                axes[1].set_ylabel("Number of Abnormal Results")
                
        plt.tight_layout()
        
        # Embed the figure in the Tkinter window
        canvas = FigureCanvasTkAgg(fig, master=self.trends_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True) 