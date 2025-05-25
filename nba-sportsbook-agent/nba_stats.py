from datetime import datetime, timedelta
from nba_api.stats.endpoints import boxscoresummaryv2, boxscoretraditionalv2, commonteamroster, playergamelog, scoreboardv2, teamgamelog
from nba_api.stats.static import players, teams
import pandas as pd
import time

CURRENT_SEASON = '2024-25'
ALL_SEASON_TYPES = ['Pre Season', 'Regular Season', 'Playoffs', 'PlayIn']


def get_teams():
	nba_teams = teams.get_teams()
	df_teams = pd.DataFrame(nba_teams)
	return df_teams


def get_all_players():
	all_players = players.get_players()
	df_players = pd.DataFrame(all_players)
	return df_players


def get_team_players(team_id, season=CURRENT_SEASON):
	roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=season)
	players_df = roster.get_data_frames()[0]  # First DataFrame contains the player info
	return players_df


def get_upcoming_games(days_ahead=1):
	all_games = []

	for i in range(days_ahead + 1):  # Include today
		game_date = (datetime.today() + timedelta(days=i)).strftime('%m/%d/%Y')
		scoreboard = scoreboardv2.ScoreboardV2(game_date=game_date)
		games_df = scoreboard.get_data_frames()[0]
		all_games.append(games_df)

	if len(all_games) == 0:
		return pd.DataFrame()

	all_games_df = pd.concat(all_games, ignore_index=True)
	all_games_df = all_games_df.sort_values(by="GAME_DATE_EST")
	return all_games_df


def get_team_stats(team_id, season=CURRENT_SEASON):
	all_games = []

	for season_type in ALL_SEASON_TYPES:
		game_log = teamgamelog.TeamGameLog(
			team_id=team_id,
			season=season,
			season_type_all_star=season_type
		)
		df = game_log.get_data_frames()[0]
		df['SEASON_TYPE'] = season_type  # Tag the game type
		all_games.append(df)

	if len(all_games) == 0:
		return pd.DataFrame()

	all_games_df = pd.concat(all_games, ignore_index=True)
	all_games_df['GAME_DATE_DT'] = pd.to_datetime(all_games_df['GAME_DATE'])
	all_games_df = all_games_df.sort_values(by='GAME_DATE_DT', ascending=False)
	return all_games_df 


def get_game_summary(game_id):
	box_score_summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
	df = box_score_summary.get_data_frames()[5]  # LineScore

	return df


def get_game_stats(game_id):
	box_score = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
	data_frames = box_score.get_data_frames()

	# Unpack safely
	player_stats_df = data_frames[0]	# PlayerStats
	team_starter_bench_stats_df = data_frames[1]	# TeamStarterBenchStats
	team_stats_df = data_frames[2]	# TeamStats
	
	return player_stats_df, team_stats_df


def get_player_stats(player_id, season=CURRENT_SEASON):
	all_games = []

	for season_type in ALL_SEASON_TYPES:
		game_log = playergamelog.PlayerGameLog(
			player_id=player_id,
			season=season,
			season_type_all_star=season_type
		)
		df = game_log.get_data_frames()[0]
		df['SEASON_TYPE'] = season_type
		all_games.append(df)

	if len(all_games) == 0:
		return pd.DataFrame()

	all_games_df = pd.concat(all_games, ignore_index=True)
	all_games_df['GAME_DATE_DT'] = pd.to_datetime(all_games_df['GAME_DATE'])
	all_games_df = all_games_df.sort_values(by='GAME_DATE_DT', ascending=False)
	return all_games_df
