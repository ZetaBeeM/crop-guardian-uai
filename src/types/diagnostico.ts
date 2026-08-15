export interface Evolution {
  tendencia: string;
  severidad_anterior: string | null;
  severidad_actual: string;
  recomendacion_seguimiento: string;
}

export interface DiagnosisResult {
  planta: string;
  sintomas: string[];
  enfermedad: string;
  severidad: string;
  confianza: number;
  razonamiento: string;
  urgente: boolean;
}

export interface AgronomistResult {
  explicacion: string;
  tratamiento: string;
  prevencion: string;
  urgencia: string;
  proxima_revision_dias: number;
}

export interface ApiResponse {
  diagnostico: DiagnosisResult;
  tratamiento: AgronomistResult;
  nombre_planta: string;
  proxima_revision: string;
}

export interface PlantSummary {
  nombre_planta: string;
  fecha: string;
  proxima_revision: string;
  diagnostico: string;
  severidad: string;
  explicacion: string;
  tratamiento: string;
  prevencion: string;
  urgencia: string;
  vencido: boolean;
}
