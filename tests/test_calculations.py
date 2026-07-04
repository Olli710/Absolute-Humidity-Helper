import pytest
# Hier importieren wir die Berechnungsfunktionen direkt aus deiner sensor.py.
# (Passe den Pfad an, falls deine Berechnungen in einer util.py oder direkt in der sensor.py liegen)
from custom_components.absolute_humidity.sensor import (
    calculate_absolute_humidity,
    calculate_dew_point,
)

def test_absolute_humidity_calculation():
    """Testet die Berechnung der absoluten Feuchtigkeit bei 20°C und 50% rF."""
    # Erwarteter Wert für 20°C und 50% rF liegt bei ca. 8.65 g/m³ (je nach exakter Formel)
    temperature = 20.0
    humidity = 50.0
    
    result = calculate_absolute_humidity(temperature, humidity)
    
    # Wir runden auf 2 Nachkommastellen und vergleichen
    assert round(result, 2) == 8.65

def test_dew_point_calculation():
    """Testet die Berechnung des Taupunkts bei 20°C und 50% rF."""
    # Der Taupunkt bei 20°C und 50% rF liegt bei ca. 9.27°C
    temperature = 20.0
    humidity = 50.0
    
    result = calculate_dew_point(temperature, humidity)
    
    assert round(result, 2) == 9.27

def test_offline_or_invalid_values():
    """Testet, dass die Formeln bei unphysikalischen oder None-Werten nicht abstürzen."""
    with pytest.raises(TypeError):
        calculate_absolute_humidity(None, 50.0)
    
    with pytest.raises(TypeError):
        calculate_dew_point(20.0, None)
