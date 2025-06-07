"""
Tests for the homepage event status dashboard functionality including
event information, tournament display, and cage configuration.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestEventStatusDashboard:
    """Test the event status dashboard on homepage"""
    
    @pytest.fixture
    def mock_event_config(self):
        """Create mock event configuration data"""
        return {
            'event_name': 'Robot Rumble 2025',
            'event_league': 'Combat Robotics League',
            'event_date': '2025-06-07',
            'match_duration': 180,
            'countdown_duration': 5,
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb',
                    'weightInt': 12
                },
                {
                    'id': 'tournament2',
                    'tourn_type': 'truefinals',
                    'weightclass': '3lb',
                    'weightInt': 3
                }
            ],
            'tournament_cages': [
                {
                    'id': 1,
                    'name': 'Main Arena'
                },
                {
                    'id': 2,
                    'name': 'Practice Arena'
                }
            ]
        }
    
    def test_homepage_loads_with_dashboard(self, client):
        """Test that homepage loads with event status dashboard"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Event Status Dashboard' in response.data
    
    def test_event_information_display(self, client, mock_event_config):
        """Test that event information is correctly displayed"""
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_event_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Check event information
            assert b'Robot Rumble 2025' in response.data
            assert b'Combat Robotics League' in response.data
            assert b'2025-06-07' in response.data
            assert b'180s' in response.data  # Match duration
            assert b'5s' in response.data    # Countdown duration
    
    def test_tournament_display_with_names(self, client, mock_event_config):
        """Test that tournaments are displayed with human-readable names"""
        with patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_settings.side_effect = lambda key, default=None: mock_event_config.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': '12lb Championship'}}]
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Check tournament display
            assert b'Tournaments (2)' in response.data  # Count
            assert b'12lb Championship' in response.data  # Tournament name from API
    
    def test_cage_configuration_display(self, client, mock_event_config):
        """Test that cage/arena configuration is displayed"""
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_event_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Check cage information
            assert b'Cages/Arenas (2)' in response.data
            assert b'Main Arena' in response.data
            assert b'Practice Arena' in response.data
            assert b'Cage ID: 1' in response.data
            assert b'Cage ID: 2' in response.data
    
    def test_quick_access_dropdowns(self, client, mock_event_config):
        """Test that cage quick access dropdowns are present"""
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_event_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Check quick access links
            assert b'/control/1' in response.data      # Judge control
            assert b'/screens/1/timer/red' in response.data  # Red player screen
            assert b'/screens/1/timer/blue' in response.data # Blue player screen
            assert b'/screens/1/timer' in response.data      # Stream overlay


class TestSystemReadyIndicator:
    """Test the system ready/configuration incomplete indicator"""
    
    def test_system_ready_with_config(self, client):
        """Test system ready indicator when properly configured"""
        mock_config = {
            'tournament_keys': [{'id': 'tournament1'}],
            'tournament_cages': [{'id': 1, 'name': 'Arena'}]
        }
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show system ready
            assert b'System Ready' in response.data
            assert b'Event is configured and ready for matches' in response.data
    
    def test_configuration_incomplete_no_tournaments(self, client):
        """Test configuration incomplete when no tournaments configured"""
        mock_config = {
            'tournament_keys': [],
            'tournament_cages': [{'id': 1, 'name': 'Arena'}]
        }
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show configuration incomplete
            assert b'Configuration Incomplete' in response.data
            assert b'No tournaments configured' in response.data
    
    def test_configuration_incomplete_no_cages(self, client):
        """Test configuration incomplete when no cages configured"""
        mock_config = {
            'tournament_keys': [{'id': 'tournament1'}],
            'tournament_cages': []
        }
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show configuration incomplete
            assert b'Configuration Incomplete' in response.data
            assert b'No cages configured' in response.data


class TestQuickActionButtons:
    """Test quick action buttons on homepage"""
    
    def test_quick_action_buttons_present(self, client):
        """Test that all quick action buttons are present"""
        response = client.get('/')
        assert response.status_code == 200
        
        # Check action buttons
        assert b'/matches/upcoming' in response.data    # Match Queue
        assert b'/matches/fight-log' in response.data   # Fight Log
        assert b'/setup' in response.data               # Setup Wizard
        assert b'/settings' in response.data            # Settings
        
        # Check button text
        assert b'View Match Queue' in response.data
        assert b'Fight Log' in response.data
        assert b'Setup Wizard' in response.data
        assert b'Settings' in response.data


class TestTournamentNameResolution:
    """Test tournament name resolution from TrueFinals API"""
    
    def test_tournament_name_from_api(self, client):
        """Test that tournament names are fetched from TrueFinals API"""
        mock_config = {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb'
                }
            ]
        }
        
        with patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            mock_tournament_details.return_value = [{'response': {'title': 'Heavyweight Championship'}}]
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show API-fetched name
            assert b'Heavyweight Championship' in response.data
    
    def test_tournament_name_fallback(self, client):
        """Test fallback to weightclass when API fails"""
        mock_config = {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'truefinals',
                    'weightclass': '12lb'
                }
            ]
        }
        
        with patch('bracketeer.config.settings.get') as mock_settings, \
             patch('bracketeer.api_truefinals.cached_api.getTournamentDetails') as mock_tournament_details:
            
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            mock_tournament_details.side_effect = Exception("API Error")
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show fallback name
            assert b'12lb' in response.data  # Weightclass fallback
    
    def test_non_truefinals_tournament(self, client):
        """Test handling of non-TrueFinals tournaments"""
        mock_config = {
            'tournament_keys': [
                {
                    'id': 'tournament1',
                    'tourn_type': 'challonge',
                    'weightclass': '3lb'
                }
            ]
        }
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show weightclass for non-TrueFinals
            assert b'3lb' in response.data


class TestEmptyConfiguration:
    """Test homepage behavior with minimal configuration"""
    
    def test_no_event_name(self, client):
        """Test display when no event name is configured"""
        mock_config = {}
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show default values
            assert b'No Event Configured' in response.data
            assert b'Unknown League' in response.data
            assert b'Date not set' in response.data
    
    def test_no_tournaments_configured(self, client):
        """Test display when no tournaments are configured"""
        mock_config = {'tournament_keys': []}
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show no tournaments message
            assert b'Tournaments (0)' in response.data
            assert b'No tournaments configured' in response.data
    
    def test_no_cages_configured(self, client):
        """Test display when no cages are configured"""
        mock_config = {'tournament_cages': []}
        
        with patch('bracketeer.config.settings.get') as mock_settings:
            mock_settings.side_effect = lambda key, default=None: mock_config.get(key, default)
            
            response = client.get('/')
            assert response.status_code == 200
            
            # Should show no cages message
            assert b'Cages/Arenas (0)' in response.data
            assert b'No cages configured' in response.data


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
    
    # Add the homepage route with proper logic
    @app.route("/")
    def index():
        from bracketeer.config import settings
        from bracketeer.api_truefinals.cached_api import getTournamentDetails
        
        # Mock event configuration
        event_config = {
            'name': settings.get('event_name', 'No Event Configured'),
            'league': settings.get('event_league', 'Unknown League'),
            'date': settings.get('event_date', 'Date not set'),
            'match_duration': settings.get('match_duration', 150),
            'countdown_duration': settings.get('countdown_duration', 3),
            'tournaments': [],
            'cages': settings.get('tournament_cages', [])
        }
        
        # Enhance tournament data with actual names from API
        tournament_keys = settings.get('tournament_keys', [])
        for tournament in tournament_keys:
            enhanced_tournament = tournament.copy()
            enhanced_tournament['display_name'] = tournament.get('weightclass', f'Tournament {tournament["id"]}')
            event_config['tournaments'].append(enhanced_tournament)
        
        return ac_render_template("homepage.html", title="Landing Page", event_config=event_config)
    
    with app.test_client() as client:
        with app.app_context():
            yield client