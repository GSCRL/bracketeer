"""
Tests for the fight log functionality including tournament filtering,
match organization, and robot statistics.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import url_for


class TestFightLogRoute:
    """Test the fight log route and basic functionality"""
    
    def test_fight_log_route_exists(self, client):
        """Test that the fight log route is accessible"""
        response = client.get('/matches/fight-log')
        assert response.status_code == 200
        assert b'Fight Log' in response.data
    
    def test_fight_log_with_no_data(self, client):
        """Test fight log displays correctly when no tournament data exists"""
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_matches:
            mock_matches.return_value = []
            
            response = client.get('/matches/fight-log')
            assert response.status_code == 200
            assert b'No match data available' in response.data
    
    def test_fight_log_tournament_filter(self, client):
        """Test tournament filtering functionality"""
        tournament_id = 'test-tournament-123'
        response = client.get(f'/matches/fight-log?tournament={tournament_id}')
        assert response.status_code == 200
        # Should not crash even with invalid tournament ID


class TestFightLogDataOrganization:
    """Test how the fight log organizes and displays match data"""
    
    @pytest.fixture
    def mock_tournament_data(self):
        """Create mock tournament and match data for testing"""
        return {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb'
                }
            ]
        }
    
    @pytest.fixture
    def mock_matches(self):
        """Create mock match data with different states"""
        return [
            {
                'id': 'match1',
                'name': 'Finals',
                'state': 'done',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'winner': 'player1',
                'calledSince': 1640995200,  # Mock timestamp
                'slots': [
                    {
                        'id': 'player1',
                        'bracketeer_player_data': {
                            'name': 'Bot Alpha',
                            'wins': 3,
                            'losses': 1,
                            'ties': 0
                        }
                    },
                    {
                        'id': 'player2', 
                        'bracketeer_player_data': {
                            'name': 'Bot Beta',
                            'wins': 2,
                            'losses': 2,
                            'ties': 1
                        }
                    }
                ]
            },
            {
                'id': 'match2',
                'name': 'Semi-Final 1',
                'state': 'active',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'calledSince': 1640995300,
                'slots': [
                    {
                        'id': 'player3',
                        'bracketeer_player_data': {
                            'name': 'Bot Gamma',
                            'wins': 2,
                            'losses': 0,
                            'ties': 0
                        }
                    },
                    {
                        'id': 'player4',
                        'bracketeer_player_data': {
                            'name': 'Bot Delta',
                            'wins': 1,
                            'losses': 1,
                            'ties': 0
                        }
                    }
                ]
            },
            {
                'id': 'match3',
                'name': 'Quarter-Final 1',
                'state': 'available',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'slots': [
                    {
                        'id': 'player5',
                        'bracketeer_player_data': {
                            'name': 'Bot Epsilon',
                            'wins': 1,
                            'losses': 0,
                            'ties': 0
                        }
                    },
                    {
                        'id': 'player6',
                        'bracketeer_player_data': {
                            'name': 'Bot Zeta',
                            'wins': 0,
                            'losses': 1,
                            'ties': 0
                        }
                    }
                ]
            }
        ]
    
    def test_match_state_organization(self, client, mock_tournament_data, mock_matches):
        """Test that matches are correctly organized by their state"""
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.side_effect = lambda key, default=None: mock_tournament_data.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': '12lb Championship'}}]
            
            response = client.get('/matches/fight-log')
            assert response.status_code == 200
            
            # Check that different match states are present
            assert b'Completed Matches' in response.data  # For 'done' matches
            assert b'In Progress' in response.data        # For 'active' matches
            assert b'Next Up' in response.data           # For 'available' matches
    
    def test_robot_records_display(self, client, mock_tournament_data, mock_matches):
        """Test that robot win/loss records are correctly displayed"""
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.side_effect = lambda key, default=None: mock_tournament_data.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': '12lb Championship'}}]
            
            response = client.get('/matches/fight-log')
            assert response.status_code == 200
            
            # Check that robot records are displayed
            assert b'Bot Alpha' in response.data
            assert b'3W-1L-0T' in response.data  # Bot Alpha's record
            assert b'Bot Beta' in response.data
            assert b'2W-2L-1T' in response.data  # Bot Beta's record
    
    def test_tournament_statistics(self, client, mock_tournament_data, mock_matches):
        """Test that tournament statistics are correctly calculated"""
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.side_effect = lambda key, default=None: mock_tournament_data.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': '12lb Championship'}}]
            
            response = client.get('/matches/fight-log')
            assert response.status_code == 200
            
            # Check tournament statistics
            # Should have: 1 completed, 1 in progress, 1 upcoming = 3 total
            response_text = response.data.decode()
            assert 'Total</span>' in response_text
            assert 'Completed</span>' in response_text
            assert 'In Progress</span>' in response_text
            assert 'Upcoming</span>' in response_text


class TestFightLogWinnerDisplay:
    """Test winner identification and display in completed matches"""
    
    def test_winner_identification(self, client):
        """Test that match winners are correctly identified and displayed"""
        mock_matches = [
            {
                'id': 'match1',
                'name': 'Test Match',
                'state': 'done',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'winner': 'red_player',
                'slots': [
                    {
                        'id': 'red_player',
                        'bracketeer_player_data': {
                            'name': 'Red Bot',
                            'wins': 1,
                            'losses': 0,
                            'ties': 0
                        }
                    },
                    {
                        'id': 'blue_player',
                        'bracketeer_player_data': {
                            'name': 'Blue Bot',
                            'wins': 0,
                            'losses': 1,
                            'ties': 0
                        }
                    }
                ]
            }
        ]
        
        mock_tournament_data = {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb'
                }
            ]
        }
        
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.side_effect = lambda key, default=None: mock_tournament_data.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': '12lb Championship'}}]
            
            response = client.get('/matches/fight-log')
            assert response.status_code == 200
            
            # Should show red winner indication
            assert b'Red Wins' in response.data


class TestFightLogTournamentFiltering:
    """Test tournament filtering functionality"""
    
    def test_tournament_filter_dropdown(self, client):
        """Test that tournament filter dropdown is present and functional"""
        mock_matches = [
            {
                'id': 'match1',
                'name': 'Match 1',
                'state': 'done',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'slots': []
            },
            {
                'id': 'match2', 
                'name': 'Match 2',
                'state': 'done',
                'tournamentID': 'tournament2',
                'weightclass': '3lb',
                'slots': []
            }
        ]
        
        mock_tournament_data = {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb'
                },
                {
                    'id': 'tournament2',
                    'tourn_type': 'truefinals', 
                    'weightclass': '3lb'
                }
            ]
        }
        
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.side_effect = lambda key, default=None: mock_tournament_data.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': 'Championship'}}]
            
            response = client.get('/matches/fight-log')
            assert response.status_code == 200
            
            # Check that tournament filter dropdown exists
            assert b'tournament-filter' in response.data
            assert b'All Tournaments' in response.data
    
    def test_specific_tournament_filter(self, client):
        """Test filtering by specific tournament"""
        mock_matches = [
            {
                'id': 'match1',
                'name': 'Match 1',
                'state': 'done',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'slots': []
            },
            {
                'id': 'match2',
                'name': 'Match 2', 
                'state': 'done',
                'tournamentID': 'tournament2',
                'weightclass': '3lb',
                'slots': []
            }
        ]
        
        mock_tournament_data = {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb'
                },
                {
                    'id': 'tournament2',
                    'tourn_type': 'truefinals',
                    'weightclass': '3lb'
                }
            ]
        }
        
        with patch('bracketeer.matches.match_results.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.side_effect = lambda key, default=None: mock_tournament_data.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': 'Championship'}}]
            
            # Test filtering by tournament1
            response = client.get('/matches/fight-log?tournament=tournament1')
            assert response.status_code == 200


class TestFightLogNavigationIntegration:
    """Test navigation links to and from fight log"""
    
    def test_homepage_fight_log_link(self, client):
        """Test that homepage includes fight log navigation link"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'/matches/fight-log' in response.data
        assert b'Fight Log' in response.data
    
    def test_match_queue_fight_log_link(self, client):
        """Test that match queue includes fight log navigation link"""
        response = client.get('/matches/upcoming')
        assert response.status_code == 200
        assert b'/matches/fight-log' in response.data
        assert b'Fight Log' in response.data


@pytest.fixture
def client():
    """Create a test client for the Flask application"""
    from flask import Flask
    from bracketeer.matches.match_results import match_results
    from bracketeer.screens.user_screens import user_screens
    from bracketeer.debug.debug import debug_pages
    from bracketeer.util.wrappers import ac_render_template
    
    # Create a minimal test app without the socketio server startup
    app = Flask(__name__, static_folder="../bracketeer/static", template_folder="../bracketeer/templates")
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # Register blueprints
    app.register_blueprint(match_results, url_prefix="/matches")
    app.register_blueprint(user_screens, url_prefix="/screens")
    app.register_blueprint(debug_pages, url_prefix="/debug")
    
    # Add the homepage route
    @app.route("/")
    def index():
        return ac_render_template("homepage.html", title="Landing Page", event_config={
            'name': 'Test Event',
            'tournaments': [],
            'cages': []
        })
    
    with app.test_client() as client:
        with app.app_context():
            yield client