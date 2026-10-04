"use client"

import { createContext, useContext } from "react"
import type { DataSource } from "./types"

// Which source feeds the workspace being rendered. Components use it to label numbers honestly:
// MOCK badges for the scripted replay, calc_id chips for values that came out of a sparklab tool.
const DataSourceContext = createContext<DataSource>("mock")

export function DataSourceProvider({ source, children }: { source: DataSource; children: React.ReactNode }) {
  return <DataSourceContext.Provider value={source}>{children}</DataSourceContext.Provider>
}

export function useDataSource(): DataSource {
  return useContext(DataSourceContext)
}
