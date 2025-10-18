import matplotlib
matplotlib.use('Agg') # Use non-interactive backend suitable for scripts
import matplotlib.pyplot as plt
import os
import numpy as np
from src.utils import ensure_dir
# Import the function from data_processor
from src.data_processor import get_runs_per_over

# Default styles
plt.style.use('seaborn-v0_8-darkgrid')
CHART_DPI = 150
FIG_SIZE = (12, 7)
TITLE_FONTSIZE = 16
LABEL_FONTSIZE = 12
TICK_FONTSIZE = 10
LEGEND_FONTSIZE = 10

def plot_run_rate(data, output_dir):
    """Generates and saves a run rate comparison chart."""
    ensure_dir(output_dir)

    if not data or 'innings' not in data or len(data['innings']) < 1:
        print("Insufficient innings data to plot run rate.")
        return None

    plt.figure(figsize=FIG_SIZE)
    max_overs = data['info'].get('overs', 20)

    # --- Plotting ---
    try:
        plot_successful = False
        for i, inning in enumerate(data['innings']):
            team = inning.get('team', f'Inning {i+1}')
            runs_per_over_cumulative = []
            cumulative_runs = 0
            over_numbers_completed = [] # Track actual overs bowled (0 to max_overs-1)
            over_data_map = {over['over']: over for over in inning.get('overs', []) if 'over' in over}
            last_over_bowled = -1

            for over_num in range(max_overs):
                if over_num in over_data_map:
                    over_data = over_data_map[over_num]
                    # Ensure deliveries exist before summing
                    over_runs = sum(d.get('runs', {}).get('total', 0) for d in over_data.get('deliveries', []))
                    cumulative_runs += over_runs
                    runs_per_over_cumulative.append(cumulative_runs)
                    over_numbers_completed.append(over_num)
                    last_over_bowled = over_num
                else:
                    # Handle end of innings correctly
                    if last_over_bowled != -1: # If some overs were bowled
                        break # Stop if data for the next over is missing

            run_rates = [runs / (ov + 1) for ov, runs in zip(over_numbers_completed, runs_per_over_cumulative)]
            overs_axis = [ov + 1 for ov in over_numbers_completed]

            if overs_axis:
                plt.plot(overs_axis, run_rates, marker='o', linestyle='-', linewidth=2, markersize=5, label=f"{team} Run Rate")
                plot_successful = True # Mark that at least one line was plotted

        if not plot_successful:
            print("Warning: No valid run rate data found to plot.")
            return None # Don't save an empty chart

        # --- Formatting ---
        plt.title("Run Rate Progression", fontsize=TITLE_FONTSIZE, pad=15)
        plt.xlabel("Over Number", fontsize=LABEL_FONTSIZE)
        plt.ylabel("Run Rate (Runs per Over)", fontsize=LABEL_FONTSIZE)
        plt.legend(fontsize=LEGEND_FONTSIZE)
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.xticks(np.arange(0, max_overs + 1, step=max(1, max_overs // 10)), fontsize=TICK_FONTSIZE)
        plt.yticks(fontsize=TICK_FONTSIZE)
        plt.xlim(0, max_overs + 1)
        plt.ylim(bottom=0)
        plt.tight_layout()

        # --- Saving ---
        chart_path = os.path.join(output_dir, "run_rate_comparison.png")
        plt.savefig(chart_path, dpi=CHART_DPI)
        print(f"Saved run rate chart: {os.path.basename(chart_path)}")
        return chart_path

    except Exception as e:
        print(f"Error generating or saving run rate chart: {e}")
        return None
    finally:
        plt.close() # Ensure plot is closed


def plot_manhattan(data, output_dir):
    """Generates and saves a Manhattan chart (runs per over)."""
    ensure_dir(output_dir)

    runs_data = get_runs_per_over(data) # Use imported function
    if not runs_data:
        print("Could not get runs per over data for Manhattan chart.")
        return None

    teams = list(runs_data.keys())
    if not teams:
        print("No teams found in runs per over data.")
        return None

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    max_overs = data['info'].get('overs', 20)
    bar_width = 0.35 if len(teams) > 1 else 0.7
    index = np.arange(max_overs) + 1 # Overs 1 to max_overs

    # --- Plotting ---
    try:
        # Use a qualitative colormap if more teams, otherwise specific colors
        if len(teams) > 2:
            colors = plt.cm.get_cmap('tab10', len(teams))
            color_map = {team: colors(i) for i, team in enumerate(teams)}
        else:
            color_map = {teams[0]: 'royalblue', teams[1]: 'darkorange'} if len(teams) == 2 else {teams[0]: 'royalblue'}


        for i, team in enumerate(teams):
            over_runs = runs_data[team]
            runs = [over_runs.get(ov, 0) for ov in range(max_overs)]
            if len(teams) > 1:
                 bar_position = index + (i - (len(teams) - 1) / 2) * bar_width
            else:
                 bar_position = index

            ax.bar(bar_position, runs[:max_overs], bar_width, label=f"{team} Runs", color=color_map.get(team))

        # --- Formatting ---
        ax.set_xlabel('Over Number', fontsize=LABEL_FONTSIZE)
        ax.set_ylabel('Runs Scored', fontsize=LABEL_FONTSIZE)
        ax.set_title('Runs Scored Per Over (Manhattan Chart)', fontsize=TITLE_FONTSIZE, pad=15)
        ax.set_xticks(index)
        # Ensure only integer ticks if max_overs is small
        if max_overs <= 20 :
             ax.set_xticklabels(index.astype(int), fontsize=TICK_FONTSIZE)
        else: # Reduce number of labels if many overs
             tick_step = max(1, max_overs // 10)
             ax.set_xticks(np.arange(1, max_overs + 1, step=tick_step))
             ax.set_xticklabels(np.arange(1, max_overs + 1, step=tick_step).astype(int), fontsize=TICK_FONTSIZE)

        ax.tick_params(axis='y', labelsize=TICK_FONTSIZE)
        ax.legend(fontsize=LEGEND_FONTSIZE)
        ax.grid(True, axis='y', linestyle='--', linewidth=0.5)
        ax.set_ylim(bottom=0) # Ensure y-axis starts at 0
        plt.tight_layout()

        # --- Saving ---
        chart_path = os.path.join(output_dir, "manhattan_chart.png")
        plt.savefig(chart_path, dpi=CHART_DPI)
        print(f"Saved Manhattan chart: {os.path.basename(chart_path)}")
        return chart_path

    except Exception as e:
        print(f"Error generating or saving Manhattan chart: {e}")
        return None
    finally:
        plt.close()