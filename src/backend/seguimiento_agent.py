"""
AgenteSeguimiento
-----------------
Compara el diagnóstico actual de una planta/cultivo con su historial almacenado
en Cosmos DB, para determinar si la condición mejoró, empeoró o se mantuvo,
y sugerir una recomendación de seguimiento.

Este agente recibe el historial ya consultado (lista de documentos de Cosmos)
para no acoplarse directamente al cliente de base de datos; eso facilita
testearlo de forma aislada.
"""

from datetime import datetime

# Orden de severidad de menor a mayor gravedad.
ORDEN_SEVERIDAD = {
    "sano": 0,
    "leve": 1,
    "moderado": 2,
    "severo": 3,
}


class AgenteSeguimiento:
    def evaluar_evolucion(self, historial: list, diagnostico_actual: dict) -> dict:
        """
        Args:
            historial: lista de documentos previos de la misma planta/cultivo,
                       cada uno con clave 'resultado' -> {'severidad': ...} y 'fecha'.
            diagnostico_actual: dict con al menos la clave 'severidad'.

        Returns:
            dict con:
                - tendencia: "mejoro" | "empeoro" | "sin_cambios" | "sin_historial"
                - severidad_anterior: str | None
                - severidad_actual: str
                - recomendacion_seguimiento: str
        """
        severidad_actual = diagnostico_actual.get("severidad", "moderado")

        if not historial:
            return {
                "tendencia": "sin_historial",
                "severidad_anterior": None,
                "severidad_actual": severidad_actual,
                "recomendacion_seguimiento": (
                    "Primer diagnóstico registrado para esta planta. "
                    "Se recomienda continuar el monitoreo regular."
                ),
            }

        historial_ordenado = sorted(
            historial, key=lambda doc: doc.get("fecha", ""), reverse=True
        )
        ultimo = historial_ordenado[0]
        severidad_anterior = ultimo.get("resultado", {}).get("severidad", "moderado")

        nivel_anterior = ORDEN_SEVERIDAD.get(severidad_anterior, 2)
        nivel_actual = ORDEN_SEVERIDAD.get(severidad_actual, 2)

        if nivel_actual < nivel_anterior:
            tendencia = "mejoro"
            recomendacion = (
                "La condición de la planta ha mejorado respecto al último "
                "diagnóstico. Mantener el tratamiento actual y continuar el "
                "monitoreo periódico."
            )
        elif nivel_actual > nivel_anterior:
            tendencia = "empeoro"
            recomendacion = (
                "La condición de la planta ha empeorado. Se recomienda "
                "intensificar el tratamiento y, si es posible, consultar a "
                "un agrónomo de forma presencial."
            )
        else:
            tendencia = "sin_cambios"
            recomendacion = (
                "No se observan cambios significativos respecto al último "
                "diagnóstico. Continuar con el tratamiento y reevaluar en la "
                "próxima fecha sugerida."
            )

        return {
            "tendencia": tendencia,
            "severidad_anterior": severidad_anterior,
            "severidad_actual": severidad_actual,
            "recomendacion_seguimiento": recomendacion,
        }
