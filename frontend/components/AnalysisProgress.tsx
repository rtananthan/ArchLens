'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Loader2, CheckCircle, XCircle, Clock } from 'lucide-react'
import { analysisApi } from '@/lib/api'
import { AnalysisStatus, AnalysisStatusResponse } from '@/types/analysis'
import { formatDate } from '@/lib/utils'

interface AnalysisProgressProps {
  analysisId: string
  onComplete: (analysisId: string) => void
  onError: (error: string) => void
}

export function AnalysisProgress({ analysisId, onComplete, onError }: AnalysisProgressProps) {
  const [status, setStatus] = useState<AnalysisStatusResponse | null>(null)
  const [isPolling, setIsPolling] = useState(true)

  useEffect(() => {
    let interval: NodeJS.Timeout

    const pollStatus = async () => {
      try {
        const response = await analysisApi.getAnalysisStatus(analysisId)
        setStatus(response)

        if (response.status === 'completed') {
          setIsPolling(false)
          onComplete(analysisId)
        } else if (response.status === 'failed') {
          setIsPolling(false)
          onError('Analysis failed. Please try again.')
        }
      } catch (error) {
        console.error('Failed to fetch status:', error)
        onError('Failed to check analysis status')
        setIsPolling(false)
      }
    }

    if (isPolling) {
      // Initial check
      pollStatus()
      
      // Poll every 2 seconds
      interval = setInterval(pollStatus, 2000)
    }

    return () => {
      if (interval) {
        clearInterval(interval)
      }
    }
  }, [analysisId, isPolling, onComplete, onError])

  const getStatusIcon = (status: AnalysisStatus) => {
    switch (status) {
      case 'pending':
        return <Clock className="h-4 w-4" />
      case 'processing':
        return <Loader2 className="h-4 w-4 animate-spin" />
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-600" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-600" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  const getStatusColor = (status: AnalysisStatus) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'processing':
        return 'bg-blue-100 text-blue-800'
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getProgressValue = () => {
    if (!status) return 0
    
    switch (status.status) {
      case 'pending':
        return 10
      case 'processing':
        return status.progress ? status.progress * 100 : 50
      case 'completed':
        return 100
      case 'failed':
        return 0
      default:
        return 0
    }
  }

  const getStatusMessage = () => {
    if (!status) return 'Initializing...'
    
    switch (status.status) {
      case 'pending':
        return 'Analysis queued for processing'
      case 'processing':
        return 'Analyzing your architecture with AI...'
      case 'completed':
        return 'Analysis completed successfully!'
      case 'failed':
        return 'Analysis failed. Please try again.'
      default:
        return 'Unknown status'
    }
  }

  if (!status) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center p-6">
          <Loader2 className="h-4 w-4 animate-spin mr-2" />
          <span>Loading...</span>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Analysis Progress</span>
          <Badge className={getStatusColor(status.status)}>
            <span className="flex items-center space-x-1">
              {getStatusIcon(status.status)}
              <span className="capitalize">{status.status}</span>
            </span>
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Progress</span>
            <span>{Math.round(getProgressValue())}%</span>
          </div>
          <Progress value={getProgressValue()} />
        </div>
        
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>{getStatusMessage()}</p>
          <p>
            <span className="font-medium">Analysis ID:</span> {analysisId}
          </p>
          <p>
            <span className="font-medium">Started:</span> {formatDate(status.timestamp)}
          </p>
          {status.estimated_completion && (
            <p>
              <span className="font-medium">Estimated completion:</span>{' '}
              {formatDate(status.estimated_completion)}
            </p>
          )}
        </div>

        {status.status === 'failed' && (
          <div className="pt-4">
            <Button 
              variant="outline" 
              onClick={() => window.location.reload()}
              className="w-full"
            >
              Try Again
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}