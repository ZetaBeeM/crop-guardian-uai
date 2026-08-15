import type { AgronomistResult } from "../types/diagnostico";

interface Props {
  result: AgronomistResult;
}

export default function AgronomistCard({ result }: Props) {
  return (
    <div className="card">
      <h2>Recomendación Agronómica</h2>

      <p>
        <b>Explicación:</b>
      </p>

      <p>{result.explicacion}</p>

      <p>
        <b>Tratamiento:</b>
      </p>

      <p>{result.tratamiento}</p>

      <p>
        <b>Prevención:</b>
      </p>

      <p>{result.prevencion}</p>

      <p>
        <b>Urgencia:</b> {result.urgencia}
      </p>

      <p>
        <b>Próxima revisión:</b> {result.proxima_revision_dias} días
      </p>
    </div>
  );
}
