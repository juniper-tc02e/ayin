import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Ayin",
    short_name: "Ayin",
    description: "Privacy self-exposure scanner. Self-scan only.",
    start_url: "/",
    display: "standalone",
    theme_color: "#0b0e14",
    background_color: "#0b0e14",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
    ],
  };
}
