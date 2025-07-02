'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, Copy, CheckCircle } from 'lucide-react'
import { useState } from 'react'

interface ArchitectureDescriptionProps {
  description: string
  fileName?: string
  onContinue?: () => void
}

export function ArchitectureDescription({ 
  description, 
  fileName, 
  onContinue 
}: ArchitectureDescriptionProps) {
  const [copied, setCopied] = useState(false)

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(description)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

  // Parse markdown-style formatting for better display
  const formatDescription = (text: string) => {
    // Split by double newlines to get paragraphs
    const paragraphs = text.split('\n\n')
    
    return paragraphs.map((paragraph, index) => {
      // Check if it's a header (starts with **)
      if (paragraph.startsWith('**') && paragraph.includes('**')) {
        const headerMatch = paragraph.match(/\*\*(.*?)\*\*(.*)/)
        if (headerMatch) {
          const [, header, content] = headerMatch
          return (
            <div key={index} className="mb-4">
              <h4 className="font-semibold text-primary mb-2">{header}</h4>
              {content.trim() && <p className="text-sm text-muted-foreground">{content.trim()}</p>}
            </div>
          )
        }
      }
      
      // Regular paragraph with inline bold formatting
      const formattedText = paragraph.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      
      return (
        <p 
          key={index} 
          className="text-sm mb-3 last:mb-0"
          dangerouslySetInnerHTML={{ __html: formattedText }}
        />
      )
    })
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center space-x-2">
            <FileText className="h-5 w-5" />
            <span>Architecture Description</span>
          </CardTitle>
          <div className="flex items-center space-x-2">
            {fileName && (
              <Badge variant="outline" className="text-xs">
                {fileName}
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={copyToClipboard}
              className="h-8"
            >
              {copied ? (
                <>
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 mr-1" />
                  Copy
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="bg-muted/50 rounded-lg p-4 border">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            {formatDescription(description)}
          </div>
        </div>
        
        {onContinue && (
          <div className="flex justify-center pt-2">
            <Button onClick={onContinue} className="w-full sm:w-auto">
              Continue to Security Analysis
            </Button>
          </div>
        )}
        
        <div className="text-xs text-muted-foreground text-center">
          This description was generated immediately by parsing your diagram. 
          Detailed security analysis is still in progress.
        </div>
      </CardContent>
    </Card>
  )
}