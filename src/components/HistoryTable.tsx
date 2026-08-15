import { useState } from "react";

import { eliminarPlanta } from "../services/api";
import type { PlantSummary } from "../types/diagnostico";

interface Props {
  items: any[];
  plants: PlantSummary[];
  error?: boolean;
  onPlantDeleted?: () => void;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("es-CL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function daysOverdue(proximaRevision: string) {
  const ms = Date.now() - new Date(proximaRevision).getTime();
  return Math.max(0, Math.floor(ms / (1000 * 60 * 60 * 24)));
}

export default function HistoryTable({
  items,
  plants,
  error,
  onPlantDeleted,
}: Props) {
  const [expandida, setExpandida] = useState<string | null>(null);
  const [eliminando, setEliminando] = useState<string | null>(null);

  function toggle(nombre: string) {
    setExpandida((actual) => (actual === nombre ? null : nombre));
  }

  if (error) {
    return (
      <div className="card">
        <h2>Mis Plantas</h2>
        <p className="plant-empty">No se pudo obtener el historial.</p>
      </div>
    );
  }

  async function handleDelete(nombre: string, e: React.MouseEvent) {
    e.stopPropagation(); // evita que también se expanda/colapse la fila

    const confirmado = window.confirm(
      `¿Eliminar todo el registro de "${nombre}"? Esta acción no se puede deshacer.`,
    );
    if (!confirmado) return;

    try {
      setEliminando(nombre);
      await eliminarPlanta(nombre);
      if (expandida === nombre) setExpandida(null);
      onPlantDeleted?.();
    } catch (err) {
      alert("No se pudo eliminar la planta. Intenta nuevamente.");
    } finally {
      setEliminando(null);
    }
  }

  return (
    <div className="card">
      <h2>Mis Plantas</h2>

      {plants.length === 0 ? (
        <p className="plant-empty">
          Todavía no has etiquetado ninguna planta. Sube una foto y asígnale un
          nombre para empezar a seguir su evolución.
        </p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Planta</th>
              <th>Último diagnóstico</th>
              <th>Severidad</th>
              <th>Próxima revisión</th>
              <th></th>
            </tr>
          </thead>

          <tbody>
            {plants.map((plant) => {
              const abierta = expandida === plant.nombre_planta;
              const borrando = eliminando === plant.nombre_planta;

              return (
                <>
                  <tr
                    key={plant.nombre_planta}
                    className={
                      (plant.vencido ? "row-overdue " : "") + "row-clickable"
                    }
                    onClick={() => toggle(plant.nombre_planta)}
                    aria-expanded={abierta}
                  >
                    <td className="plant-name-cell">
                      <span className="row-caret">{abierta ? "▾" : "▸"}</span>
                      {plant.nombre_planta}
                    </td>
                    <td>{plant.diagnostico}</td>
                    <td>{plant.severidad}</td>
                    <td>
                      {plant.vencido ? (
                        <span className="overdue-badge">
                          📷 Envía otra foto · vencido hace{" "}
                          {daysOverdue(plant.proxima_revision)}{" "}
                          {daysOverdue(plant.proxima_revision) === 1
                            ? "día"
                            : "días"}
                        </span>
                      ) : (
                        formatDate(plant.proxima_revision)
                      )}
                    </td>
                    <td className="plant-actions-cell">
                      <button
                        type="button"
                        className="delete-plant-btn"
                        onClick={(e) => handleDelete(plant.nombre_planta, e)}
                        disabled={borrando}
                        aria-label={`Eliminar registro de ${plant.nombre_planta}`}
                        title="Eliminar registro de esta planta"
                      >
                        {borrando ? "…" : "🗑"}
                      </button>
                    </td>
                  </tr>

                  {abierta && (
                    <tr
                      key={`${plant.nombre_planta}-detalle`}
                      className="row-detail"
                    >
                      <td colSpan={5}>
                        <div className="plant-detail">
                          <div className="plant-detail-block">
                            <span className="plant-detail-label">
                              Explicación
                            </span>
                            <p>{plant.explicacion}</p>
                          </div>

                          <div className="plant-detail-block">
                            <span className="plant-detail-label">
                              Tratamiento
                            </span>
                            <p>{plant.tratamiento}</p>
                          </div>

                          <div className="plant-detail-block">
                            <span className="plant-detail-label">
                              Prevención
                            </span>
                            <p>{plant.prevencion}</p>
                          </div>

                          {plant.urgencia && (
                            <p className="plant-detail-urgencia">
                              <span className="plant-detail-label">
                                Urgencia
                              </span>{" "}
                              {plant.urgencia}
                            </p>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      )}

      <h2 className="history-subtitle">Registro completo</h2>

      <table>
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Planta</th>
            <th>Diagnóstico</th>
          </tr>
        </thead>

        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{formatDate(item.fecha)}</td>
              <td>{item.nombre_planta ?? "—"}</td>
              <td>{item.resultado.enfermedad}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
