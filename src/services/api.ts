import type { ApiResponse, PlantSummary } from "../types/diagnostico";

const API_URL = "http://localhost:5000";

export async function analizarCultivo(
  imagenBase64: string,
  nombrePlanta: string,
): Promise<ApiResponse> {
  const response = await fetch(`${API_URL}/analizar-cultivo`, {
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
    throw new Error("Error al analizar cultivo");
  }

  return response.json();
}

export async function obtenerHistorial() {
  const response = await fetch(`${API_URL}/historial`);

  if (!response.ok) {
    throw new Error("Error al obtener el historial");
  }

  return response.json();
}

export async function obtenerPlantas(): Promise<PlantSummary[]> {
  const response = await fetch(`${API_URL}/plantas`);

  if (!response.ok) {
    throw new Error("Error al obtener las plantas");
  }

  return response.json();
}

export async function eliminarPlanta(nombrePlanta: string): Promise<void> {
  const response = await fetch(
    `${API_URL}/plantas/${encodeURIComponent(nombrePlanta)}`,
    { method: "DELETE" },
  );

  if (!response.ok) {
    throw new Error("Error al eliminar la planta");
  }
}
