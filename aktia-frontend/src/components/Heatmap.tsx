import { useEffect, useRef } from "react";

/**
 * Mapa de calor do Grad-CAM sobre a radiografia. `grid` vem pronto do backend
 * (valores de 0 a 1); aqui ele só é pintado: cada célula vira um pixel e o
 * navegador suaviza ao esticar até o tamanho da imagem.
 */
export default function Heatmap({ grid }: { grid: number[][] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context || grid.length === 0) return;

    const rows = grid.length;
    const columns = grid[0].length;
    canvas.width = columns;
    canvas.height = rows;

    const image = context.createImageData(columns, rows);
    grid.forEach((row, y) =>
      row.forEach((value, x) => {
        const offset = (y * columns + x) * 4;
        // Do amarelo (influência baixa) ao vermelho (alta); abaixo de 0,2 fica transparente.
        image.data[offset] = 255;
        image.data[offset + 1] = Math.round(220 * (1 - value));
        image.data[offset + 2] = 0;
        image.data[offset + 3] = value < 0.2 ? 0 : Math.round(170 * value);
      })
    );
    context.putImageData(image, 0, 0);
  }, [grid]);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none absolute inset-0 h-full w-full rounded-md"
      style={{ imageRendering: "auto" }}
    />
  );
}
