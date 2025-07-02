'use client'

import { useState } from 'react'
import { Shield, Github, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FileUpload } from '@/components/FileUpload'
import { AnalysisProgress } from '@/components/AnalysisProgress'
import { AnalysisResults } from '@/components/AnalysisResults'
import { ArchitectureDescription } from '@/components/ArchitectureDescription'
import { PillarAvailabilityNotice } from '@/components/PillarAvailabilityNotice'
import { ThemeToggle } from '@/components/ThemeToggle'
import { analysisApi } from '@/lib/api'

type AppState = 'upload' | 'description' | 'analyzing' | 'results' | 'error'

export default function Home() {
  const [appState, setAppState] = useState<AppState>('upload')
  const [analysisId, setAnalysisId] = useState<string>('')
  const [error, setError] = useState<string>('')
  const [isUploading, setIsUploading] = useState(false)
  const [architectureDescription, setArchitectureDescription] = useState<string>('')
  const [fileName, setFileName] = useState<string>('')

  const handleFileSelect = async (file: File) => {
    setIsUploading(true)
    setError('')
    setFileName(file.name)

    try {
      const response = await analysisApi.analyzeFile(file)
      setAnalysisId(response.analysis_id)
      
      // If we got an immediate description, show it first
      if (response.description) {
        setArchitectureDescription(response.description)
        setAppState('description')
      } else {
        // Otherwise go straight to analyzing
        setAppState('analyzing')
      }
    } catch (err) {
      console.error('Upload failed:', err)
      setError('Failed to upload file. Please try again.')
      setAppState('error')
    } finally {
      setIsUploading(false)
    }
  }

  const handleAnalysisComplete = (id: string) => {
    setAnalysisId(id)
    setAppState('results')
  }

  const handleAnalysisError = (errorMessage: string) => {
    setError(errorMessage)
    setAppState('error')
  }

  const resetApp = () => {
    setAppState('upload')
    setAnalysisId('')
    setError('')
    setIsUploading(false)
    setArchitectureDescription('')
    setFileName('')
  }

  const continueToAnalysis = () => {
    setAppState('analyzing')
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Shield className="h-8 w-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold">ArchLens</h1>
                <p className="text-sm text-muted-foreground">
                  AWS Architecture Analysis
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Button variant="ghost" size="sm" asChild>
                <a
                  href="https://github.com/your-repo/archlens"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Github className="h-4 w-4 mr-2" />
                  GitHub
                </a>
              </Button>
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Hero Section */}
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold mb-4">
              AI-Powered AWS Architecture Analysis
            </h2>
            <p className="text-xl text-muted-foreground mb-6">
              Upload your draw.io architecture diagrams and get instant security analysis 
              based on AWS Well-Architected Framework best practices.
            </p>
            <div className="flex items-center justify-center space-x-6 text-sm text-muted-foreground">
              <div className="flex items-center space-x-1">
                <Shield className="h-4 w-4" />
                <span>Security Analysis</span>
              </div>
              <div className="flex items-center space-x-1">
                <ExternalLink className="h-4 w-4" />
                <span>AI-Powered Insights</span>
              </div>
              <div className="flex items-center space-x-1">
                <Github className="h-4 w-4" />
                <span>No Authentication Required</span>
              </div>
            </div>
          </div>

          {/* App States */}
          {appState === 'upload' && (
            <div className="space-y-6">
              <FileUpload 
                onFileSelect={handleFileSelect}
                isUploading={isUploading}
              />
              
              {/* Pillar Availability Notice */}
              <PillarAvailabilityNotice />
              
              {/* Features */}
              <div className="grid md:grid-cols-3 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Security Analysis</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription>
                      Comprehensive security assessment based on AWS Well-Architected 
                      Framework Security Pillar principles.
                    </CardDescription>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">AI-Powered</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription>
                      Uses Amazon Bedrock for intelligent analysis and 
                      actionable recommendations.
                    </CardDescription>
                  </CardContent>
                </Card>
                
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Instant Results</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <CardDescription>
                      Get detailed analysis results within minutes, 
                      with exportable reports.
                    </CardDescription>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {appState === 'description' && (
            <div className="space-y-6">
              <ArchitectureDescription
                description={architectureDescription}
                fileName={fileName}
                onContinue={continueToAnalysis}
              />
              
              <div className="text-center">
                <Button variant="outline" onClick={resetApp}>
                  Start New Analysis
                </Button>
              </div>
            </div>
          )}

          {appState === 'analyzing' && (
            <div className="space-y-6">
              {architectureDescription && (
                <ArchitectureDescription
                  description={architectureDescription}
                  fileName={fileName}
                />
              )}
              
              <AnalysisProgress
                analysisId={analysisId}
                onComplete={handleAnalysisComplete}
                onError={handleAnalysisError}
              />
              
              <div className="text-center">
                <Button variant="outline" onClick={resetApp}>
                  Start New Analysis
                </Button>
              </div>
            </div>
          )}

          {appState === 'results' && (
            <div className="space-y-6">
              <AnalysisResults analysisId={analysisId} />
              
              <div className="text-center">
                <Button onClick={resetApp}>
                  Analyze Another File
                </Button>
              </div>
            </div>
          )}

          {appState === 'error' && (
            <Card>
              <CardContent className="p-8 text-center">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-destructive">
                    Something went wrong
                  </h3>
                  <p className="text-muted-foreground">
                    {error || 'An unexpected error occurred. Please try again.'}
                  </p>
                  <Button onClick={resetApp}>
                    Try Again
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="container mx-auto px-4 py-8">
          <div className="text-center text-sm text-muted-foreground">
            <p>
              Built with Next.js, AWS CDK, and Amazon Bedrock.{' '}
              <a 
                href="https://github.com/your-repo/archlens" 
                className="underline hover:text-foreground"
                target="_blank"
                rel="noopener noreferrer"
              >
                View source code on GitHub
              </a>
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}