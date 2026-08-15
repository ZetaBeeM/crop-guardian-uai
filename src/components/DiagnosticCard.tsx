import type { DiagnosisResult } from "../types/diagnostico";

interface Props {
  result: DiagnosisResult;
}

export default function DiagnosticCard({ result }: Props) {
  return (
    <div className="card">
      <h2>Diagnóstico</h2>

      <p>
        <b>Planta:</b> {result.planta}
      </p>

      <p>
        <b>Diagnóstico:</b> {result.enfermedad}
      </p>

      <p>
        <b>Severidad:</b> {result.severidad}
      </p>

      <p>
        <b>Confianza:</b> {(result.confianza * 100).toFixed(0)}%
      </p>

      <p>
        <b>Síntomas:</b>
      </p>

      <ul>
        {result.sintomas.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>
    </div>
  );
}
