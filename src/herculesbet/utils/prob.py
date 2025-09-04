def remove_overround_1x2(odds_tuple):
    """
    1X2 odds -> marzs-mentesített implied valószínűségek.
    odds_tuple: (H, D, A) decimális oddsok
    """
    h, d, a = odds_tuple
    if min(h, d, a) <= 1.0:
        raise ValueError("Odds must be > 1.0")
    inv = [1.0 / h, 1.0 / d, 1.0 / a]
    s = sum(inv)
    return [x / s for x in inv]

