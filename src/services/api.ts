import type { ApiResponse, PlantSummary } from "../types/diagnostico";

// Mismo origen que el backend: Flask sirve el frontend desde static/.
const API_URL = "";

/**
 * Mensaje a mostrar cuando la API falla.
 *
 * Solo se usa el texto del servidor en los 4xx, que son accionables por quien
 * usa la app (falta la foto, imagen muy grande, sesion caducada). Los 5xx
 * devuelven str(e) y ahi puede venir cualquier cosa, como el volcado entero
 * de un error de credenciales de Azure.
 */
async function mensajeDeError(response: Response, porDefecto: string) {
  if (response.status >= 500) return porDefecto;

  try {
    const cuerpo = await response.json();
    return typeof cuerpo?.error === "string" ? cuerpo.error : porDefecto;
  } catch {
    return porDefecto;
  }
}

export async function analizarCultivo(
  imagenBase64: string,
  nombrePlanta: string,
): Promise<ApiResponse> {
  const response = await fetch(`${API_URL}/api/analizar-cultivo`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      imagen: imagenBase64,
      nombre_planta: nombrePlanta,
    }),
  });

  if (!response.ok) {
    throw new Error(
      await mensajeDeError(
        response,
        "No se pudo analizar la foto. Intentalo de nuevo en un momento.",
      ),
    );
  }

  return response.json();
}

export async function obtenerHistorial() {
  const response = await fetch(`${API_URL}/api/historial`);

  if (!response.ok) {
    throw new Error("Error al obtener el historial");
  }

  return response.json();
}

export async function obtenerPlantas(): Promise<PlantSummary[]> {
  const response = await fetch(`${API_URL}/api/plantas`);

  if (!response.ok) {
    throw new Error("Error al obtener las plantas");
  }

  return response.json();
}

export async function eliminarPlanta(nombrePlanta: string): Promise<void> {
  const response = await fetch(
    `${API_URL}/api/plantas/${encodeURIComponent(nombrePlanta)}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    throw new Error("Error al eliminar la planta");
  }
}
