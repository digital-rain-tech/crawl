"""Informatica PowerCenter parsers.

PowerCenter exports use the POWERMART XML format (powrmart.dtd).
The export hierarchy is:
    POWERMART → REPOSITORY → FOLDER → {SOURCE, TARGET, MAPPLET, MAPPING, SESSION, WORKFLOW}

Currently supports offline XML export mode only (pctr-export:).
"""
