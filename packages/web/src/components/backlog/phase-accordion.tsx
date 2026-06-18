'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PhaseView, CardView, CardType, CardStatus } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Zap,
  Bug,
  Wrench,
  CircleDot,
  CheckCircle2,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface PhaseAccordionProps {
  phase: PhaseView;
  projectSlug: string;
  defaultExpanded?: boolean;
}

// Card type icons and colors
const CARD_TYPE_CONFIG: Record<string, { icon: typeof FileText; color: string; label: string }> = {
  [CardType.TASK]: { icon: FileText, color: 'text-blue-500', label: 'Task' },
  [CardType.STORY]: { icon: FileText, color: 'text-green-500', label: 'Story' },
  [CardType.SPIKE]: { icon: Zap, color: 'text-purple-500', label: 'Spike' },
  [CardType.BUG]: { icon: Bug, color: 'text-red-500', label: 'Bug' },
  [CardType.DEMO]: { icon: Wrench, color: 'text-orange-500', label: 'Demo' },
};

// Card status icons
const CARD_STATUS_CONFIG: Record<string, { icon: typeof CircleDot; color: string }> = {
  [CardStatus.DRAFT]: { icon: CircleDot, color: 'text-gray-400' },
  [CardStatus.READY]: { icon: Clock, color: 'text-blue-500' },
  [CardStatus.IN_PROGRESS]: { icon: AlertCircle, color: 'text-yellow-500' },
  [CardStatus.DONE]: { icon: CheckCircle2, color: 'text-green-500' },
};

export function PhaseAccordion({
  phase,
  projectSlug,
  defaultExpanded = true,
}: PhaseAccordionProps) {
  const router = useRouter();
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const totalStoryPoints = phase.cards.reduce(
    (sum, card) => sum + (card.story_points || 0),
    0
  );

  const handleCardClick = (card: CardView) => {
    router.push(`/projects/${projectSlug}/cards/${card.id}` as any);
  };

  return (
    <Card>
      <CardHeader
        className="cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-5 w-5 text-muted-foreground" />
            )}
            <div>
              <h3 className="text-lg font-semibold">{phase.name}</h3>
              <p className="text-sm text-muted-foreground">{phase.code}</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{phase.cards.length} cards</span>
            <span>{totalStoryPoints} SP</span>
          </div>
        </div>
        {phase.description_md && (
          <p className="text-sm text-muted-foreground mt-2 ml-8">
            {phase.description_md}
          </p>
        )}
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0">
          {phase.cards.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No cards in this phase
            </p>
          ) : (
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="text-left text-xs font-medium text-muted-foreground px-4 py-2">
                      Code
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground px-4 py-2">
                      Title
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground px-4 py-2">
                      Type
                    </th>
                    <th className="text-center text-xs font-medium text-muted-foreground px-4 py-2">
                      SP
                    </th>
                    <th className="text-center text-xs font-medium text-muted-foreground px-4 py-2">
                      Status
                    </th>
                    <th className="text-left text-xs font-medium text-muted-foreground px-4 py-2">
                      Skills
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {phase.cards.map((card, index) => {
                    const typeConfig = CARD_TYPE_CONFIG[card.type] || CARD_TYPE_CONFIG[CardType.TASK];
                    const statusConfig = CARD_STATUS_CONFIG[card.status] || CARD_STATUS_CONFIG[CardStatus.DRAFT];
                    const TypeIcon = typeConfig.icon;
                    const StatusIcon = statusConfig.icon;

                    return (
                      <tr
                        key={card.id}
                        className={cn(
                          'cursor-pointer hover:bg-muted/50 transition-colors',
                          index !== phase.cards.length - 1 && 'border-b'
                        )}
                        onClick={() => handleCardClick(card)}
                      >
                        <td className="px-4 py-3">
                          <code className="text-sm font-mono bg-muted px-1.5 py-0.5 rounded">
                            {card.code}
                          </code>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium">{card.title}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <TypeIcon className={cn('h-4 w-4', typeConfig.color)} />
                            <span className="text-sm">{typeConfig.label}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <Badge variant="outline">{card.story_points || '-'}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-1.5">
                            <StatusIcon className={cn('h-4 w-4', statusConfig.color)} />
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-1">
                            {card.skill_slugs.slice(0, 3).map((slug) => (
                              <Badge key={slug} variant="secondary" className="text-xs">
                                {slug}
                              </Badge>
                            ))}
                            {card.skill_slugs.length > 3 && (
                              <Badge variant="secondary" className="text-xs">
                                +{card.skill_slugs.length - 3}
                              </Badge>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

export default PhaseAccordion;
