# Examen_core.py
from datetime import datetime

# Verbonden studenten
clients = {}        # socket → studentnaam
last_pong = {}      # studentnaam → timestamp

# Tijd waarna een student als offline wordt beschouwd
TIMEOUT_SECONDS = 10
