import json
import os

def load_match_data(json_filepath):
    """Loads match data from a JSON file with improved error reporting."""
    if not isinstance(json_filepath, str) or not json_filepath:
         print("Error: Invalid file path provided.")
         return None
    if not os.path.exists(json_filepath):
        print(f"Error: File not found at '{json_filepath}'")
        return None
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded data from {os.path.basename(json_filepath)}")
        return data
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode JSON from {os.path.basename(json_filepath)} - {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred loading {os.path.basename(json_filepath)}: {e}")
        return None

def get_match_summary(data):
    """Extracts basic match information."""
    if not data or 'info' not in data:
        return "Match info not available."
    try:
        info = data['info']
        teams = info.get('teams', ['Team A', 'Team B'])
        venue = info.get('venue', 'Unknown Venue')
        date = info.get('dates', ['Unknown Date'])[0]
        event_name = info.get('event', {}).get('name', 'the match')
        match_num = info.get('event', {}).get('match_number')
        event_str = f"{event_name}" + (f", Match {match_num}" if match_num else "")

        toss_winner = info.get('toss', {}).get('winner', 'N/A')
        toss_decision = info.get('toss', {}).get('decision', 'N/A')
        toss_str = f"Toss: {toss_winner} won the toss and chose to {toss_decision}." if toss_winner != 'N/A' else "Toss info unavailable."

        outcome = info.get('outcome', {})
        winner = outcome.get('winner', 'N/A')
        result_details = outcome.get('by', {})
        margin = ""
        result_type = outcome.get('result', 'normal') # Check for tie, no result etc.

        if winner != 'N/A':
            if 'runs' in result_details:
                margin = f" by {result_details['runs']} runs"
            elif 'wickets' in result_details:
                margin = f" by {result_details['wickets']} wickets"
            result_str = f"Result: {winner} won{margin}."
        elif result_type == 'tie':
             result_str = "Result: The match was a Tie."
        elif result_type == 'no result':
             result_str = "Result: No Result."
        else:
             result_str = "Result: Information unavailable."


        # Construct a more detailed summary for context
        summary = (
            f"Details for {event_str}: {teams[0]} vs {teams[1]} "
            f"at {venue} on {date}. {toss_str} {result_str}"
        )
        return summary
    except Exception as e:
        print(f"Error processing match summary: {e}")
        return "Error summarizing match info."

def get_runs_per_over(data):
    """Calculates runs scored in each over for each inning."""
    runs_data = {}
    if not data or 'innings' not in data:
        print("Warning: Innings data not found for calculating runs per over.")
        return runs_data

    try:
        for i, inning in enumerate(data['innings']):
            team = inning.get('team', f'Inning {i+1}')
            over_runs = {}
            sorted_overs = sorted(inning.get('overs', []), key=lambda x: x.get('over', -1))
            for over_data in sorted_overs:
                over_num = over_data.get('over')
                if over_num is None: continue
                total_over_runs = sum(d.get('runs', {}).get('total', 0) for d in over_data.get('deliveries', []))
                over_runs[over_num] = total_over_runs
            runs_data[team] = over_runs
    except Exception as e:
        print(f"Error calculating runs per over: {e}")

    return runs_data

def format_inning_for_llm(inning_data, inning_number, max_balls=150):
    """Formats ball-by-ball data of an inning into a compact string for LLM prompts."""
    team = inning_data.get('team', f'Inning {inning_number}')
    overs_data = inning_data.get('overs', [])
    ball_by_ball_summary = [f"--- Inning {inning_number}: {team} Batting ---"]
    ball_count = 0

    if not overs_data:
        ball_by_ball_summary.append("(No over data available for this inning)")
        return "\n".join(ball_by_ball_summary)

    sorted_overs = sorted(overs_data, key=lambda x: x.get('over', -1))

    for over in sorted_overs:
        if ball_count >= max_balls: break
        over_num = over.get('over')
        if over_num is None: continue # Skip if over number missing

        for i, delivery in enumerate(over.get('deliveries', [])):
            if ball_count >= max_balls: break
            # Ensure ball number calculation is robust
            # Standard cricket notation is 1-6 balls per over, not 0-indexed
            ball_in_over = i + 1
            # Adjust if extras mean more than 6 balls (simple approach: just keep counting)
            ball_num = f"{over_num}.{ball_in_over}"

            batter = delivery.get('batter', 'Unknown Batter')
            bowler = delivery.get('bowler', 'Unknown Bowler')
            runs_info = delivery.get('runs', {})
            batter_runs = runs_info.get('batter', 0)
            total_runs = runs_info.get('total', 0)

            # Build line part by part
            line_parts = [f"B {ball_num}: {bowler} to {batter}, {batter_runs} run{'s' if batter_runs != 1 else ''} ({total_runs} total)"]

            if 'wickets' in delivery:
                wicket = delivery['wickets'][0]
                fielder_text = ""
                kind = wicket.get('kind', 'out')
                player_out = wicket.get('player_out', 'Batter')
                if 'fielders' in wicket and wicket['fielders']:
                     fielder_names = [f['name'] for f in wicket['fielders'] if 'name' in f]
                     if fielder_names:
                         if 'caught' in kind: fielder_text = f" caught by {', '.join(fielder_names)}"
                         elif 'run out' in kind: fielder_text = f" run out ({', '.join(fielder_names)})"
                         elif 'stumped' in kind: fielder_text = f" stumped by {', '.join(fielder_names)}"
                         # Add other fielding types if necessary
                line_parts.append(f" WICKET! ({player_out} {kind}{fielder_text})")

            if 'extras' in delivery:
                # Handle multiple types of extras if needed, though usually one type per ball
                extras_type = list(delivery['extras'].keys())[0]
                extras_runs = delivery['extras'][extras_type]
                line_parts.append(f" Extras: {extras_runs} {extras_type}")

            ball_by_ball_summary.append("".join(line_parts))
            ball_count += 1
            # Don't count extra balls (wides/noballs) towards the ball_in_over for the *next* delivery?
            # Standard JSON often lists them sequentially. Keep simple counting for now.

    if ball_count >= max_balls and len(overs_data) > 0 and over_num < max(o.get('over',-1) for o in overs_data):
        ball_by_ball_summary.append(f"\n...(further deliveries omitted from over {over_num+1} onwards due to length limit)")

    return "\n".join(ball_by_ball_summary)