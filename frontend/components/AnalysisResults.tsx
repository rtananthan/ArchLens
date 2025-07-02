'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { 
  Download, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Info,
  Shield,
  TrendingUp,
  FileText,
  Loader2
} from 'lucide-react'
import { analysisApi } from '@/lib/api'
import { AnalysisDetailResponse, SecurityIssue, IssueSeverity } from '@/types/analysis'
import { formatDate, getScoreColor, getSeverityColor } from '@/lib/utils'
import { ArchitectureDescription } from './ArchitectureDescription'
import { PillarAvailabilityNotice } from './PillarAvailabilityNotice'

interface AnalysisResultsProps {
  analysisId: string
}

export function AnalysisResults({ analysisId }: AnalysisResultsProps) {
  const [results, setResults] = useState<AnalysisDetailResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchResults = async () => {
      try {
        setIsLoading(true)
        const response = await analysisApi.getAnalysisResults(analysisId)
        setResults(response)
      } catch (err) {
        console.error('Failed to fetch results:', err)
        setError('Failed to load analysis results')
      } finally {
        setIsLoading(false)
      }
    }

    fetchResults()
  }, [analysisId])

  const exportResults = () => {
    if (!results) return

    const exportData = {
      analysis_id: results.analysis_id,
      timestamp: results.timestamp,
      file_name: results.file_name,
      results: results.results
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })
    
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `archlens-analysis-${results.analysis_id}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const getSeverityIcon = (severity: IssueSeverity) => {
    switch (severity) {
      case 'HIGH':
        return <XCircle className="h-4 w-4" />
      case 'MEDIUM':
        return <AlertTriangle className="h-4 w-4" />
      case 'LOW':
        return <Info className="h-4 w-4" />
      default:
        return <Info className="h-4 w-4" />
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center p-8">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          <span>Loading analysis results...</span>
        </CardContent>
      </Card>
    )
  }

  if (error || !results) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Failed to Load Results</h3>
          <p className="text-muted-foreground mb-4">
            {error || 'Analysis results are not available'}
          </p>
          <Button onClick={() => window.location.reload()}>
            Try Again
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (results.status === 'failed') {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Analysis Failed</h3>
          <p className="text-muted-foreground mb-4">
            {results.error_message || 'An error occurred during analysis'}
          </p>
          <Button onClick={() => window.location.reload()}>
            Try Again
          </Button>
        </CardContent>
      </Card>
    )
  }

  if (!results.results) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Results Available</h3>
          <p className="text-muted-foreground">
            Analysis completed but no results were generated
          </p>
        </CardContent>
      </Card>
    )
  }

  const { results: analysisResults } = results
  const securityIssues = analysisResults.security.issues || []
  const highIssues = securityIssues.filter(issue => issue.severity === 'HIGH')
  const mediumIssues = securityIssues.filter(issue => issue.severity === 'MEDIUM')
  const lowIssues = securityIssues.filter(issue => issue.severity === 'LOW')

  return (
    <div className="space-y-6">
      {/* Architecture Description */}
      {results.description && (
        <ArchitectureDescription
          description={results.description}
          fileName={results.file_name}
        />
      )}

      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <CheckCircle className="h-5 w-5 text-green-600" />
                <span>Analysis Complete</span>
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                {results.file_name && `File: ${results.file_name} • `}
                Completed: {formatDate(results.timestamp)}
              </p>
            </div>
            <Button onClick={exportResults} variant="outline">
              <Download className="h-4 w-4 mr-2" />
              Export Results
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Overall Score */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5" />
            <span>Overall Score</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <div className="text-4xl font-bold">
              <span className={getScoreColor(analysisResults.overall_score)}>
                {analysisResults.overall_score.toFixed(1)}
              </span>
              <span className="text-lg text-muted-foreground">/10</span>
            </div>
            <div className="flex-1">
              <Progress value={analysisResults.overall_score * 10} className="h-2" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Security Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Shield className="h-5 w-5" />
            <span>Security Analysis</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Security Score */}
          <div className="flex items-center space-x-4">
            <div className="text-3xl font-bold">
              <span className={getScoreColor(analysisResults.security.score)}>
                {analysisResults.security.score.toFixed(1)}
              </span>
              <span className="text-lg text-muted-foreground">/10</span>
            </div>
            <div className="flex-1">
              <Progress value={analysisResults.security.score * 10} className="h-2" />
            </div>
          </div>

          {/* Issue Summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card className="p-4">
              <div className="flex items-center space-x-2">
                <XCircle className="h-4 w-4 text-red-600" />
                <span className="font-medium">High</span>
              </div>
              <div className="text-2xl font-bold text-red-600">
                {highIssues.length}
              </div>
            </Card>
            <Card className="p-4">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <span className="font-medium">Medium</span>
              </div>
              <div className="text-2xl font-bold text-yellow-600">
                {mediumIssues.length}
              </div>
            </Card>
            <Card className="p-4">
              <div className="flex items-center space-x-2">
                <Info className="h-4 w-4 text-blue-600" />
                <span className="font-medium">Low</span>
              </div>
              <div className="text-2xl font-bold text-blue-600">
                {lowIssues.length}
              </div>
            </Card>
          </div>

          {/* Security Issues */}
          {securityIssues.length > 0 && (
            <div className="space-y-4">
              <h4 className="font-semibold">Security Issues</h4>
              <div className="space-y-3">
                {securityIssues.map((issue, index) => (
                  <Card key={index} className="p-4">
                    <div className="flex items-start space-x-3">
                      <div className="flex items-center space-x-2 min-w-0">
                        {getSeverityIcon(issue.severity)}
                        <Badge className={getSeverityColor(issue.severity)}>
                          {issue.severity}
                        </Badge>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <h5 className="font-medium">{issue.component}</h5>
                          {issue.aws_service && (
                            <Badge variant="outline" className="text-xs">
                              {issue.aws_service}
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mb-2">
                          {issue.issue}
                        </p>
                        <p className="text-sm font-medium">
                          <span className="text-muted-foreground">Recommendation:</span>{' '}
                          {issue.recommendation}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* General Recommendations */}
          {analysisResults.security.recommendations.length > 0 && (
            <div className="space-y-4">
              <h4 className="font-semibold">General Recommendations</h4>
              <ul className="space-y-2">
                {analysisResults.security.recommendations.map((recommendation, index) => (
                  <li key={index} className="flex items-start space-x-2">
                    <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                    <span className="text-sm">{recommendation}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Future Pillars Notice */}
      <PillarAvailabilityNotice />
    </div>
  )
}