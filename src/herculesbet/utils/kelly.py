def fractional_kelly(prob: float, odds: float, fraction: float = 0.25) -> float:
    """
    Visszaadja a bankroll hányadát (0..1), amit feltegyünk.
    prob: modell szerinti nyerési valószínűség (0..1)
    odds: decimális odds (>=1.01)
    fraction: 0.25 -> negyed-Kelly
    """
    b = max(odds - 1.0, 1e-9)
    q = 1.0 - prob
    k = (b * prob - q) / b
    return max(k * fraction, 0.0)

