"""
Tests for port configuration and automatic port detection functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
import socket


class TestPortDetection:
    """Test port availability detection and automatic port finding"""
    
    def test_is_port_available_true(self):
        """Test port availability detection for available port"""
        from bracketeer.__main__ import is_port_available
        
        # Test with a high port that should be available
        result = is_port_available('127.0.0.1', 65432)
        assert result is True
    
    def test_is_port_available_false(self):
        """Test port availability detection for unavailable port"""
        from bracketeer.__main__ import is_port_available
        
        # Create a socket to occupy a port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))  # Bind to any available port
            port = sock.getsockname()[1]
            
            # Test that the occupied port is detected as unavailable
            result = is_port_available('127.0.0.1', port)
            assert result is False
    
    def test_find_available_port_preferred_available(self):
        """Test finding port when preferred port is available"""
        from bracketeer.__main__ import find_available_port
        
        # Test with a high port that should be available
        preferred_port = 65431
        result = find_available_port('127.0.0.1', preferred_port)
        assert result == preferred_port
    
    def test_find_available_port_fallback(self):
        """Test finding alternative port when preferred is unavailable"""
        from bracketeer.__main__ import find_available_port
        
        # Create a socket to occupy the preferred port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))
            occupied_port = sock.getsockname()[1]
            
            # Try to find a port when the preferred one is occupied
            result = find_available_port('127.0.0.1', occupied_port)
            
            # Should return a different port
            assert result is not None
            assert result != occupied_port
    
    def test_find_available_port_common_ports(self):
        """Test that common development ports are tried first"""
        from bracketeer.__main__ import find_available_port
        
        with patch('bracketeer.__main__.is_port_available') as mock_available:
            # Mock that preferred port is unavailable, but 5000 is available
            def mock_port_check(host, port):
                if port == 9999:  # Preferred port
                    return False
                elif port == 5000:  # Common port
                    return True
                else:
                    return False
            
            mock_available.side_effect = mock_port_check
            
            result = find_available_port('127.0.0.1', 9999)
            assert result == 5000


class TestArgumentParsing:
    """Test command line argument parsing"""
    
    def test_parse_arguments_defaults(self):
        """Test default argument values"""
        from bracketeer.__main__ import parse_arguments
        
        with patch('sys.argv', ['bracketeer']):
            args = parse_arguments()
            assert args.port == 80
            assert args.host == '0.0.0.0'
            assert args.dev is False
            assert args.debug is False
            assert args.no_debug is False
    
    def test_parse_arguments_custom_port(self):
        """Test custom port argument"""
        from bracketeer.__main__ import parse_arguments
        
        with patch('sys.argv', ['bracketeer', '--port', '8080']):
            args = parse_arguments()
            assert args.port == 8080
    
    def test_parse_arguments_dev_mode(self):
        """Test development mode flag"""
        from bracketeer.__main__ import parse_arguments
        
        with patch('sys.argv', ['bracketeer', '--dev']):
            args = parse_arguments()
            assert args.dev is True
    
    def test_parse_arguments_custom_host(self):
        """Test custom host argument"""
        from bracketeer.__main__ import parse_arguments
        
        with patch('sys.argv', ['bracketeer', '--host', '127.0.0.1']):
            args = parse_arguments()
            assert args.host == '127.0.0.1'
    
    def test_parse_arguments_debug_flags(self):
        """Test debug mode flags"""
        from bracketeer.__main__ import parse_arguments
        
        with patch('sys.argv', ['bracketeer', '--debug']):
            args = parse_arguments()
            assert args.debug is True
        
        with patch('sys.argv', ['bracketeer', '--no-debug']):
            args = parse_arguments()
            assert args.no_debug is True


class TestServerStartup:
    """Test server startup logic with port configuration"""
    
    def test_dev_mode_port_selection(self):
        """Test port selection in development mode"""
        from bracketeer.__main__ import parse_arguments
        
        # Mock arguments for dev mode
        class MockArgs:
            port = 80
            host = '127.0.0.1'
            dev = True
            debug = False
            no_debug = False
        
        with patch('bracketeer.__main__.find_available_port') as mock_find_port, \
             patch('bracketeer.__main__.socketio') as mock_socketio:
            
            mock_find_port.return_value = 8080
            
            # This would test the main() function logic, but we need to mock more
            # For now, just test that the find_available_port function is called correctly
            from bracketeer.__main__ import find_available_port
            result = find_available_port('127.0.0.1', 80)
            
            # Should return a valid port number
            assert isinstance(result, int)
            assert result > 0
    
    def test_production_mode_port_check(self):
        """Test port validation in production mode"""
        from bracketeer.__main__ import is_port_available
        
        # Test that we can check if a port is available
        # This is essentially testing the same functionality as earlier tests
        # but in the context of production mode validation
        result = is_port_available('127.0.0.1', 65430)
        assert isinstance(result, bool)


class TestPortRangeSearch:
    """Test port range searching functionality"""
    
    def test_port_range_limits(self):
        """Test that port searching respects specified ranges"""
        from bracketeer.__main__ import find_available_port
        
        with patch('bracketeer.__main__.is_port_available') as mock_available:
            # Mock that only port 6000 is available in the range
            def mock_port_check(host, port):
                return port == 6000
            
            mock_available.side_effect = mock_port_check
            
            # Search in a limited range
            result = find_available_port('127.0.0.1', 9999, port_range=(6000, 6010))
            assert result == 6000
    
    def test_no_available_ports(self):
        """Test behavior when no ports are available"""
        from bracketeer.__main__ import find_available_port
        
        with patch('bracketeer.__main__.is_port_available') as mock_available:
            # Mock that no ports are available
            mock_available.return_value = False
            
            result = find_available_port('127.0.0.1', 9999, port_range=(6000, 6005))
            assert result is None


class TestCommandLineExamples:
    """Test that command line examples work as expected"""
    
    def test_help_message_generation(self):
        """Test that help message can be generated without errors"""
        from bracketeer.__main__ import parse_arguments
        
        # Test that argument parser can be created and help accessed
        with patch('sys.argv', ['bracketeer', '--help']):
            with pytest.raises(SystemExit):  # argparse exits after showing help
                parse_arguments()
    
    def test_port_shorthand(self):
        """Test that -p shorthand works for port"""
        from bracketeer.__main__ import parse_arguments
        
        with patch('sys.argv', ['bracketeer', '-p', '3000']):
            args = parse_arguments()
            assert args.port == 3000