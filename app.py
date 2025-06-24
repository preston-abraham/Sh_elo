import streamlit as st
import math
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
from datetime import datetime

# Google Sheets setup
@st.cache_resource
def init_connection():
    """Initialize connection to Google Sheets"""
    try:
        # Get credentials from Streamlit secrets
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets: {str(e)}")
        st.error("Please check your Google Sheets configuration in Streamlit secrets.")
        return None

def get_worksheet(worksheet_name="Players"):
    """Get or create a specific worksheet"""
    try:
        client = init_connection()
        if not client:
            return None, None
            
        sheet_name = st.secrets.get("sheet_name", "Secret_Hitler_ELO")
        
        try:
            # Try to open existing sheet
            sheet = client.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            # Create new sheet if it doesn't exist
            sheet = client.create(sheet_name)
            # Make it shareable (optional)
            sheet.share('', perm_type='anyone', role='reader')
            st.success(f"Created new Google Sheet: {sheet_name}")
        
        # Get or create the specific worksheet
        try:
            worksheet = sheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            if worksheet_name == "Players":
                worksheet = sheet.add_worksheet(title="Players", rows="100", cols="20")
                # Add headers
                worksheet.update('A1:C1', [['Player', 'ELO', 'Last_Updated']])
            elif worksheet_name == "Match_History":
                worksheet = sheet.add_worksheet(title="Match_History", rows="1000", cols="20")
                # Add headers
                headers = ['Date', 'Liberal_Team', 'Fascist_Team', 'Hitler', 'Winning_Team', 
                          'Game_End_Condition', 'Shooter', 'Shot_Player', 'Liberal_ELO_Changes', 
                          'Fascist_ELO_Changes', 'Match_Notes']
                worksheet.update('A1:K1', [headers])
            
        return worksheet, sheet
    except Exception as e:
        st.error(f"Error accessing worksheet: {str(e)}")
        return None, None

def load_player_elos():
    """Load player ELO ratings from Google Sheets"""
    try:
        worksheet, _ = get_worksheet("Players")
        if not worksheet:
            return {}
            
        # Get all data
        data = worksheet.get_all_records()
        
        # Convert to dictionary
        player_elos = {}
        for row in data:
            if row.get('Player') and row.get('ELO'):  # Skip empty rows
                try:
                    player_elos[row['Player']] = float(row['ELO'])
                except (ValueError, TypeError):
                    st.warning(f"Invalid ELO value for player {row['Player']}: {row['ELO']}")
                    continue
                
        return player_elos
    except Exception as e:
        st.error(f"Error loading player data: {str(e)}")
        return {}

def save_player_elos(player_elos):
    """Save player ELO ratings to Google Sheets"""
    try:
        worksheet, _ = get_worksheet("Players")
        if not worksheet:
            return False
        
        # Get current data to preserve structure
        current_data = worksheet.get_all_values()
        
        # Clear all data except headers
        if len(current_data) > 1:
            worksheet.batch_clear([f"A2:C{len(current_data)}"])
        
        # Prepare data for upload
        data_to_upload = []
        for player, elo in player_elos.items():
            data_to_upload.append([
                str(player), 
                float(elo), 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        
        if data_to_upload:
            # Update sheet with new data
            range_name = f'A2:C{len(data_to_upload) + 1}'
            worksheet.update(range_name, data_to_upload, value_input_option='USER_ENTERED')
            
        return True
    except Exception as e:
        st.error(f"Error saving player data: {str(e)}")
        st.error(f"Error details: {type(e).__name__}")
        return False

def save_match_history(match_data):
    """Save match history to Google Sheets"""
    try:
        worksheet, _ = get_worksheet("Match_History")
        if not worksheet:
            return False
        
        # Get existing data to append to
        existing_data = worksheet.get_all_values()
        next_row = len(existing_data) + 1
        
        # Prepare match data for upload - convert all to strings
        row_data = [
            str(match_data['date']),
            ', '.join(match_data['liberal_team']),
            ', '.join(match_data['fascist_team']),
            str(match_data['hitler']),
            str(match_data['winning_team']),
            str(match_data['game_end_condition']),
            str(match_data.get('shooter', '')),
            str(match_data.get('shot_player', '')),
            str(match_data['liberal_elo_changes']),
            str(match_data['fascist_elo_changes']),
            str(match_data.get('notes', ''))
        ]
        
        # Insert the new match data
        worksheet.update(f'A{next_row}:K{next_row}', [row_data], value_input_option='USER_ENTERED')
        return True
        
    except Exception as e:
        st.error(f"Error saving match history: {str(e)}")
        st.error(f"Error details: {type(e).__name__}")
        return False

def load_match_history():
    """Load match history from Google Sheets"""
    try:
        worksheet, _ = get_worksheet("Match_History")
        if not worksheet:
            return []
            
        # Get all data
        data = worksheet.get_all_records()
        return data
        
    except Exception as e:
        st.error(f"Error loading match history: {str(e)}")
        return []

def get_sheet_url():
    """Get the URL of the Google Sheet"""
    try:
        _, sheet = get_worksheet("Players")
        if sheet:
            return sheet.url
        return None
    except Exception as e:
        st.error(f"Error getting sheet URL: {str(e)}")
        return None

# Initialize session state
if 'player_elos' not in st.session_state:
    st.session_state.player_elos = {}

if 'sheets_loaded' not in st.session_state:
    st.session_state.sheets_loaded = False

def calculate_expected_score(rating_a, rating_b):
    """Calculate expected score for player A against player B"""
    return 1 / (1 + 10**((rating_b - rating_a) / 400))

def calculate_team_elo_update(team_players, opposing_players, won, k_factor=32):
    """Calculate ELO updates for a team based on the outcome"""
    team_ratings = [st.session_state.player_elos.get(player, 1200) for player in team_players]
    opponent_ratings = [st.session_state.player_elos.get(player, 1200) for player in opposing_players]
    
    # Calculate average team ratings
    team_avg = sum(team_ratings) / len(team_ratings)
    opponent_avg = sum(opponent_ratings) / len(opponent_ratings)
    
    # Calculate expected score for the team
    expected_score = calculate_expected_score(team_avg, opponent_avg)
    
    # Actual score (1 for win, 0 for loss)
    actual_score = 1 if won else 0
    
    # Calculate rating change
    rating_change = k_factor * (actual_score - expected_score)
    
    # Apply the same rating change to all team members
    updates = {}
    for player in team_players:
        old_rating = st.session_state.player_elos.get(player, 1200)
        new_rating = old_rating + rating_change
        updates[player] = {
            'old_rating': old_rating,
            'new_rating': new_rating,
            'change': rating_change
        }
    
    return updates

def check_password():
    """Check if the password is correct"""
    if 'password_correct' not in st.session_state:
        st.session_state.password_correct = False
    
    def password_entered():
        """Check the password"""
        if st.session_state["password"] == st.secrets.get("admin_password", "admin123"):
            st.session_state.password_correct = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state.password_correct = False
    
    if not st.session_state.password_correct:
        st.text_input(
            "🔒 Enter admin password to manage games and update ELO scores:", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        if "password" in st.session_state:
            st.error("😞 Password incorrect")
        return False
    else:
        return True

def main():
    st.title("🕵️ Secret Hitler ELO Calculator")
    st.write("Track ELO ratings and match history for your Secret Hitler games!")
    
    # Show Google Sheet link prominently
    sheet_url = get_sheet_url()
    if sheet_url:
        st.info(f"📊 **View Google Sheet:** [Open Sheet]({sheet_url})")
    
    # Auto-load data for public viewing
    if not st.session_state.sheets_loaded and st.session_state.player_elos == {}:
        with st.spinner("Loading current ELO standings..."):
            loaded_elos = load_player_elos()
            if loaded_elos:
                st.session_state.player_elos = loaded_elos
                st.session_state.sheets_loaded = True

    # Public ELO Leaderboard (Always visible)
    st.header("🏆 Current ELO Standings")
    
    if st.session_state.player_elos:
        # Sort players by ELO (highest first)
        sorted_players = sorted(st.session_state.player_elos.items(), key=lambda x: x[1], reverse=True)
        
        # Display as a nice table
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.write("**Rank**")
        with col2:
            st.write("**Player**")
        with col3:
            st.write("**ELO**")
        
        st.write("---")
        
        for i, (player, elo) in enumerate(sorted_players, 1):
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if i == 1:
                    st.write(f"🥇 {i}")
                elif i == 2:
                    st.write(f"🥈 {i}")
                elif i == 3:
                    st.write(f"🥉 {i}")
                else:
                    st.write(f"#{i}")
            with col2:
                st.write(f"**{player}**")
            with col3:
                st.write(f"{elo:.0f}")
        
        # Refresh button for public users
        if st.button("🔄 Refresh ELO Standings"):
            with st.spinner("Refreshing standings..."):
                loaded_elos = load_player_elos()
                if loaded_elos:
                    st.session_state.player_elos = loaded_elos
                    st.session_state.sheets_loaded = True
                    st.success("ELO standings refreshed!")
                    st.rerun()
    else:
        st.info("No player data available. ELO standings will appear here once games are played.")
    
    # Public Match History
    st.header("📋 Recent Match History")
    with st.spinner("Loading match history..."):
        match_history = load_match_history()
        
    if match_history:
        # Show last 5 matches
        recent_matches = match_history[-5:] if len(match_history) > 5 else match_history
        recent_matches.reverse()  # Most recent first
        
        for match in recent_matches:
            with st.expander(f"🎮 {match['Date']} - {match['Winning_Team']} Victory ({match['Game_End_Condition']})"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**🗽 Liberal Team:**")
                    for player in match['Liberal_Team'].split(', '):
                        st.write(f"• {player}")
                with col2:
                    st.write("**🏛️ Fascist Team:**")
                    fascists = match['Fascist_Team'].split(', ')
                    for i, player in enumerate(fascists):
                        if player == match['Hitler']:
                            st.write(f"• {player} 👑 (Hitler)")
                        else:
                            st.write(f"• {player}")
                
                if match.get('Shooter') and match.get('Shot_Player'):
                    st.write(f"**🔫 Shooting:** {match['Shooter']} shot {match['Shot_Player']}")
                
                if match.get('Match_Notes'):
                    st.write(f"**📝 Notes:** {match['Match_Notes']}")
    else:
        st.info("No match history available yet.")
    
    st.write("---")
    
    # Admin Section (Password Protected)
    st.header("🔐 Game Management (Admin Only)")
    
    # Check password before showing admin features
    if not check_password():
        st.info("👀 **Public View**: You can see the current ELO standings and recent match history above.")
        st.info("🔒 **Admin Access**: Enter the password above to run games and update ELO scores.")
        return
    
    # Admin successfully logged in
    st.success("✅ Admin access granted!")
    
    # Logout button
    if st.button("🚪 Logout"):
        st.session_state.password_correct = False
        st.rerun()
    
    # Google Sheets connection status (Admin only)
    with st.expander("📊 Google Sheets Connection", expanded=False):
        st.write("**Status:** Connected to Google Sheets for persistent storage")
        
        # Show sheet URL in admin section too
        if sheet_url:
            st.write(f"**Sheet URL:** {sheet_url}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📥 Load from Sheets"):
                with st.spinner("Loading player data..."):
                    loaded_elos = load_player_elos()
                    if loaded_elos:
                        st.session_state.player_elos = loaded_elos
                        st.session_state.sheets_loaded = True
                        st.success(f"Loaded {len(loaded_elos)} players from Google Sheets!")
                        st.rerun()
                    else:
                        st.info("No player data found in sheets.")
        
        with col2:
            if st.button("💾 Save to Sheets"):
                if st.session_state.player_elos:
                    with st.spinner("Saving player data..."):
                        if save_player_elos(st.session_state.player_elos):
                            st.success("Player data saved to Google Sheets!")
                        else:
                            st.error("Failed to save data.")
                else:
                    st.warning("No player data to save.")
        
        with col3:
            if st.button("🔄 Manual Reload"):
                with st.spinner("Reloading player data..."):
                    loaded_elos = load_player_elos()
                    if loaded_elos:
                        st.session_state.player_elos = loaded_elos
                        st.session_state.sheets_loaded = True
                        st.success(f"Reloaded {len(loaded_elos)} players!")
                        st.rerun()
    
    # Player ELO Management (Admin only)
    with st.expander("👥 Manage Player ELO Ratings", expanded=False):
        st.subheader("Current Player Ratings")
        
        # Add new player
        col1, col2 = st.columns(2)
        with col1:
            new_player = st.text_input("Add New Player:", key="new_player_input")
        with col2:
            initial_elo = st.number_input("Initial ELO:", min_value=0, value=1200, key="initial_elo_input")
        
        if st.button("Add Player") and new_player:
            if new_player not in st.session_state.player_elos:
                st.session_state.player_elos[new_player] = initial_elo
                st.success(f"Added {new_player} with ELO {initial_elo}")
                st.rerun()
            else:
                st.warning(f"{new_player} already exists!")
        
        # Display and edit existing players
        if st.session_state.player_elos:
            st.write("**Current Players:**")
            players_to_remove = []
            
            for player, elo in st.session_state.player_elos.items():
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"**{player}**")
                with col2:
                    new_elo = st.number_input(f"ELO", min_value=0, value=int(elo), key=f"elo_{player}")
                    if new_elo != elo:
                        st.session_state.player_elos[player] = new_elo
                with col3:
                    if st.button("Remove", key=f"remove_{player}"):
                        players_to_remove.append(player)
            
            # Remove players marked for removal
            for player in players_to_remove:
                del st.session_state.player_elos[player]
                st.rerun()
            
            # Quick save option
            if st.button("💾 Quick Save Changes"):
                with st.spinner("Saving changes..."):
                    if save_player_elos(st.session_state.player_elos):
                        st.success("Changes saved to Google Sheets!")
                    else:
                        st.error("Failed to save changes.")
    
    # Game Setup (Admin only)
    st.header("🎮 Secret Hitler Game Setup")
    
    if not st.session_state.player_elos:
        st.warning("Please add some players first or load existing data from Google Sheets!")
        return
    
    available_players = list(st.session_state.player_elos.keys())
    
    # Team configuration
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗽 Liberal Team")
        liberal_size = st.selectbox("Liberal Team Size:", options=[3, 4, 5, 6], key="liberal_size")
        liberal_players = []
        for i in range(liberal_size):
            player = st.selectbox(
                f"Liberal {i+1}:", 
                options=[""] + available_players,
                key=f"liberal_player_{i}"
            )
            if player:
                liberal_players.append(player)
    
    with col2:
        st.subheader("🏛️ Fascist Team")
        fascist_size = st.selectbox("Fascist Team Size:", options=[2, 3, 4], key="fascist_size")
        fascist_players = []
        hitler = None
        
        for i in range(fascist_size):
            if i == 0:
                player = st.selectbox(
                    f"👑 Hitler:", 
                    options=[""] + available_players,
                    key=f"fascist_player_{i}"
                )
                if player:
                    fascist_players.append(player)
                    hitler = player
            else:
                player = st.selectbox(
                    f"Fascist {i}:", 
                    options=[""] + available_players,
                    key=f"fascist_player_{i}"
                )
                if player:
                    fascist_players.append(player)
    
    # Validation
    all_selected_players = liberal_players + fascist_players
    if len(all_selected_players) != len(set(all_selected_players)):
        st.error("⚠️ Each player can only be on one team!")
        return
    
    if len(liberal_players) != liberal_size or len(fascist_players) != fascist_size:
        st.warning("Please select all players for both teams.")
        return
    
    # Display current team ratings
    st.subheader("Current Team Ratings")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**🗽 Liberal Team:**")
        liberal_total = 0
        for player in liberal_players:
            elo = st.session_state.player_elos[player]
            st.write(f"• {player}: {elo}")
            liberal_total += elo
        liberal_avg = liberal_total / len(liberal_players)
        st.write(f"**Average: {liberal_avg:.1f}**")
    
    with col2:
        st.write("**🏛️ Fascist Team:**")
        fascist_total = 0
        for player in fascist_players:
            elo = st.session_state.player_elos[player]
            if player == hitler:
                st.write(f"• {player}: {elo} 👑 (Hitler)")
            else:
                st.write(f"• {player}: {elo}")
            fascist_total += elo
        fascist_avg = fascist_total / len(fascist_players)
        st.write(f"**Average: {fascist_avg:.1f}**")
    
    # Game Result
    st.header("🏆 Game Result")
    
    col1, col2 = st.columns(2)
    with col1:
        winning_team = st.radio("Which team won?", options=["Liberal", "Fascist"], key="winning_team")
    
    with col2:
        game_end_options = [
            "5 Liberal Policies",
            "5 Fascist Policies", 
            "Hitler Elected Chancellor",
            "Hitler Shot"
        ]
        game_end_condition = st.selectbox("How did the game end?", options=game_end_options, key="game_end")
    
    # Optional shooting information
    st.subheader("🔫 Shooting Information (Optional)")
    col1, col2 = st.columns(2)
    with col1:
        shooter = st.selectbox("Who shot (if anyone)?", options=[""] + all_selected_players, key="shooter")
    with col2:
        shot_options = [""] + all_selected_players if shooter else [""]
        shot_player = st.selectbox("Who was shot?", options=shot_options, key="shot_player")
    
    # Optional match notes
    match_notes = st.text_area("Match Notes (Optional):", key="match_notes", placeholder="Any additional notes about this game...")
    
    k_factor = st.slider("K-Factor (rating change sensitivity):", min_value=16, max_value=64, value=32, key="k_factor")
    
    if st.button("Calculate ELO Updates", type="primary"):
        # Calculate updates for both teams
        liberal_won = winning_team == "Liberal"
        fascist_won = winning_team == "Fascist"
        
        liberal_updates = calculate_team_elo_update(liberal_players, fascist_players, liberal_won, k_factor)
        fascist_updates = calculate_team_elo_update(fascist_players, liberal_players, fascist_won, k_factor)
        
        # Display results
        st.header("📈 ELO Updates")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if liberal_won:
                st.success("**🗽 Liberal Team (Winners) 🏆**")
            else:
                st.error("**🗽 Liberal Team (Losers) 😞**")
            
            for player, update in liberal_updates.items():
                change_color = "green" if update['change'] >= 0 else "red"
                st.write(f"**{player}:**")
                st.write(f"• Before: {update['old_rating']:.1f}")
                st.write(f"• After: {update['new_rating']:.1f}")
                st.write(f"• Change: :{change_color}[{update['change']:+.1f}]")
                st.write("---")
        
        with col2:
            if fascist_won:
                st.success("**🏛️ Fascist Team (Winners) 🏆**")
            else:
                st.error("**🏛️ Fascist Team (Losers) 😞**")
            
            for player, update in fascist_updates.items():
                change_color = "green" if update['change'] >= 0 else "red"
                st.write(f"**{player}:**")
                if player == hitler:
                    st.write(f"• Before: {update['old_rating']:.1f} 👑")
                    st.write(f"• After: {update['new_rating']:.1f} 👑")
                else:
                    st.write(f"• Before: {update['old_rating']:.1f}")
                    st.write(f"• After: {update['new_rating']:.1f}")
                st.write(f"• Change: :{change_color}[{update['change']:+.1f}]")
                st.write("---")
        
        # Option to apply updates and save match
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Apply ELO Updates", type="secondary"):
                # Update the session state with new ratings
                for player, update in {**liberal_updates, **fascist_updates}.items():
                    st.session_state.player_elos[player] = update['new_rating']
                
                st.success("✅ ELO ratings have been updated!")
                st.rerun()
        
        with col2:
            if st.button("Apply Updates & Save Match", type="primary"):
                # Update the session state with new ratings
                for player, update in {**liberal_updates, **fascist_updates}.items():
                    st.session_state.player_elos[player] = update['new_rating']
                
                # Prepare match data
                match_data = {
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'liberal_team': liberal_players,
                    'fascist_team': fascist_players,
                    'hitler': hitler,
                    'winning_team': winning_team,
                    'game_end_condition': game_end_condition,
                    'shooter': shooter if shooter else '',
                    'shot_player': shot_player if shot_player else '',
                    'liberal_elo_changes': {player: update['change'] for player, update in liberal_updates.items()},
                    'fascist_elo_changes': {player: update['change'] for player, update in fascist_updates.items()},
                    'notes': match_notes if match_notes else ''
                }
                
                # Save to Google Sheets
                with st.spinner("Saving match and updated ratings..."):
                    # Save ELO updates
                    elo_saved = save_player_elos(st.session_state.player_elos)
                    # Save match history
                    match_saved = save_match_history(match_data)
                    
                    if elo_saved and match_saved:
                        st.success("✅ ELO ratings updated and match saved!")
                    elif elo_saved:
                        st.warning("✅ ELO ratings updated, but failed to save match history.")
                    elif match_saved:
                        st.warning("✅ Match saved, but failed to update ELO ratings.")
                    else:
                        st.error("❌ Failed to save both ELO ratings and match history.")
                
                st.rerun()

    # Debug section for testing (Admin only)
    with st.expander("🔧 Debug & Testing", expanded=False):
        st.write("**Test Google Sheets Connection:**")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Test Save ELO"):
                test_data = {"TestPlayer": 1250.5}
                if save_player_elos(test_data):
                    st.success("✅ ELO save test successful!")
                else:
                    st.error("❌ ELO save test failed!")
        
        with col2:
            if st.button("Test Save Match"):
                test_match = {
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'liberal_team': ['TestLib1', 'TestLib2'],
                    'fascist_team': ['TestFas1', 'TestFas2'],
                    'hitler': 'TestFas1',
                    'winning_team': 'Liberal',
                    'game_end_condition': 'Test Match',
                    'shooter': '',
                    'shot_player': '',
                    'liberal_elo_changes': {'TestLib1': 10, 'TestLib2': 10},
                    'fascist_elo_changes': {'TestFas1': -10, 'TestFas2': -10},
                    'notes': 'Test match'
                }
                if save_match_history(test_match):
                    st.success("✅ Match save test successful!")
                else:
                    st.error("❌ Match save test failed!")

if __name__ == "__main__":
    main()
