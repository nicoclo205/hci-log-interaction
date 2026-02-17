#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test de normalización de valores de emociones"""

def normalize_emotion(value):
    """Normaliza y clampea valor de emoción a rango [0, 1]"""
    try:
        if value is None:
            return 0.0
        normalized = float(value) / 100.0
        # Clampear al rango [0, 1] para cumplir con CHECK constraint
        return max(0.0, min(1.0, normalized))
    except (ValueError, TypeError):
        return 0.0


def test_normalization():
    """Prueba la función de normalización con varios casos"""
    print("🧪 Test de Normalización de Emociones\n")

    test_cases = [
        # (input, expected, description)
        (0, 0.0, "Valor mínimo"),
        (50, 0.5, "Valor medio"),
        (100, 1.0, "Valor máximo"),
        (150, 1.0, "Valor fuera de rango (>100)"),
        (-10, 0.0, "Valor negativo"),
        (None, 0.0, "Valor None"),
        ("50", 0.5, "String numérico"),
        ("invalid", 0.0, "String inválido"),
        (0.0, 0.0, "Float cero"),
        (99.9, 0.999, "Float válido"),
    ]

    all_passed = True

    for input_val, expected, description in test_cases:
        result = normalize_emotion(input_val)
        passed = abs(result - expected) < 0.001  # Tolerancia para floats

        status = "✅" if passed else "❌"
        print(f"{status} {description}")
        print(f"   Input: {input_val} → Output: {result:.3f} (Expected: {expected:.3f})")

        if not passed:
            all_passed = False
        print()

    print("=" * 60)
    if all_passed:
        print("✅ Todos los tests pasaron!")
        print("\n💡 La normalización está funcionando correctamente.")
        print("   Valores siempre estarán en el rango [0.0, 1.0]")
    else:
        print("❌ Algunos tests fallaron")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    test_normalization()
