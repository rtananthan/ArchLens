export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type IssueSeverity = 'HIGH' | 'MEDIUM' | 'LOW'

export interface SecurityIssue {
  severity: IssueSeverity
  component: string
  issue: string
  recommendation: string
  aws_service?: string
}

export interface SecurityAnalysis {
  score: number
  issues: SecurityIssue[]
  recommendations: string[]
}

export interface AnalysisResults {
  overall_score: number
  security: SecurityAnalysis
  performance?: any
  cost?: any
  reliability?: any
  operational_excellence?: any
}

export interface AnalysisRecord {
  analysis_id: string
  status: AnalysisStatus
  timestamp: string
  file_name?: string
  file_size?: number
  description?: string  // Immediate architecture description
  results?: AnalysisResults
  error_message?: string
}

export interface AnalysisResponse {
  analysis_id: string
  status: AnalysisStatus
  message: string
  description?: string  // Immediate architecture description
}

export interface AnalysisStatusResponse {
  analysis_id: string
  status: AnalysisStatus
  timestamp: string
  progress?: number
  estimated_completion?: string
}

export interface AnalysisDetailResponse {
  analysis_id: string
  status: AnalysisStatus
  timestamp: string
  file_name?: string
  description?: string  // Immediate architecture description
  results?: AnalysisResults
  error_message?: string
}