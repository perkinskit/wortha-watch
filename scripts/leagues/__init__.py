from leagues.nfl import NFL
from leagues.cfb import CFB
from leagues.nba import NBA
from leagues.nhl import NHL

LEAGUES = {cls.slug: cls for cls in (NFL, CFB, NBA, NHL)}
