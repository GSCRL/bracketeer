"""
Tests for the enhanced match queue functionality including organized sections,
tournament names, and refresh functionality.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMatchQueueOrganization:
    """Test the organized match queue sections (Active, On Deck, Upcoming)"""
    
    @pytest.fixture
    def mock_organized_matches(self):
        """Create mock match data organized by status"""
        return [
            {
                'id': 'active_match',
                'name': 'Championship Final',
                'state': 'active',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'calledSince': 1640995200,
                'slots': [
                    {
                        'id': 'player1',
                        'bracketeer_player_data': {
                            'name': 'Lightning Bot',
                            'wins': 4,
                            'losses': 0,
                            'ties': 0
                        }
                    },
                    {
                        'id': 'player2',
                        'bracketeer_player_data': {
                            'name': 'Thunder Bot',
                            'wins': 3,
                            'losses': 1,
                            'ties': 0
                        }
                    }
                ]
            },
            {
                'id': 'called_match',
                'name': 'Semi-Final 1',
                'state': 'called',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'calledSince': 1640995300,
                'slots': [
                    {
                        'id': 'player3',
                        'bracketeer_player_data': {
                            'name': 'Storm Bot',
                            'wins': 2,
                            'losses': 1,
                            'ties': 1
                        }
                    },
                    {
                        'id': 'player4',
                        'bracketeer_player_data': {
                            'name': 'Wind Bot',
                            'wins': 3,
                            'losses': 0,
                            'ties': 0
                        }
                    }
                ]
            },
            {
                'id': 'available_match',
                'name': 'Quarter-Final 1',
                'state': 'available',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'slots': [
                    {
                        'id': 'player5',
                        'bracketeer_player_data': {
                            'name': 'Fire Bot',
                            'wins': 1,
                            'losses': 0,
                            'ties': 0
                        }
                    },
                    {
                        'id': 'player6',
                        'bracketeer_player_data': {
                            'name': 'Ice Bot',
                            'wins': 1,
                            'losses': 1,
                            'ties': 0
                        }
                    }
                ]
            }
        ]
    
    def test_match_queue_sections_present(self, client, mock_organized_matches):
        """Test that all three match queue sections are present"""
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_matches:
            mock_matches.return_value = mock_organized_matches
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Check that all three sections are present
            assert b'Fighting Now' in response.data        # Active section
            assert b'On Deck - Called to Arena' in response.data  # On Deck section
            assert b'Upcoming Matches' in response.data    # Upcoming section
    
    def test_active_matches_display(self, client, mock_organized_matches):
        """Test that active matches are displayed in the Fighting Now section"""
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_matches:
            mock_matches.return_value = mock_organized_matches
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Check active match content
            assert b'Lightning Bot' in response.data
            assert b'Thunder Bot' in response.data
            assert b'Championship Final' in response.data
            assert b'ACTIVE' in response.data
    
    def test_on_deck_matches_display(self, client, mock_organized_matches):
        """Test that called matches are displayed in the On Deck section"""
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_matches:
            mock_matches.return_value = mock_organized_matches
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Check on deck match content
            assert b'Storm Bot' in response.data
            assert b'Wind Bot' in response.data
            assert b'Semi-Final 1' in response.data
    
    def test_upcoming_matches_display(self, client, mock_organized_matches):
        """Test that available matches are displayed in the Upcoming section"""
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_matches:
            mock_matches.return_value = mock_organized_matches
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Check upcoming match content
            assert b'Fire Bot' in response.data
            assert b'Ice Bot' in response.data
            assert b'Quarter-Final 1' in response.data


class TestRobotRecordsDisplay:
    """Test robot win/loss/tie record display in match queue"""
    
    def test_robot_records_format(self, client):
        """Test that robot records are displayed in correct W-L-T format"""
        mock_matches = [
            {
                'id': 'test_match',
                'name': 'Test Match',
                'state': 'active',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'slots': [
                    {
                        'id': 'player1',
                        'bracketeer_player_data': {
                            'name': 'Test Bot',
                            'wins': 5,
                            'losses': 2,
                            'ties': 1
                        }
                    }
                ]
            }
        ]
        
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_get_matches:
            mock_get_matches.return_value = mock_matches
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Check that record is displayed correctly
            assert b'5W' in response.data  # Wins
            assert b'2L' in response.data  # Losses
            assert b'1T' in response.data  # Ties


class TestTournamentNameDisplay:
    """Test tournament name display instead of IDs"""
    
    def test_tournament_names_shown(self, client):
        """Test that tournament names are displayed instead of IDs"""
        mock_matches = [
            {
                'id': 'test_match',
                'name': 'Test Match',
                'state': 'active',
                'tournamentID': 'tournament1',
                'weightclass': '12lb',
                'tournament_display_name': '12lb Championship',
                'slots': []
            }
        ]
        
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_get_matches, \
             patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_get_matches.return_value = mock_matches
            mock_settings.return_value = [{'id': 'tournament1', 'tourn_type': 'truefinals'}]
            mock_tournament_details.return_value = [{'response': {'title': '12lb Championship'}}]
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Should show tournament name, not ID
            assert b'12lb Championship' in response.data


class TestMatchQueueRefresh:
    """Test refresh functionality in match queue"""
    
    def test_refresh_button_present(self, client):
        """Test that refresh button is present in match queue"""
        response = client.get('/matches/upcoming')
        assert response.status_code == 200
        
        # Check for refresh button
        assert b'refresh=1' in response.data
        assert b'Refresh' in response.data
    
    def test_refresh_parameter_handling(self, client):
        """Test that refresh parameter is handled correctly"""
        with patch('bracketeer.api_truefinals.cached_api.purge_API_Cache') as mock_purge:
            response = client.get('/matches/upcoming?refresh=1')
            assert response.status_code == 200
            
            # Should call cache purge when refresh=1
            mock_purge.assert_called_once_with(timer_passed=0)


class TestMatchStatusCounts:
    """Test match status count display in header"""
    
    def test_status_counts_display(self, client):
        """Test that match status counts are displayed in header"""
        mock_matches = [
            {'id': '1', 'state': 'active', 'tournamentID': 't1', 'slots': []},
            {'id': '2', 'state': 'active', 'tournamentID': 't1', 'slots': []},
            {'id': '3', 'state': 'called', 'tournamentID': 't1', 'slots': []},
            {'id': '4', 'state': 'available', 'tournamentID': 't1', 'slots': []},
            {'id': '5', 'state': 'available', 'tournamentID': 't1', 'slots': []},
            {'id': '6', 'state': 'available', 'tournamentID': 't1', 'slots': []}
        ]
        
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_get_matches:
            mock_get_matches.return_value = mock_matches
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Check status indicators are present
            assert b'Active' in response.data
            assert b'On Deck' in response.data
            assert b'Upcoming' in response.data


class TestMatchQueueNavigation:
    """Test navigation integration with fight log"""
    
    def test_fight_log_button_present(self, client):
        """Test that fight log button is present in match queue"""
        response = client.get('/matches/upcoming')
        assert response.status_code == 200
        
        # Check for fight log navigation
        assert b'/matches/fight-log' in response.data
        assert b'Fight Log' in response.data


class TestEmptyMatchQueue:
    """Test match queue behavior with no matches"""
    
    def test_no_matches_message(self, client):
        """Test display when no matches are available"""
        with patch('bracketeer.api_truefinals.cached_wrapper.getAllTournamentsMatchesWithPlayers') as mock_matches:
            mock_matches.return_value = []
            
            response = client.get('/matches/upcoming')
            assert response.status_code == 200
            
            # Should show "no matches" message
            assert b'No matches currently available' in response.data
            assert b'robot carnage' in response.data  # Part of the fun message


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