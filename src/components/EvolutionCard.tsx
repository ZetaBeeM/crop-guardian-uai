import type { Evolution } from "../types/diagnostico";

interface Props {
  evolution: Evolution;
}

export default function EvolutionCard({ evolution }: Props) {
  return (
    <div className="card">
      <h2>📈 Seguimiento</h2>

      <p>
        <b>Tendencia:</b> {evolution.tendencia}
      </p>

      <p>
        <b>Anterior:</b> {evolution.severidad_anterior ?? "N/A"}
      </p>

      <p>
        <b>Actual:</b> {evolution.severidad_actual}
      </p>

      <p>{evolution.recomendacion_seguimiento}</p>
    </div>
  );
}
