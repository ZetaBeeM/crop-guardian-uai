import { useEffect, useState } from "react";

import UploadForm from "./components/UploadForm";
import DiagnosticCard from "./components/DiagnosticCard";
import TreatmentCard from "./components/TreatmentCard";
import HistoryTable from "./components/HistoryTable";

import {
  analizarCultivo,
  obtenerHistorial,
  obtenerPlantas,
} from "./services/api";

import type { ApiResponse, PlantSummary } from "./types/diagnostico";

function App() {
  const [result, setResult] = useState<ApiResponse>();
  const [history, setHistory] = useState<any[]>([]);
  const [plants, setPlants] = useState<PlantSummary[]>([]);
  const [historyError, setHistoryError] = useState(false);
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const guardado = localStorage.getItem("cropguardian_theme");
    if (guardado) return guardado === "dark";
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  });

  useEffect(() => {
    document.documentElement.setAttribute(
      "data-theme",
      darkMode ? "dark" : "light",
    );
    localStorage.setItem("cropguardian_theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  async function refreshData() {
    try {
      const [historial, plantas] = await Promise.all([
        obtenerHistorial(),
        obtenerPlantas(),
      ]);
      setHistory(historial);
      setPlants(plantas);
      setHistoryError(false);
    } catch {
      setHistoryError(true);
    }
  }

  async function handleUpload(nombre: string, base64: string) {
    const response = await analizarCultivo(base64, nombre);

    setResult(response);

    await refreshData();
  }

  useEffect(() => {
    refreshData();
  }, []);

  return (
    <div className="container">
      <button
        type="button"
        className="theme-toggle"
        onClick={() => setDarkMode((d) => !d)}
        aria-label={darkMode ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
        title={darkMode ? "Modo claro" : "Modo oscuro"}
      >
        {darkMode ? "☀️" : "🌙"}
      </button>

      <h1>Crop Guardian uAI</h1>

      <p>Sistema Multiagente para Diagnóstico de Enfermedades en Plantas</p>

      <UploadForm onSubmit={handleUpload} />

      {result && (
        <>
          <DiagnosticCard result={result.diagnostico} />
          <TreatmentCard result={result.tratamiento} />
        </>
      )}

      <HistoryTable
        items={history}
        plants={plants}
        error={historyError}
        onPlantDeleted={refreshData}
      />
    </div>
  );
}

export default App;
