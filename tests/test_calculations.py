from custom_components.absolute_humidity.sensor import (
    calculate_absolute_humidity,
)


def test_absolute_humidity_calculation():
    """Testet die Berechnung der absoluten Feuchtigkeit bei 20°C und 50% rF."""
    temperature = 20.0
    humidity = 50.0

    result = calculate_absolute_humidity(temperature, humidity)

    # Deine Formel liefert präzise ~8.63 g/m³
    assert result is not None
    assert round(result, 2) == 8.63


def test_offline_or_invalid_values():
    """Testet, dass die Formel bei None-Werten nicht abstürzt und None zurückgibt."""
    # Da deine Implementierung den TypeError intern abfängt und loggt,
    # prüfen wir hier, ob die Funktion robust None zurückliefert.
    result = calculate_absolute_humidity(None, 50.0)
    assert result is None

    result = calculate_absolute_humidity(20.0, None)
    assert result is None
