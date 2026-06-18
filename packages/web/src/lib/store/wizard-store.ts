import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * Wizard step definitions for the project creation wizard.
 * According to SPEC §11: Step 2.4.1 - Q&A is Step 2 of 4.
 */
export type WizardStep = 'identity' | 'qa' | 'tech' | 'artifacts';

export const WIZARD_STEPS: { key: WizardStep; label: string; description: string }[] = [
  { key: 'identity', label: 'Project Identity', description: 'Name and basic information' },
  { key: 'qa', label: 'Discovery Q&A', description: 'Answer questions about your project' },
  { key: 'tech', label: 'Tech Stack', description: 'Select technologies and frameworks' },
  { key: 'artifacts', label: 'Artifacts', description: 'Upload documents and resources' },
];

export interface WizardStepStatus {
  completed: boolean;
  canProceed: boolean;
  validationErrors: string[];
}

export interface WizardState {
  // Current project being created/edited
  projectSlug: string | null;
  projectId: string | null;

  // Current step
  currentStep: WizardStep;
  currentStepIndex: number;

  // Step completion status
  stepStatuses: Record<WizardStep, WizardStepStatus>;

  // Draft data for identity step
  identityDraft: {
    name: string;
    objective: string;
    contextMd: string;
  };

  // Actions
  setProject: (slug: string, id: string) => void;
  clearProject: () => void;
  
  goToStep: (step: WizardStep) => void;
  nextStep: () => void;
  prevStep: () => void;
  
  setStepStatus: (step: WizardStep, status: Partial<WizardStepStatus>) => void;
  markStepCompleted: (step: WizardStep) => void;
  
  setIdentityDraft: (data: Partial<WizardState['identityDraft']>) => void;
  
  canGoToStep: (step: WizardStep) => boolean;
  getProgress: () => { completed: number; total: number; percentage: number };
  
  reset: () => void;
}

const initialStepStatuses: Record<WizardStep, WizardStepStatus> = {
  identity: { completed: false, canProceed: false, validationErrors: [] },
  qa: { completed: false, canProceed: false, validationErrors: [] },
  tech: { completed: false, canProceed: true, validationErrors: [] }, // Tech is optional
  artifacts: { completed: false, canProceed: true, validationErrors: [] }, // Artifacts optional
};

const initialState = {
  projectSlug: null,
  projectId: null,
  currentStep: 'identity' as WizardStep,
  currentStepIndex: 0,
  stepStatuses: { ...initialStepStatuses },
  identityDraft: {
    name: '',
    objective: '',
    contextMd: '',
  },
};

export const useWizardStore = create<WizardState>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        setProject: (slug, id) => {
          set({ projectSlug: slug, projectId: id }, false, 'setProject');
        },

        clearProject: () => {
          set({ 
            projectSlug: null, 
            projectId: null,
            currentStep: 'identity',
            currentStepIndex: 0,
          }, false, 'clearProject');
        },

        goToStep: (step) => {
          const { canGoToStep } = get();
          if (!canGoToStep(step)) return;

          const stepIndex = WIZARD_STEPS.findIndex(s => s.key === step);
          set({ currentStep: step, currentStepIndex: stepIndex }, false, 'goToStep');
        },

        nextStep: () => {
          const { currentStepIndex, stepStatuses, currentStep } = get();
          
          // Check if current step allows proceeding
          if (!stepStatuses[currentStep].canProceed) return;
          
          if (currentStepIndex < WIZARD_STEPS.length - 1) {
            const nextStepKey = WIZARD_STEPS[currentStepIndex + 1].key;
            set({ 
              currentStep: nextStepKey, 
              currentStepIndex: currentStepIndex + 1 
            }, false, 'nextStep');
          }
        },

        prevStep: () => {
          const { currentStepIndex } = get();
          if (currentStepIndex > 0) {
            const prevStepKey = WIZARD_STEPS[currentStepIndex - 1].key;
            set({ 
              currentStep: prevStepKey, 
              currentStepIndex: currentStepIndex - 1 
            }, false, 'prevStep');
          }
        },

        setStepStatus: (step, status) => {
          const { stepStatuses } = get();
          set({
            stepStatuses: {
              ...stepStatuses,
              [step]: { ...stepStatuses[step], ...status },
            },
          }, false, 'setStepStatus');
        },

        markStepCompleted: (step) => {
          const { stepStatuses } = get();
          set({
            stepStatuses: {
              ...stepStatuses,
              [step]: { ...stepStatuses[step], completed: true, canProceed: true },
            },
          }, false, 'markStepCompleted');
        },

        setIdentityDraft: (data) => {
          const { identityDraft } = get();
          set({
            identityDraft: { ...identityDraft, ...data },
          }, false, 'setIdentityDraft');
        },

        canGoToStep: (step) => {
          const { stepStatuses } = get();
          const targetIndex = WIZARD_STEPS.findIndex(s => s.key === step);
          
          // Can always go back
          // To go forward, all previous steps must allow proceeding
          for (let i = 0; i < targetIndex; i++) {
            const stepKey = WIZARD_STEPS[i].key;
            if (!stepStatuses[stepKey].canProceed) {
              return false;
            }
          }
          return true;
        },

        getProgress: () => {
          const { stepStatuses } = get();
          const completed = Object.values(stepStatuses).filter(s => s.completed).length;
          const total = WIZARD_STEPS.length;
          return {
            completed,
            total,
            percentage: Math.round((completed / total) * 100),
          };
        },

        reset: () => {
          set({ ...initialState, stepStatuses: { ...initialStepStatuses } }, false, 'reset');
        },
      }),
      {
        name: 'wizard-store',
        // Only persist the draft data and current step, not computed state
        partialize: (state) => ({
          projectSlug: state.projectSlug,
          projectId: state.projectId,
          currentStep: state.currentStep,
          currentStepIndex: state.currentStepIndex,
          identityDraft: state.identityDraft,
        }),
      }
    ),
    {
      name: 'wizard-store',
    }
  )
);

export default useWizardStore;
