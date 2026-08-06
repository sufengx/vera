import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发模式代理 /api 到本机 ClickHouse（生产走 nginx，见 nginx.conf）
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 8501,
    proxy: {
      "/api": {
        target: "http://localhost:8123",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
        headers: { Authorization: "Basic ZGVmYXVsdDp2ZXJh" },
      },
    },
  },
});
