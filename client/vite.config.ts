import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  server: {
    proxy: {
      "/session": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: "index.html",
        review: "review.html",
      },
    },
  },
});
