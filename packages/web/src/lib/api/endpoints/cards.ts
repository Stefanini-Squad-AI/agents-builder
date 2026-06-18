import { 
  CardView, 
  PhaseView,
  DraftCardRequest,
  ProposeBacklogRequest,
  ProposeBacklogResponse,
  CardsStatsResponse,
  CardDepView,
  CardInputView,
  CardInputKind,
  Priority,
  CardStatus,
  ApiResponse,
  UpdateSectionRequest,
  RegenerateSectionResponse,
  DraftCardResponse,
  UpdateDependenciesRequest,
  CreateCardInputRequest,
  UpdateCardInputRequest,
  DagResponse,
} from '../types';
import { get, post, put, patch, del } from '../client';

/**
 * Cards and Phases API endpoints
 */
export const cardsApi = {
  // List project cards
  async getCards(projectSlug: string): Promise<CardView[]> {
    return get<CardView[]>(`/api/projects/${projectSlug}/cards`);
  },

  // Get specific card
  async getCard(projectSlug: string, cardId: string): Promise<CardView> {
    return get<CardView>(`/api/projects/${projectSlug}/cards/${cardId}`);
  },

  // Draft new card using AI
  async draftCard(projectSlug: string, data: DraftCardRequest): Promise<{
    card: CardView;
    llm_run_id: string;
    cost_usd?: number;
  }> {
    return post(`/api/projects/${projectSlug}/cards/draft`, data);
  },

  // Update card content
  async updateCard(projectSlug: string, cardId: string, data: {
    title?: string;
    context_md?: string;
    task_md?: string;
    outputs_md?: string;
    acceptance_criteria_md?: string;
    human_gate?: boolean;
    human_gate_checklist_md?: string;
    story_points?: number;
    priority?: Priority;
    status?: CardStatus;
  }): Promise<CardView> {
    return put<CardView>(`/api/projects/${projectSlug}/cards/${cardId}`, data);
  },

  // Update card content by section
  async updateCardSection(projectSlug: string, cardId: string, section: string, content: string): Promise<CardView> {
    return patch<CardView>(`/api/projects/${projectSlug}/cards/${cardId}/sections/${section}`, { content });
  },

  // Regenerate a single section using LLM
  async regenerateCardSection(projectSlug: string, cardId: string, section: string): Promise<RegenerateSectionResponse> {
    return post<RegenerateSectionResponse>(`/api/projects/${projectSlug}/cards/${cardId}/sections/${section}/regenerate`);
  },

  // Draft entire card using LLM
  async draftCardContent(projectSlug: string, cardId: string): Promise<DraftCardResponse> {
    return post<DraftCardResponse>(`/api/projects/${projectSlug}/cards/${cardId}/draft`);
  },

  // Update card dependencies
  async updateCardDependencies(projectSlug: string, cardId: string, data: UpdateDependenciesRequest): Promise<CardView> {
    return put<CardView>(`/api/projects/${projectSlug}/cards/${cardId}/dependencies`, data);
  },

  // List card inputs
  async listCardInputs(projectSlug: string, cardId: string): Promise<CardInputView[]> {
    return get<CardInputView[]>(`/api/projects/${projectSlug}/cards/${cardId}/inputs`);
  },

  // Create card input
  async createCardInput(projectSlug: string, cardId: string, data: CreateCardInputRequest): Promise<CardInputView> {
    return post<CardInputView>(`/api/projects/${projectSlug}/cards/${cardId}/inputs`, data);
  },

  // Update card input
  async updateCardInput(projectSlug: string, cardId: string, inputId: string, data: UpdateCardInputRequest): Promise<CardInputView> {
    return patch<CardInputView>(`/api/projects/${projectSlug}/cards/${cardId}/inputs/${inputId}`, data);
  },

  // Delete card input
  async deleteCardInput(projectSlug: string, cardId: string, inputId: string): Promise<void> {
    return del(`/api/projects/${projectSlug}/cards/${cardId}/inputs/${inputId}`);
  },

  // Render card as markdown
  async renderCardMarkdown(projectSlug: string, cardId: string): Promise<{
    markdown: string;
    filename: string;
  }> {
    return get(`/api/projects/${projectSlug}/cards/${cardId}/render`);
  },

  // Get cards statistics
  async getCardsStats(projectSlug: string): Promise<CardsStatsResponse> {
    return get(`/api/projects/${projectSlug}/cards/stats`);
  },
};

/**
 * Phases API endpoints
 */
const phasesApiObj = {
  // List project phases
  async getPhases(projectSlug: string): Promise<PhaseView[]> {
    return get<PhaseView[]>(`/api/projects/${projectSlug}/phases`);
  },

  // Get specific phase
  async getPhase(projectSlug: string, phaseId: string): Promise<PhaseView> {
    return get<PhaseView>(`/api/projects/${projectSlug}/phases/${phaseId}`);
  },

  // Update phase
  async updatePhase(projectSlug: string, phaseId: string, data: {
    name?: string;
    description_md?: string;
  }): Promise<PhaseView> {
    return put<PhaseView>(`/api/projects/${projectSlug}/phases/${phaseId}`, data);
  },
};

/**
 * Backlog management API
 */
const backlogApiObj = {
  // Propose entire backlog using AI
  async proposeBacklog(projectSlug: string): Promise<ProposeBacklogResponse> {
    return post(`/api/projects/${projectSlug}/backlog/propose`);
  },

  // Get project DAG (card dependencies)
  async getProjectDag(projectSlug: string): Promise<DagResponse> {
    return get<DagResponse>(`/api/projects/${projectSlug}/dag`);
  },

  // Update card dependencies
  async updateCardDependencies(projectSlug: string, cardId: string, data: {
    depends_on_codes?: string[];
    parallel_with_codes?: string[];
  }): Promise<CardView> {
    return put<CardView>(`/api/projects/${projectSlug}/cards/${cardId}/dependencies`, data);
  },

  // Validate backlog structure
  async validateBacklog(projectSlug: string): Promise<{
    valid: boolean;
    issues: Array<{
      severity: string;
      message: string;
      card_code?: string;
    }>;
  }> {
    return get(`/api/projects/${projectSlug}/backlog/validate`);
  },
};

export { cardsApi as default };
export { phasesApiObj as phasesApi };
export { backlogApiObj as backlogApi };