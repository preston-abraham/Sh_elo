import streamlit as st
import math
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

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

def get_worksheet():
    """Get or create the ELO tracking worksheet"""
    try:
        client = init_connection()
        if not client:
            return None
            
        sheet_name = st.secrets.get("sheet_name", "ELO_Tracker")
        
        try:
            # Try to open existing sheet
            sheet = client.open(sheet_name)
        except gspread.SpreadsheetNotFound:
            # Create new sheet if it doesn't exist
            sheet = client.create(sheet_name)
            # Make it shareable (optional)
            sheet.share('', perm_type='anyone', role='reader')
            st.success(f"Created new Google Sheet: {sheet_name}")
        
        # Get or create the Players worksheet
        try:
            worksheet = sheet.worksheet("Players")
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title="Players", rows="100", cols="20")
            # Add headers
            worksheet.update('A1:C1', [['Player', 'ELO', 'Last_Updated']])
            
        return worksheet
    except Exception as e:
        st.error(f"Error accessing worksheet: {str(e)}")
        return None

def load_player_elos():
    """Load player ELO ratings from Google Sheets"""
    try:
        worksheet = get_worksheet()
        if not worksheet:
            return {}
            
        # Get all data
        data = worksheet.get_all_records()
        
        # Convert to dictionary
        player_elos = {}
        for row in data:
            if row['Player'] and row['ELO']:  # Skip empty rows
                player_elos[row['Player']] = float(row['ELO'])
                
        return player_elos
    except Exception as e:
        st.error(f"Error loading player data: {str(e)}")
        return {}

def save_player_elos(player_elos):
    """Save player ELO ratings to Google Sheets"""
    try:
        worksheet = get_worksheet()
        if not worksheet:
            return False
            
        # Clear existing data (except headers)
        worksheet.clear()
        worksheet.update('A1:C1', [['Player', 'ELO', 'Last_Updated']])
        
        # Prepare data for upload
        data_to_upload = []
        for player, elo in player_elos.items():
            data_to_upload.append([player, elo, pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')])
        
        if data_to_upload:
            # Update sheet with new data
            worksheet.update(f'A2:C{len(data_to_upload) + 1}', data_to_upload)
            
        return True
    except Exception as e:
        st.error(f"Error saving player data: {str(e)}")
        return False

# Initialize session state for player ELO ratings
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

def main():
    st.title("🎲 Multiplayer ELO Calculator")
    st.write("Calculate ELO ratings after each round of your multiplayer tabletop game!")
    
    # Google Sheets connection status
    with st.expander("📊 Google Sheets Connection", expanded=False):
        st.write("**Status:** Connected to Google Sheets for persistent storage")
        
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
            if st.button("🔄 Auto-Load"):
                if not st.session_state.sheets_loaded:
                    with st.spinner("Auto-loading player data..."):
                        loaded_elos = load_player_elos()
                        if loaded_elos:
                            st.session_state.player_elos = loaded_elos
                            st.session_state.sheets_loaded = True
                            st.success(f"Auto-loaded {len(loaded_elos)} players!")
                            st.rerun()
    
    # Auto-load on first visit
    if not st.session_state.sheets_loaded and st.session_state.player_elos == {}:
        with st.spinner("Loading existing player data..."):
            loaded_elos = load_player_elos()
            if loaded_elos:
                st.session_state.player_elos = loaded_elos
                st.session_state.sheets_loaded = True
                st.success(f"Auto-loaded {len(loaded_elos)} players from Google Sheets!")
                st.rerun()
    
    # Player ELO Management
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
    
    # Game Setup
    st.header("🎮 Game Setup")
    
    if not st.session_state.player_elos:
        st.warning("Please add some players first or load existing data from Google Sheets!")
        return
    
    available_players = list(st.session_state.player_elos.keys())
    
    # Team configuration
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Team 1")
        team1_size = st.selectbox("Team 1 Size:", options=[2, 3, 4, 5], key="team1_size")
        team1_players = []
        for i in range(team1_size):
            player = st.selectbox(
                f"Player {i+1}:", 
                options=[""] + available_players,
                key=f"team1_player_{i}"
            )
            if player:
                team1_players.append(player)
    
    with col2:
        st.subheader("Team 2")
        team2_size = st.selectbox("Team 2 Size:", options=[2, 3, 4, 5], key="team2_size")
        team2_players = []
        for i in range(team2_size):
            player = st.selectbox(
                f"Player {i+1}:", 
                options=[""] + available_players,
                key=f"team2_player_{i}"
            )
            if player:
                team2_players.append(player)
    
    # Validation
    all_selected_players = team1_players + team2_players
    if len(all_selected_players) != len(set(all_selected_players)):
        st.error("⚠️ Each player can only be on one team!")
        return
    
    if len(team1_players) != team1_size or len(team2_players) != team2_size:
        st.warning("Please select all players for both teams.")
        return
    
    # Display current team ratings
    st.subheader("Current Team Ratings")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Team 1:**")
        team1_total = 0
        for player in team1_players:
            elo = st.session_state.player_elos[player]
            st.write(f"• {player}: {elo}")
            team1_total += elo
        team1_avg = team1_total / len(team1_players)
        st.write(f"**Average: {team1_avg:.1f}**")
    
    with col2:
        st.write("**Team 2:**")
        team2_total = 0
        for player in team2_players:
            elo = st.session_state.player_elos[player]
            st.write(f"• {player}: {elo}")
            team2_total += elo
        team2_avg = team2_total / len(team2_players)
        st.write(f"**Average: {team2_avg:.1f}**")
    
    # Game Result
    st.header("🏆 Game Result")
    winning_team = st.radio("Which team won?", options=["Team 1", "Team 2"], key="winning_team")
    
    k_factor = st.slider("K-Factor (rating change sensitivity):", min_value=16, max_value=64, value=32, key="k_factor")
    
    if st.button("Calculate ELO Updates", type="primary"):
        # Calculate updates for both teams
        team1_won = winning_team == "Team 1"
        team2_won = winning_team == "Team 2"
        
        team1_updates = calculate_team_elo_update(team1_players, team2_players, team1_won, k_factor)
        team2_updates = calculate_team_elo_update(team2_players, team1_players, team2_won, k_factor)
        
        # Display results
        st.header("📈 ELO Updates")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if team1_won:
                st.success("**Team 1 (Winners) 🏆**")
            else:
                st.error("**Team 1 (Losers) 😞**")
            
            for player, update in team1_updates.items():
                change_color = "green" if update['change'] >= 0 else "red"
                st.write(f"**{player}:**")
                st.write(f"• Before: {update['old_rating']:.1f}")
                st.write(f"• After: {update['new_rating']:.1f}")
                st.write(f"• Change: :{change_color}[{update['change']:+.1f}]")
                st.write("---")
        
        with col2:
            if team2_won:
                st.success("**Team 2 (Winners) 🏆**")
            else:
                st.error("**Team 2 (Losers) 😞**")
            
            for player, update in team2_updates.items():
                change_color = "green" if update['change'] >= 0 else "red"
                st.write(f"**{player}:**")
                st.write(f"• Before: {update['old_rating']:.1f}")
                st.write(f"• After: {update['new_rating']:.1f}")
                st.write(f"• Change: :{change_color}[{update['change']:+.1f}]")
                st.write("---")
        
        # Option to apply updates
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Apply ELO Updates", type="secondary"):
                # Update the session state with new ratings
                for player, update in {**team1_updates, **team2_updates}.items():
                    st.session_state.player_elos[player] = update['new_rating']
                
                st.success("✅ ELO ratings have been updated!")
                st.rerun()
        
        with col2:
            if st.button("Apply & Save to Sheets", type="primary"):
                # Update the session state with new ratings
                for player, update in {**team1_updates, **team2_updates}.items():
                    st.session_state.player_elos[player] = update['new_rating']
                
                # Save to Google Sheets
                with st.spinner("Saving updated ratings..."):
                    if save_player_elos(st.session_state.player_elos):
                        st.success("✅ ELO ratings updated and saved to Google Sheets!")
                    else:
                        st.error("ELO ratings updated locally, but failed to save to sheets.")
                st.rerun()

if __name__ == "__main__":
    main()
