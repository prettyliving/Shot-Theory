# Definitions

Fixing these up front keeps the analysis honest. Change them deliberately, not by accident.

| Term | Definition |
|---|---|
| Game scope | Regular season only (`game_type = 2`) unless stated |
| Win / Loss / OTL | Regulation win, regulation loss, or loss in OT/shootout (1 point) |
| Goal differential | Goals for minus goals against |
| Shot share | Team shots for / (shots for + shots against) |
| Shooting % | Goals / shots on goal |
| Win streak | 3+ consecutive wins (OTL breaks a win streak but not a loss streak, since it is a non-win) |
| Losing streak | 3+ consecutive games without a win |
| Consistently productive | Player with 20+ games and a point in at least 50% of them, with low variance in points per game (coefficient of variation below the league median among qualifiers). Refine after seeing the data |
| Production trend | Rolling 10-game points per game |

## Known limits
- Shot attempts (Corsi/Fenwick) are not in the boxscore; v1 uses shots on goal only.
- Shootout goals count in the final score but are not skater goals.
