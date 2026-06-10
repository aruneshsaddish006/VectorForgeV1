"use client"

import { useState } from "react"
import { Sidebar } from "@/components/shell/sidebar"
import { TopBar } from "@/components/shell/top-bar"
import { Inspector } from "@/components/shell/inspector"
import { ChatThread } from "@/components/chat/chat-thread"
import { DatasetDetails } from "@/components/chat/dataset-details"
import { ModelDetails } from "@/components/chat/model-details"
import { ProjectDetails } from "@/components/chat/project-details"
import { UseCaseDetails } from "@/components/chat/use-case-details"
import { WorkspaceDetails } from "@/components/chat/workspace-details"
import type { Project, Workspace } from "@/lib/api"

export default function DashboardPage() {
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [activeView, setActiveView] = useState("chat")

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-canvas p-3 text-foreground sm:p-4">
      <TopBar
        selectedWorkspace={selectedWorkspace}
        selectedProject={selectedProject}
        inspectorOpen={inspectorOpen}
        onToggleInspector={() => setInspectorOpen((v) => !v)}
      />

      <div className="mt-3 flex min-h-0 flex-1 gap-3 sm:mt-4 sm:gap-4">
        <Sidebar
          selectedWorkspace={selectedWorkspace}
          selectedProject={selectedProject}
          activeView={activeView}
          onWorkspaceChange={(workspace) => {
            setSelectedWorkspace(workspace)
            setSelectedProject(null)
          }}
          onProjectChange={setSelectedProject}
          onViewChange={setActiveView}
        />

        <main className="app-panel min-w-0 flex-1 overflow-hidden rounded-[28px]">
          {activeView === "workspaces" ? (
            <WorkspaceDetails
              selectedWorkspace={selectedWorkspace}
              onWorkspaceChange={(workspace) => {
                setSelectedWorkspace(workspace)
                setSelectedProject(null)
              }}
              onProjectChange={setSelectedProject}
            />
          ) : activeView === "projects" ? (
            <ProjectDetails
              selectedWorkspace={selectedWorkspace}
              selectedProject={selectedProject}
              onProjectChange={setSelectedProject}
            />
          ) : activeView === "datasets" ? (
            <DatasetDetails selectedWorkspace={selectedWorkspace} />
          ) : activeView === "models" ? (
            <ModelDetails selectedWorkspace={selectedWorkspace} />
          ) : activeView === "use-cases" ? (
            <UseCaseDetails selectedWorkspace={selectedWorkspace} />
          ) : (
            <ChatThread selectedWorkspace={selectedWorkspace} selectedProject={selectedProject} />
          )}
        </main>

        <Inspector open={inspectorOpen} />
      </div>
    </div>
  )
}
