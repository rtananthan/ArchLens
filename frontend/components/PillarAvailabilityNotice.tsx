'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Shield, TrendingUp, DollarSign, Zap, Leaf, Clock } from 'lucide-react'

export function PillarAvailabilityNotice() {
  const pillars = [
    {
      name: 'Security',
      icon: Shield,
      status: 'available',
      description: 'Identity & access, data protection, infrastructure security'
    },
    {
      name: 'Performance',
      icon: TrendingUp,
      status: 'coming-soon',
      description: 'Scalability, efficiency, and optimization analysis'
    },
    {
      name: 'Cost',
      icon: DollarSign,
      status: 'coming-soon',
      description: 'Cost optimization and resource efficiency'
    },
    {
      name: 'Reliability',
      icon: Zap,
      status: 'coming-soon',
      description: 'Fault tolerance and disaster recovery'
    },
    {
      name: 'Operational Excellence',
      icon: Clock,
      status: 'coming-soon',
      description: 'Operations, monitoring, and continuous improvement'
    },
    {
      name: 'Sustainability',
      icon: Leaf,
      status: 'coming-soon',
      description: 'Environmental impact and resource efficiency'
    }
  ]

  return (
    <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 border-blue-200 dark:border-blue-800">
      <CardContent className="p-4">
        <div className="space-y-3">
          <div className="flex items-center space-x-2">
            <Shield className="h-5 w-5 text-blue-600" />
            <h3 className="font-semibold text-blue-900 dark:text-blue-100">
              AWS Well-Architected Framework Analysis
            </h3>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {pillars.map((pillar) => {
              const IconComponent = pillar.icon
              return (
                <div
                  key={pillar.name}
                  className="flex flex-col items-center p-2 rounded-lg bg-white/50 dark:bg-gray-900/50 border border-gray-200/50 dark:border-gray-700/50"
                >
                  <div className={`flex items-center space-x-1 mb-1 ${
                    pillar.status === 'available' 
                      ? 'text-green-600 dark:text-green-400' 
                      : 'text-gray-400 dark:text-gray-500'
                  }`}>
                    <IconComponent className="h-4 w-4" />
                    <Badge 
                      variant={pillar.status === 'available' ? 'default' : 'secondary'}
                      className={`text-xs ${
                        pillar.status === 'available'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                      }`}
                    >
                      {pillar.status === 'available' ? 'Available' : 'Soon'}
                    </Badge>
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                      {pillar.name}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-tight">
                      {pillar.description}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
          
          <div className="text-xs text-blue-700 dark:text-blue-300 bg-blue-100/50 dark:bg-blue-900/20 rounded p-2">
            <strong>Currently Available:</strong> Security Pillar analysis with AI-powered insights. 
            Additional pillars will be added in future updates to provide comprehensive architecture assessment.
          </div>
        </div>
      </CardContent>
    </Card>
  )
}