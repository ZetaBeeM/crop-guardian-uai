import { useState } from "react";

interface Props {
  onSubmit: (nombre: string, base64: string) => void;
}

export default function UploadForm({ onSubmit }: Props) {
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
          onChange={(e) => {
            setNombre(e.target.value);
            setError(undefined);
          }}
        />
      </div>

      <input type="file" accept="image/*" onChange={handleChange} />

      {error && <p className="plant-tag-error">{error}</p>}

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
