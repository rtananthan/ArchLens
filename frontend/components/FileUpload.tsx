'use client'

import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, File, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { formatBytes } from '@/lib/utils'

interface FileUploadProps {
  onFileSelect: (file: File) => void
  isUploading?: boolean
  acceptedFileTypes?: string[]
}

export function FileUpload({ 
  onFileSelect, 
  isUploading = false,
  acceptedFileTypes = ['.xml', '.drawio']
}: FileUploadProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0]
      setSelectedFile(file)
      onFileSelect(file)
    }
  }, [onFileSelect])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/xml': ['.xml'],
      'application/vnd.jgraph.mxfile': ['.drawio'],
      'text/xml': ['.xml']
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024, // 10MB
    disabled: isUploading
  })

  const removeFile = () => {
    setSelectedFile(null)
  }

  return (
    <Card className="w-full">
      <CardContent className="p-6">
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
            ${isDragActive && !isDragReject ? 'border-primary bg-primary/5' : ''}
            ${isDragReject ? 'border-destructive bg-destructive/5' : ''}
            ${!isDragActive ? 'border-muted-foreground/25 hover:border-primary/50' : ''}
            ${isUploading ? 'cursor-not-allowed opacity-50' : ''}
          `}
        >
          <input {...getInputProps()} />
          
          {selectedFile ? (
            <div className="space-y-4">
              <div className="flex items-center justify-center space-x-2">
                <File className="h-8 w-8 text-primary" />
                <div className="text-left">
                  <p className="font-medium">{selectedFile.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatBytes(selectedFile.size)}
                  </p>
                </div>
                {!isUploading && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile()
                    }}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              {isUploading && (
                <p className="text-sm text-muted-foreground">
                  Uploading and analyzing...
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <Upload className="h-12 w-12 mx-auto text-muted-foreground" />
              <div className="space-y-2">
                <p className="text-lg font-medium">
                  {isDragActive ? 'Drop your file here' : 'Upload your draw.io file'}
                </p>
                <p className="text-sm text-muted-foreground">
                  Drag and drop or click to select a .xml or .drawio file
                </p>
                <p className="text-xs text-muted-foreground">
                  Maximum file size: 10MB
                </p>
              </div>
              <Button variant="outline" disabled={isUploading}>
                Select File
              </Button>
            </div>
          )}
          
          {isDragReject && (
            <p className="text-sm text-destructive mt-2">
              Please upload a valid .xml or .drawio file
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}