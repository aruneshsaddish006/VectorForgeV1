const nextConfig = {
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  outputFileTracingRoot: new URL(".", import.meta.url).pathname,
}

export default nextConfig
