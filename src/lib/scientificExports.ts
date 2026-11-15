
export type ScientificExportMetadata = {
  title?: string;
  domain?: string;
  parameter?: string;
  unit?: string;
  source?: string;
  generatedAt?: string;
  methodology?: string;
  description?: string;
  [key: string]: unknown;
};

export type ScientificExportRow = Record<
  string,
  string | number | boolean | null | undefined
>;

// ---------------------------------------------------------
// FILENAME HANDLING
// ---------------------------------------------------------

function safeFilename(
  filename: string,
  fallbackExtension?: string
): string {
  const trimmed = filename.trim();
  const lastDot = trimmed.lastIndexOf(".");

  const hasExtension = lastDot > 0;

  const base = hasExtension
    ? trimmed.slice(0, lastDot)
    : trimmed;

  const extension = hasExtension
    ? trimmed.slice(lastDot + 1).toLowerCase()
    : fallbackExtension;

  const cleanedBase =
    base
      .toLowerCase()
      .replace(/[^a-z0-9-_]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "") || "geonova-export";

  const cleanedExtension = extension
    ?.replace(/[^a-z0-9]/g, "");

  return cleanedExtension
    ? `${cleanedBase}.${cleanedExtension}`
    : cleanedBase;
}

// ---------------------------------------------------------
// DOWNLOAD HANDLER
// ---------------------------------------------------------

function downloadBlob(
  blob: Blob,
  filename: string
): void {
  if (typeof window === "undefined") {
    throw new Error("File exports are only available in the browser.");
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  link.style.display = "none";

  document.body.appendChild(link);
  link.click();
  link.remove();

  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 1000);
}

// ---------------------------------------------------------
// CSV ESCAPING
// ---------------------------------------------------------

function escapeCsv(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }

  const text = String(value);

  if (
    text.includes(",") ||
    text.includes('"') ||
    text.includes("\n") ||
    text.includes("\r")
  ) {
    return `"${text.replace(/"/g, '""')}"`;
  }

  return text;
}

// ---------------------------------------------------------
// CSV EXPORT
// ---------------------------------------------------------

export function exportScientificCSV(
  data: ScientificExportRow[],
  metadata: ScientificExportMetadata = {},
  filename = "geonova-observations.csv"
): void {
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error("No observation records are available to export.");
  }

  const headers = Array.from(
    new Set(data.flatMap((row) => Object.keys(row)))
  );

  if (headers.length === 0) {
    throw new Error("The observation dataset contains no columns.");
  }

  const metadataRows = [
    ["# GeoNOVA Scientific Data Export"],
    ["# Generated At", metadata.generatedAt || new Date().toISOString()],
    ["# Title", metadata.title || ""],
    ["# Domain", metadata.domain || ""],
    ["# Parameter", metadata.parameter || ""],
    ["# Unit", metadata.unit || ""],
    ["# Source", metadata.source || ""],
    ["# Methodology", metadata.methodology || ""],
    ["# Description", metadata.description || ""],
    [],
  ];

  const csvRows = [
    ...metadataRows.map((row) =>
      row.map(escapeCsv).join(",")
    ),
    headers.map(escapeCsv).join(","),
    ...data.map((row) =>
      headers
        .map((header) => escapeCsv(row[header]))
        .join(",")
    ),
  ];

  const csv = "\uFEFF" + csvRows.join("\r\n");

  const blob = new Blob([csv], {
    type: "text/csv;charset=utf-8;",
  });

  downloadBlob(
    blob,
    safeFilename(filename, "csv")
  );
}

// ---------------------------------------------------------
// JSON EXPORT
// ---------------------------------------------------------

export function exportScientificJSON(
  data: unknown,
  metadata: ScientificExportMetadata = {},
  filename = "geonova-research-data.json"
): void {
  if (data === null || data === undefined) {
    throw new Error("No scientific data is available to export.");
  }

  const payload = {
    export_metadata: {
      application: "GeoNOVA",
      export_format: "JSON",
      generated_at:
        metadata.generatedAt || new Date().toISOString(),
      ...metadata,
    },
    data,
  };

  const json = JSON.stringify(payload, null, 2);

  const blob = new Blob([json], {
    type: "application/json;charset=utf-8;",
  });

  downloadBlob(
    blob,
    safeFilename(filename, "json")
  );
}

// ---------------------------------------------------------
// PNG CHART EXPORT
// ---------------------------------------------------------

export async function exportScientificChartPNG(
  container: HTMLElement | null,
  filename = "geonova-scientific-chart.png"
): Promise<void> {
  if (typeof window === "undefined") {
    throw new Error("Chart exports are only available in the browser.");
  }

  if (!container) {
    throw new Error("Chart container was not found.");
  }

  const svg = container.querySelector("svg");

  if (!svg) {
    throw new Error("No rendered chart SVG was found.");
  }

  const clonedSvg = svg.cloneNode(true) as SVGSVGElement;

  const bounds = svg.getBoundingClientRect();

  const width = Math.max(
    Math.ceil(bounds.width),
    Number(svg.getAttribute("width")) || 800
  );

  const height = Math.max(
    Math.ceil(bounds.height),
    Number(svg.getAttribute("height")) || 450
  );

  clonedSvg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clonedSvg.setAttribute("width", String(width));
  clonedSvg.setAttribute("height", String(height));
  clonedSvg.setAttribute(
    "viewBox",
    `0 0 ${width} ${height}`
  );

  // Preserve computed styles from the rendered chart.
  const originalElements = [
    svg,
    ...Array.from(svg.querySelectorAll("*")),
  ];

  const clonedElements = [
    clonedSvg,
    ...Array.from(clonedSvg.querySelectorAll("*")),
  ];

  originalElements.forEach((original, index) => {
    const cloned = clonedElements[index];

    if (!cloned) return;

    const computed = window.getComputedStyle(original);

    const properties = [
      "fill",
      "stroke",
      "stroke-width",
      "stroke-dasharray",
      "font-family",
      "font-size",
      "font-weight",
      "text-anchor",
      "opacity",
    ];

    properties.forEach((property) => {
      const value = computed.getPropertyValue(property);

      if (value) {
        cloned.setAttribute(
          property,
          value
        );
      }
    });
  });

  // White export background for document compatibility.
  const background = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "rect"
  );

  background.setAttribute("x", "0");
  background.setAttribute("y", "0");
  background.setAttribute("width", String(width));
  background.setAttribute("height", String(height));
  background.setAttribute("fill", "#ffffff");

  clonedSvg.insertBefore(
    background,
    clonedSvg.firstChild
  );

  const serialized = new XMLSerializer().serializeToString(
    clonedSvg
  );

  const svgBlob = new Blob(
    [serialized],
    {
      type: "image/svg+xml;charset=utf-8",
    }
  );

  const svgUrl = URL.createObjectURL(svgBlob);

  try {
    const image = new Image();

    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();

      image.onerror = () => {
        reject(
          new Error("Unable to render chart SVG for PNG export.")
        );
      };

      image.src = svgUrl;
    });

    const canvas = document.createElement("canvas");

    const scale = Math.min(
      Math.max(window.devicePixelRatio || 1, 2),
      3
    );

    canvas.width = width * scale;
    canvas.height = height * scale;

    const context = canvas.getContext("2d");

    if (!context) {
      throw new Error("Unable to create PNG rendering context.");
    }

    context.fillStyle = "#ffffff";

    context.fillRect(
      0,
      0,
      canvas.width,
      canvas.height
    );

    context.scale(scale, scale);

    context.drawImage(
      image,
      0,
      0,
      width,
      height
    );

    const pngBlob = await new Promise<Blob>(
      (resolve, reject) => {
        canvas.toBlob((blob) => {
          if (blob) {
            resolve(blob);
          } else {
            reject(
              new Error("PNG image generation failed.")
            );
          }
        }, "image/png");
      }
    );

    downloadBlob(
      pngBlob,
      safeFilename(filename, "png")
    );
  } finally {
    URL.revokeObjectURL(svgUrl);
  }
}
