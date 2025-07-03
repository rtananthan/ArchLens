// ArchLens Frontend - Main Application Page
// This is the primary user interface for the ArchLens application.
// It manages the complete user workflow from file upload to analysis results.

'use client'  // Next.js 14 directive for client-side rendering (required for React hooks)

// React hooks for state management
import { useState } from 'react'

// UI icons from Lucide React (lightweight icon library)
import { Shield, Github, ExternalLink } from 'lucide-react'

// Reusable UI components from shadcn/ui component library
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

// Custom ArchLens components for specific functionality
import { FileUpload } from '@/components/FileUpload'                    // Drag-and-drop file upload
import { AnalysisProgress } from '@/components/AnalysisProgress'        // Real-time progress tracking
import { AnalysisResults } from '@/components/AnalysisResults'          // Results visualization
import { ArchitectureDescription } from '@/components/ArchitectureDescription'  // Component summary
import { PillarAvailabilityNotice } from '@/components/PillarAvailabilityNotice'  // Feature notice
import { ThemeToggle } from '@/components/ThemeToggle'                  // Dark/light mode toggle

// API client for backend communication
import { analysisApi } from '@/lib/api'

// Application state machine - defines the different screens/phases of the app
// This creates a clear workflow that users follow from start to finish
type AppState = 'upload' | 'description' | 'analyzing' | 'results' | 'error'

export default function Home() {
  // State management for the application workflow
  const [appState, setAppState] = useState<AppState>('upload')           // Current app phase
  const [analysisId, setAnalysisId] = useState<string>('')               // Unique ID for tracking analysis
  const [error, setError] = useState<string>('')                         // Error messages for user feedback
  const [isUploading, setIsUploading] = useState(false)                  // Loading state during file upload
  const [architectureDescription, setArchitectureDescription] = useState<string>('')  // AI-generated summary
  const [fileName, setFileName] = useState<string>('')                   // Original filename for display

  /**
   * Handle file upload and initiate analysis workflow
   * 
   * This is the main entry point for user interaction. When a user selects
   * a file, this function:
   * 1. Updates UI to show loading state
   * 2. Sends file to backend for processing
   * 3. Handles the response and moves to next phase
   * 4. Manages error states and user feedback
   */
  const handleFileSelect = async (file: File) => {
    // Set loading state and clear any previous errors
    setIsUploading(true)
    setError('')
    setFileName(file.name)  // Store filename for display

    try {
      // Call backend API to upload and analyze file
      const response = await analysisApi.analyzeFile(file)
      setAnalysisId(response.analysis_id)  // Store ID for future API calls
      
      // Backend can provide immediate description of components found
      if (response.description) {
        setArchitectureDescription(response.description)
        setAppState('description')  // Show description phase first
      } else {
        // If no immediate description, go straight to analysis
        setAppState('analyzing')
      }
    } catch (err) {
      // Handle upload/analysis errors gracefully
      console.error('Upload failed:', err)
      setError('Failed to upload file. Please try again.')
      setAppState('error')
    } finally {
      // Always reset loading state when done
      setIsUploading(false)
    }
  }

  /**
   * Handle successful completion of analysis
   * Called by AnalysisProgress component when analysis finishes
   */
  const handleAnalysisComplete = (id: string) => {
    setAnalysisId(id)
    setAppState('results')  // Move to results display phase
  }

  /**
   * Handle analysis errors
   * Called by AnalysisProgress component when analysis fails
   */
  const handleAnalysisError = (errorMessage: string) => {
    setError(errorMessage)
    setAppState('error')  // Show error state with message
  }

  /**
   * Reset application to initial state
   * Allows users to start a new analysis from any phase
   */
  const resetApp = () => {
    setAppState('upload')               // Back to upload phase
    setAnalysisId('')                   // Clear analysis tracking
    setError('')                        // Clear error messages
    setIsUploading(false)               // Reset loading states
    setArchitectureDescription('')      // Clear previous description
    setFileName('')                     // Clear filename
  }

  /**
   * Transition from description phase to analysis phase
   * User can review the component summary before proceeding
   */
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
          {/* Hero Section - Main value proposition and feature highlights */}
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

          {/* Application State Rendering - shows different UI based on current phase */}
          {/* Phase 1: File Upload - Initial state where users select files */}
          {appState === 'upload' && (
            <div className="space-y-6">
              {/* Main file upload component with drag-and-drop functionality */}
              <FileUpload 
                onFileSelect={handleFileSelect}  // Callback when user selects file
                isUploading={isUploading}        // Loading state for UI feedback
              />
              
              {/* Notice about current feature availability */}
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

          {/* Phase 2: Architecture Description - Shows AI-identified components */}
          {appState === 'description' && (
            <div className="space-y-6">
              {/* Display component summary and allow user to proceed */}
              <ArchitectureDescription
                description={architectureDescription}  // AI-generated component summary
                fileName={fileName}                    // Original file name for context
                onContinue={continueToAnalysis}        // Callback to proceed to analysis
              />
              
              <div className="text-center">
                <Button variant="outline" onClick={resetApp}>
                  Start New Analysis
                </Button>
              </div>
            </div>
          )}

          {/* Phase 3: Analysis in Progress - Shows real-time progress */}
          {appState === 'analyzing' && (
            <div className="space-y-6">
              {/* Show architecture description if available */}
              {architectureDescription && (
                <ArchitectureDescription
                  description={architectureDescription}  // Component summary for context
                  fileName={fileName}                    // File name for reference
                />
              )}
              
              {/* Real-time progress tracking with polling */}
              <AnalysisProgress
                analysisId={analysisId}               // ID for tracking this analysis
                onComplete={handleAnalysisComplete}   // Callback when analysis finishes
                onError={handleAnalysisError}         // Callback for error handling
              />
              
              <div className="text-center">
                <Button variant="outline" onClick={resetApp}>
                  Start New Analysis
                </Button>
              </div>
            </div>
          )}

          {/* Phase 4: Results Display - Shows complete analysis results */}
          {appState === 'results' && (
            <div className="space-y-6">
              {/* Comprehensive results with security scores and recommendations */}
              <AnalysisResults analysisId={analysisId} />  {/* Fetches and displays full results */}
              
              <div className="text-center">
                <Button onClick={resetApp}>
                  Analyze Another File
                </Button>
              </div>
            </div>
          )}

          {/* Phase 5: Error State - Shows user-friendly error messages */}
          {appState === 'error' && (
            <Card>
              <CardContent className="p-8 text-center">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold text-destructive">
                    Something went wrong
                  </h3>
                  <p className="text-muted-foreground">
                    {/* Display specific error message or generic fallback */}
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