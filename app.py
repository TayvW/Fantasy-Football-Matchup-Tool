import nflreadpy as nfl
import pandas as pd
import streamlit as st

st.title("🏈 Custom Fantasy Football Matchup & Waiver Tool")
st.write("Compare player usage, opponent defenses, and weekly projections.")

@st.cache_data
def load_data():
    df_2026 = nfl.load_player_stats([2026]).to_pandas()
    fantasy_positions = ['QB', 'RB', 'WR', 'TE']
    df = df_2026[df_2026['position'].isin(fantasy_positions)].copy()
    return df

with st.spinner("Loading 2026 NFL Data..."):
    df = load_data()

# League averages & DvP calculations
league_pos_avg = df.groupby('position')['fantasy_points_ppr'].mean().to_dict()

dvp = df.groupby(['opponent_team', 'position']).agg(
    def_pts_allowed=('fantasy_points_ppr', 'mean')
).reset_index()

dvp['dvp_multiplier'] = dvp.apply(
    lambda row: row['def_pts_allowed'] / league_pos_avg[row['position']] if league_pos_avg[row['position']] > 0 else 1.0, 
    axis=1
)

# Added average receiving yards and average rushing yards
player_baselines = df.groupby(['player_name', 'position', 'team']).agg(
    avg_targets=('targets', 'mean'),
    avg_rec_yards=('receiving_yards', 'mean'),
    avg_carries=('carries', 'mean'),
    avg_rush_yards=('rushing_yards', 'mean'),
    base_ppr=('fantasy_points_ppr', 'mean'),
    games_played=('week', 'nunique')
).reset_index()

player_baselines = player_baselines[player_baselines['games_played'] >= 1].copy()

# CREATE NAVIGATION TABS AT THE TOP
tab1, tab2 = st.tabs(["📊 Main Matchup Analyzer", "🚀 Waiver Wire & Sleeper Finder"])

# ==============================================================================
# TAB 1: EXACT ORIGINAL MATCHUP ANALYZER (UNCHANGED)
# ==============================================================================
with tab1:
    # --- SIDEBAR CONTROLS ---
    st.sidebar.header("Matchup Filters")

    all_teams = sorted(df['team'].dropna().unique())
    selected_team = st.sidebar.selectbox("Select Team to Analyze", all_teams)

    all_opponents = sorted(df['opponent_team'].dropna().unique())
    selected_opponent = st.sidebar.selectbox("Select Opposing Defense", all_opponents)

    selected_position = st.sidebar.selectbox("Select Position", ['QB', 'RB', 'WR', 'TE'])

    # --- MAIN DISPLAY ---
    st.subheader(f"Matchup: {selected_team} {selected_position}s vs. {selected_opponent} Defense")

    def_matchup = dvp[(dvp['opponent_team'] == selected_opponent) & (dvp['position'] == selected_position)]
    multiplier = def_matchup['dvp_multiplier'].values[0] if not def_matchup.empty else 1.0

    team_players = player_baselines[
        (player_baselines['team'] == selected_team) & 
        (player_baselines['position'] == selected_position)
    ].copy()

    if not team_players.empty:
        team_players['Matchup Multiplier'] = round(multiplier, 2)
        team_players['Projected PPR'] = round(team_players['base_ppr'] * multiplier, 2)
        
        # Round metrics to 1 decimal place for clean reading
        team_players['avg_targets'] = round(team_players['avg_targets'], 1)
        team_players['avg_rec_yards'] = round(team_players['avg_rec_yards'], 1)
        team_players['avg_carries'] = round(team_players['avg_carries'], 1)
        team_players['avg_rush_yards'] = round(team_players['avg_rush_yards'], 1)
        team_players['base_ppr'] = round(team_players['base_ppr'], 1)

        # Select display columns based on position relevance
        if selected_position in ['WR', 'TE']:
            cols = ['player_name', 'base_ppr', 'avg_targets', 'avg_rec_yards', 'Matchup Multiplier', 'Projected PPR']
            rename_dict = {
                'player_name': 'Player',
                'base_ppr': 'Season Avg PPR',
                'avg_targets': 'Avg Targets',
                'avg_rec_yards': 'Avg Rec Yards'
            }
        elif selected_position == 'RB':
            cols = ['player_name', 'base_ppr', 'avg_carries', 'avg_rush_yards', 'avg_targets', 'avg_rec_yards', 'Matchup Multiplier', 'Projected PPR']
            rename_dict = {
                'player_name': 'Player',
                'base_ppr': 'Season Avg PPR',
                'avg_carries': 'Avg Carries',
                'avg_rush_yards': 'Avg Rush Yards',
                'avg_targets': 'Avg Targets',
                'avg_rec_yards': 'Avg Rec Yards'
            }
        else:  # QB
            cols = ['player_name', 'base_ppr', 'avg_carries', 'avg_rush_yards', 'Matchup Multiplier', 'Projected PPR']
            rename_dict = {
                'player_name': 'Player',
                'base_ppr': 'Season Avg PPR',
                'avg_carries': 'Avg Rush Att',
                'avg_rush_yards': 'Avg Rush Yards'
            }
        
        display_df = team_players[cols].rename(columns=rename_dict).sort_values(by='Projected PPR', ascending=False)
        
        st.dataframe(display_df, use_container_width=True)
        
        if multiplier > 1.1:
            st.success(f"🟢 **Favorable Matchup!** The {selected_opponent} allow +{int((multiplier-1)*100)}% more points than average to {selected_position}s.")
        elif multiplier < 0.9:
            st.warning(f"🔴 **Tough Matchup!** The {selected_opponent} lock down opposing {selected_position}s (-{int((1-multiplier)*100)}%).")
    else:
        st.info("No player data found for this combination.")

# ==============================================================================
# TAB 2: NEW WAIVER WIRE & SLEEPER FINDER (SEPARATED)
# ==============================================================================
with tab2:
    st.header("🎯 Undervalued & Sleeper Target Finder")
    st.write("Find players with high underlying workload volume or favorable matchup spikes.")

    filter_pos = st.radio("Filter Position View", ['ALL', 'WR', 'RB', 'TE'], horizontal=True)

    data_scope = player_baselines.copy()
    if filter_pos != 'ALL':
        data_scope = data_scope[data_scope['position'] == filter_pos]

    st.markdown("---")
    
    # SECTION A: Sneaky High-Volume Earners
    st.subheader("🔥 Sneaky Volume Earners (High Opportunity)")
    st.caption("Players averaging 5+ targets or 10+ carries per game across the league.")

    high_vol = data_scope[(data_scope['avg_targets'] >= 5.0) | (data_scope['avg_carries'] >= 10.0)].copy()
    
    high_vol['avg_targets'] = round(high_vol['avg_targets'], 1)
    high_vol['avg_carries'] = round(high_vol['avg_carries'], 1)
    high_vol['avg_rec_yards'] = round(high_vol['avg_rec_yards'], 1)
    high_vol['avg_rush_yards'] = round(high_vol['avg_rush_yards'], 1)
    high_vol['base_ppr'] = round(high_vol['base_ppr'], 1)

    vol_cols = ['player_name', 'team', 'position', 'avg_targets', 'avg_rec_yards', 'avg_carries', 'avg_rush_yards', 'base_ppr']
    vol_rename = {
        'player_name': 'Player',
        'team': 'Team',
        'position': 'Pos',
        'avg_targets': 'Avg Targets',
        'avg_rec_yards': 'Avg Rec Yds',
        'avg_carries': 'Avg Carries',
        'avg_rush_yards': 'Avg Rush Yds',
        'base_ppr': 'Avg PPR Points'
    }

    st.dataframe(
        high_vol[vol_cols].rename(columns=vol_rename).sort_values(by=['Avg Targets', 'Avg Carries'], ascending=False),
        use_container_width=True
    )

    st.markdown("---")

    # SECTION B: Matchup Streamers & Sleeper Boom Candidates
    st.subheader("⚡ Top Matchup Multiplier Targets")
    st.caption("Lower-baseline players facing defenses that allow +10% or more points than average (Multiplier ≥ 1.10).")

    favorable_dvp = dvp[dvp['dvp_multiplier'] >= 1.10].copy()
    
    matchup_sleepers = pd.merge(data_scope, favorable_dvp, left_on='position', right_on='position')
    matchup_sleepers['Projected PPR'] = round(matchup_sleepers['base_ppr'] * matchup_sleepers['dvp_multiplier'], 2)
    matchup_sleepers['dvp_multiplier'] = round(matchup_sleepers['dvp_multiplier'], 2)
    matchup_sleepers['base_ppr'] = round(matchup_sleepers['base_ppr'], 1)

    # Focus on sleeper range (baseline average under 14 PPR)
    sleeper_streamers = matchup_sleepers[matchup_sleepers['base_ppr'] < 14.0].sort_values(by='Projected PPR', ascending=False)

    stream_cols = ['player_name', 'team', 'position', 'opponent_team', 'base_ppr', 'dvp_multiplier', 'Projected PPR']
    stream_rename = {
        'player_name': 'Player',
        'team': 'Team',
        'position': 'Pos',
        'opponent_team': 'Opponent Defense',
        'base_ppr': 'Baseline PPR',
        'dvp_multiplier': 'Matchup Boost',
        'Projected PPR': 'Projected PPR'
    }

    st.dataframe(
        sleeper_streamers[stream_cols].rename(columns=stream_rename).head(15),
        use_container_width=True
    )