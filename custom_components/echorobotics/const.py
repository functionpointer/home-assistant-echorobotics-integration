"""Constants for the echorobotics integration."""
from datetime import timedelta

DOMAIN = "echorobotics"
UPDATE_INTERVAL = timedelta(minutes=2)
GETCONFIG_UPDATE_INTERVAL = timedelta(days=1)
HISTORY_UPDATE_INTERVAL = 15 * 60
RobotId = str
