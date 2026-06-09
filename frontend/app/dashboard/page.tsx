"use client"

import { useState } from "react"
import { Sidebar } from "@/components/shell/sidebar"
import { TopBar } from "@/components/shell/top-bar"
import { Inspector } from "@/components/shell/inspector"
import { ChatThread } from "@/components/chat/chat-thread"
import type { Project, Workspace } from "@/lib/api"

export default function DashboardPage() {
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-canvas text-foreground">
      <Sidebar
        selectedWorkspace={selectedWorkspace}
        selectedProject={selectedProject}
        onWorkspaceChange={(workspace) => {
          setSelectedWorkspace(workspace)
          setSelectedProject(null)
        }}
        onProjectChange={setSelectedProject}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar inspectorOpen={inspectorOpen} onToggleInspector={() => setInspectorOpen((v) => !v)} />

        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 bg-canvas">
            <ChatThread selectedWorkspace={selectedWorkspace} selectedProject={selectedProject} />
          </main>

          <Inspector open={inspectorOpen} />
        </div>
      </div>
    </div>
  )
}
