from datetime import datetime, timedelta
from nba_api.stats.endpoints import boxscoresummaryv2, boxscoretraditionalv2, commonteamroster, playergamelog, scoreboardv2, teamgamelog
from nba_api.stats.static import players, teams
from utils import logger
import pandas as pd


class NBAStatsAPI:
    def __init__(self, current_season='2024-25', season_types = ['Pre Season', 'Regular Season', 'Playoffs', 'PlayIn']):
        self.CURRENT_SEASON = current_season
        self.SEASON_TYPES = season_types

    def get_teams(self):
        logger.debug("Fetching all NBA teams.")
        try:
            nba_teams_data = teams.get_teams()
            df_teams = pd.DataFrame(nba_teams_data)
            logger.info(f"Successfully fetched {len(df_teams)} NBA teams.")
            return df_teams
        except Exception as e:
            logger.error(f"Error fetching NBA teams: {e}", exc_info=True)
            raise

    def get_all_players(self):
        logger.debug("Fetching all NBA players.")
        try:
            all_players_data = players.get_players()
            df_players = pd.DataFrame(all_players_data)
            logger.info(f"Successfully fetched {len(df_players)} players.")
            return df_players
        except Exception as e:
            logger.error(f"Error fetching all NBA players: {e}", exc_info=True)
            raise

    def get_team_players(self, team_id):
        logger.debug(f"Fetching team roster for team_id: {team_id}, season: {self.CURRENT_SEASON}.")
        try:
            roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=self.CURRENT_SEASON)
            players_df = roster.get_data_frames()[0]  # First DataFrame contains the player info
            if players_df.empty:
                logger.info(f"No players found for team_id: {team_id}, season: {self.CURRENT_SEASON}.")
            else:
                logger.info(f"Successfully fetched {len(players_df)} players for team_id: {team_id}, season: {self.CURRENT_SEASON}.")
            return players_df
        except Exception as e:
            logger.error(f"Error fetching team roster for team_id {team_id}: {e}", exc_info=True)
            raise

    def get_upcoming_games(self, days_ahead=1):
        logger.debug(f"Fetching upcoming games for {days_ahead} days ahead.")
        all_games_list = []
        try:
            for i in range(days_ahead + 1):  # Include today
                game_date_str = (datetime.today() + timedelta(days=i)).strftime('%m/%d/%Y')
                logger.debug(f"Fetching games for date: {game_date_str}")
                scoreboard = scoreboardv2.ScoreboardV2(game_date=game_date_str)
                games_df = scoreboard.get_data_frames()[0]
                all_games_list.append(games_df)

            if not all_games_list:
                logger.info("No upcoming games found within the specified range.")
                return pd.DataFrame()

            all_games_df = pd.concat(all_games_list, ignore_index=True)
            all_games_df = all_games_df.sort_values(by="GAME_DATE_EST")
            logger.info(f"Successfully fetched {len(all_games_df)} upcoming games.")
            return all_games_df
        except Exception as e:
            logger.error(f"Error fetching upcoming games: {e}", exc_info=True)
            raise

    def get_team_stats(self, team_id):
        logger.debug(f"Fetching team game logs for team_id: {team_id}, season: {self.CURRENT_SEASON}.")
        all_games_list = []
        try:
            for season_type in self.SEASON_TYPES:
                logger.debug(f"Fetching team game log for season type: {season_type}")
                # time.sleep(0.1) # Consider delay
                game_log = teamgamelog.TeamGameLog(
                    team_id=team_id,
                    season=self.CURRENT_SEASON,
                    season_type_all_star=season_type # Corrected parameter name
                )
                df = game_log.get_data_frames()[0]
                if not df.empty:
                    df['SEASON_TYPE'] = season_type  # Tag the game type
                    all_games_list.append(df)
                else:
                    logger.debug(f"No team game log data for team_id {team_id}, season {self.CURRENT_SEASON}, type {season_type}.")


            if not all_games_list:
                logger.info(f"No team game logs found for team_id: {team_id}, season: {self.CURRENT_SEASON} across all season types.")
                return pd.DataFrame()

            all_games_df = pd.concat(all_games_list, ignore_index=True)
            all_games_df['GAME_DATE_DT'] = pd.to_datetime(all_games_df['GAME_DATE'])
            all_games_df = all_games_df.sort_values(by='GAME_DATE_DT', ascending=False)
            logger.info(f"Successfully fetched {len(all_games_df)} team game log entries for team_id: {team_id}.")
            return all_games_df
        except Exception as e:
            logger.error(f"Error fetching team stats for team_id {team_id}: {e}", exc_info=True)
            raise

    def get_game_summary(self, game_id):
        logger.debug(f"Fetching game summary for game_id: {game_id}.")
        try:
            box_score_summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
            # Index 5 corresponds to the 'LineScore' DataFrame in the BoxScoreSummaryV2 endpoint
            df_summary = box_score_summary.get_data_frames()[5]
            if df_summary.empty:
                 logger.info(f"No game summary (LineScore) found for game_id: {game_id}.")
            else:
                logger.info(f"Successfully fetched game summary for game_id: {game_id}.")
            return df_summary
        except Exception as e:
            logger.error(f"Error fetching game summary for game_id {game_id}: {e}", exc_info=True)
            raise

    def get_game_stats(self, game_id):
        logger.debug(f"Fetching game stats for game_id: {game_id}.")
        try:
            box_score = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id)
            data_frames = box_score.get_data_frames()

            player_stats_df = data_frames[0]    # PlayerStats
            team_starter_bench_stats_df = data_frames[1]    # TeamStarterBenchStats
            team_stats_df = data_frames[2]    # TeamStats

            if player_stats_df.empty and team_stats_df.empty:
                 logger.info(f"No player or team stats found for game_id: {game_id}.")
            else:
                logger.info(f"Successfully fetched player stats ({len(player_stats_df)} rows) and team stats ({len(team_stats_df)} rows) for game_id: {game_id}.")
            return player_stats_df, team_stats_df
        except Exception as e:
            logger.error(f"Error fetching game stats for game_id {game_id}: {e}", exc_info=True)
            raise

    def get_player_stats(self, player_id):
        logger.debug(f"Fetching player game logs for player_id: {player_id}, season: {self.CURRENT_SEASON}.")
        all_games_list = []
        try:
            for season_type in self.SEASON_TYPES:
                logger.debug(f"Fetching player game log for season type: {season_type}")
                # time.sleep(0.1) # Consider delay
                game_log = playergamelog.PlayerGameLog(
                    player_id=player_id,
                    season=self.CURRENT_SEASON,
                    season_type_all_star=season_type # Corrected parameter name
                )
                df = game_log.get_data_frames()[0]
                if not df.empty:
                    df['SEASON_TYPE'] = season_type
                    all_games_list.append(df)
                else:
                    logger.debug(f"No player game log data for player_id {player_id}, season {self.CURRENT_SEASON}, type {season_type}.")


            if not all_games_list:
                logger.info(f"No player game logs found for player_id: {player_id}, season: {self.CURRENT_SEASON} across all season types.")
                return pd.DataFrame()

            all_games_df = pd.concat(all_games_list, ignore_index=True)
            all_games_df['GAME_DATE_DT'] = pd.to_datetime(all_games_df['GAME_DATE'])
            all_games_df = all_games_df.sort_values(by='GAME_DATE_DT', ascending=False)
            logger.info(f"Successfully fetched {len(all_games_df)} player game log entries for player_id: {player_id}.")
            return all_games_df
        except Exception as e:
            logger.error(f"Error fetching player stats for player_id {player_id}: {e}", exc_info=True)
            raise
