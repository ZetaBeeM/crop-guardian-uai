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

import type {
  ApiResponse,
  HistoryEntry,
  PlantSummary,
} from "./types/diagnostico";

function App() {
  const [result, setResult] = useState<ApiResponse>();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [plants, setPlants] = useState<PlantSummary[]>([]);
  const [historyError, setHistoryError] = useState(false);
  const [analizando, setAnalizando] = useState(false);
  const [errorAnalisis, setErrorAnalisis] = useState<string>();
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
    setAnalizando(true);
    setErrorAnalisis(undefined);
    // Limpiar el diagnostico anterior: si este falla, dejarlo en pantalla
    // haria parecer que corresponde a la foto nueva.
    setResult(undefined);

    try {
      const response = await analizarCultivo(base64, nombre);
      setResult(response);
      await refreshData();
    } catch (e) {
      setErrorAnalisis(
        e instanceof Error ? e.message : "No se pudo analizar la foto.",
      );
    } finally {
      setAnalizando(false);
    }
  }

  useEffect(() => {
    // Carga inicial al montar. La regla apunta a los setState sincronos que
    // encadenan renders; aqui refreshData es asincrona y solo actualiza el
    // estado cuando responde la API.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshData();
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

      <UploadForm
        onSubmit={handleUpload}
        analizando={analizando}
        errorAnalisis={errorAnalisis}
      />

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
