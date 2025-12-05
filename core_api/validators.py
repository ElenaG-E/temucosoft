import re
from rest_framework.exceptions import ValidationError

def clean_rut(rut: str) -> str:
    """Limpia el RUT, dejando solo números y la K (mayúscula), y elimina puntos o guiones."""
    if not isinstance(rut, str):
        raise ValidationError("El RUT debe ser una cadena de texto.")
    
    # Eliminar puntos, guiones y espacios
    rut_limpio = re.sub(r'[.-]', '', rut).strip().upper()
    return rut_limpio

def calculate_dv(rut_body: str) -> str:
    """Calcula el Dígito Verificador (DV) usando el algoritmo de la serie 2, 3, 4, 5, 6, 7."""
    try:
        rut_body = rut_body.zfill(8) # Rellena con ceros a la izquierda (ej: 76.xxx.xxx)
        reversed_digits = map(int, rut_body[::-1])
    except ValueError:
        return "" # Retorna vacío si el cuerpo no es numérico

    factor = 2
    sum_digits = 0
    for digit in reversed_digits:
        sum_digits += digit * factor
        factor += 1
        if factor > 7:
            factor = 2

    remainder = sum_digits % 11
    dv = 11 - remainder
    
    if dv == 10:
        return 'K'
    elif dv == 11:
        return '0'
    else:
        return str(dv)

def validate_chilean_rut(value: str):
    """
    Validador principal de RUT chileno.
    Acepta formatos como 76.xxx.xxx-k, 76xxxxxxk, 12345678-k, etc.
    """
    rut_limpio = clean_rut(value)
    
    if len(rut_limpio) < 2:
        raise ValidationError("El RUT no es válido: demasiado corto.")

    dv_ingresado = rut_limpio[-1]
    rut_body = rut_limpio[:-1]

    # Verificar que el cuerpo del RUT sea numérico
    if not rut_body.isdigit():
        raise ValidationError("El cuerpo del RUT debe contener solo números.")

    # Calcular el DV
    dv_calculado = calculate_dv(rut_body)

    if dv_calculado == dv_ingresado:
        return value # Retorna el valor original si es válido
    else:
        raise ValidationError(
            f"El RUT ingresado ('{value}') es inválido. El dígito verificador correcto es '{dv_calculado}'."
        )
