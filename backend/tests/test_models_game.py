from app.models import PlayerStats, TowerProgress


def test_tower_progress_persists(db_session):
    p = TowerProgress(level="N5", zone_idx=0, stage_idx=1, is_boss=False,
                      cleared=True, stars=2, best_accuracy=0.8, attempts=1)
    db_session.add(p)
    db_session.commit()
    got = db_session.query(TowerProgress).one()
    assert got.level == "N5" and got.stars == 2 and got.is_boss is False


def test_player_stats_defaults(db_session):
    s = PlayerStats(id=1)
    db_session.add(s)
    db_session.commit()
    assert db_session.get(PlayerStats, 1).total_xp == 0
    assert db_session.get(PlayerStats, 1).player_level == 1
