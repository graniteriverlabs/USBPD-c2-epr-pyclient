"""
Built-in default logging configuration.
Auto-generated from config/logging_config.json by tools/generate_internal_defaults.py.
Used when logging_config.json is not provided or not found.
"""

from typing import Any, Dict

DEFAULT_LOGGING_CONFIG: Dict[str, Any] = {'version': '1.0',
 'description': 'Logging configuration - default, session, environments, formats',
 'configLocation': 'config/logging_config.json',
 'default': {'logFilename': 'api_framework.log',
             'logDirectory': 'user_interaction/logs',
             'logLevel': 'INFO',
             'logToConsole': True,
             'maxLogSizeMb': 10,
             'backupCount': 5,
             'rotationType': 'size',
             'logMode': 'a',
             'loggerName': 'ApiFramework'},
 'session': {'logFilename': 'api_framework_session.log',
             'logDirectory': 'user_interaction/logs',
             'logLevel': 'INFO',
             'logToConsole': True,
             'maxLogSizeMb': 5,
             'backupCount': 3,
             'rotationType': 'size',
             'logMode': 'a',
             'loggerName': 'ApiFramework_Session'},
 'environments': {'development': {'logLevel': 'DEBUG',
                                  'logToConsole': True,
                                  'maxLogSizeMb': 5,
                                  'backupCount': 3,
                                  'rotationType': 'size'},
                  'production': {'logLevel': 'INFO',
                                 'logToConsole': False,
                                 'maxLogSizeMb': 50,
                                 'backupCount': 30,
                                 'rotationType': 'time'},
                  'testing': {'logLevel': 'WARNING',
                              'logToConsole': True,
                              'logMode': 'w',
                              'backupCount': 1,
                              'maxLogSizeMb': 2}},
 'formats': {'simple': '%(asctime)s - %(levelname)s - %(message)s',
             'detailed': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] [%(threadName)s] - '
                         '%(message)s',
             'debug': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] [%(threadName)s] '
                      '[%(funcName)s] - %(message)s',
             'json': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": '
                     '"%(name)s"}'}}
