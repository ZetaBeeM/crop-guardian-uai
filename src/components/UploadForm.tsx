import { useState } from "react";

interface Props {
  onSubmit: (nombre: string, base64: string) => void;
  analizando?: boolean;
  errorAnalisis?: string;
}

export default function UploadForm({
  onSubmit,
  analizando = false,
  errorAnalisis,
}: Props) {
  const [preview, setPreview] = useState<string>();
  const [nombre, setNombre] = useState("");
  const [error, setError] = useState<string>();

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(undefined);

    const file = e.target.files?.[0];

    if (!file) return;

    if (!nombre.trim()) {
      setError("Asigna un nombre a la planta antes de subir la foto (ej. Tomate1).");
      e.target.value = "";
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      const result = reader.result as string;

      setPreview(result);

      const base64 = result.split(",")[1];

      onSubmit(nombre.trim(), base64);
    };

    reader.readAsDataURL(file);
  };

  return (
    <div>
      <div className="plant-tag-field">
        <label htmlFor="plant-name">Nombre de la planta</label>
        <input
          id="plant-name"
          type="text"
          placeholder="ej. Tomate1"
          value={nombre}
          disabled={analizando}
          onChange={(e) => {
            setNombre(e.target.value);
            setError(undefined);
          }}
        />
      </div>

      <input
        type="file"
        accept="image/*"
        disabled={analizando}
        onChange={handleChange}
      />

      <div aria-live="polite">
        {analizando && (
          <p className="upload-status">
            <svg
              className="sprout"
              viewBox="0 0 32 32"
              aria-hidden="true"
              focusable="false"
            >
              <path className="sprout-stem" d="M16 29 C16 24 15.5 19 16 11" />
              <path
                className="sprout-leaf sprout-leaf-izq"
                d="M16 21 C11.5 21.5 8 19 6.5 14.5 C11.5 13.5 15 16.5 16 21 Z"
              />
              <path
                className="sprout-leaf sprout-leaf-der"
                d="M16 15.5 C20.5 16 24 13.5 25.5 9 C20.5 8 17 11 16 15.5 Z"
              />
            </svg>
            Analizando la foto… puede tardar hasta un minuto.
          </p>
        )}

        {(error ?? errorAnalisis) && (
          <p className="plant-tag-error">{error ?? errorAnalisis}</p>
        )}
      </div>

      {preview && (
        <img
          src={preview}
          style={{
            maxWidth: "300px",
            marginTop: "1rem",
          }}
        />
      )}
    </div>
  );
}
