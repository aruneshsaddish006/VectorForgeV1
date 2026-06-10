const nextConfig = {
  // Emit a self-contained server bundle (server.js + minimal node_modules)
  // so the Docker runtime image stays small. See Dockerfile runner stage.
  output: "standalone",
  typescript: { ignoreBuildErrors: true },
  outputFileTracingRoot: new URL(".", import.meta.url).pathname,
  allowedDevOrigins: ["*"],
}

export default nextConfig
