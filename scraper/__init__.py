"""
Standalone scraper for OpenPath door access data.

This package an be executed
via cron job or manually to sync data from the OpenPath API to the local database.

Usage:
    python -m scraper.main

The scraper reads configuration via the scraper.config module
and writes to the database defined in the configuration.
"""
