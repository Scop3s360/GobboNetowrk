# PyInstaller hook override for 'workflow' module namespace conflict.
# This prevents PyInstaller from executing the contrib 'hook-workflow.py'
# which targets a third-party package not used here.

# Do nothing, letting PyInstaller analyze our local 'workflow' folder normally.
