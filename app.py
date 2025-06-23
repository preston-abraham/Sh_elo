import streamlit as st
import math

# Initialize session state for player ELO ratings
if 'player_elos' not in st.session_state:
    st.session_state.player_elos = {}

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
    
    # Player ELO Management
    with st.expander("📊 Manage Player ELO Ratings", expanded=False):
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
    
    # Game Setup
    st.header("🎮 Game Setup")
    
    if not st.session_state.player_elos:
        st.warning("Please add some players first using the expander above!")
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
        if st.button("Apply ELO Updates", type="secondary"):
            # Update the session state with new ratings
            for player, update in {**team1_updates, **team2_updates}.items():
                st.session_state.player_elos[player] = update['new_rating']
            
            st.success("✅ ELO ratings have been updated!")
            st.rerun()
