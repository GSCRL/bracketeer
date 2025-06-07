"""
WSGI entry point for production deployment with Gunicorn.

This module provides the WSGI application for production servers like Gunicorn,
separating it from the development server logic in __main__.py
"""

import logging
import os

# Import the Flask app and SocketIO instance
from bracketeer.__main__ import app, socketio

# Configure logging for production
if not app.debug:
    logging.basicConfig(level=logging.INFO)
    
    # Set up file logging for production
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = logging.FileHandler('logs/bracketeer.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    
    app.logger.setLevel(logging.INFO)
    app.logger.info('Bracketeer startup')

def create_app():
    """
    Application factory that returns the SocketIO WSGI application.
    This ensures proper initialization for production deployment.
    """
    return socketio

# The WSGI application that Gunicorn will use
application = create_app()

if __name__ == "__main__":
    # This allows running the WSGI app directly for testing
    socketio.run(app, host='0.0.0.0', port=8000)