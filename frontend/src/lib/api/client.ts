import { auth } from '@/lib/firebase';
import { UserRole } from '@/lib/auth/roles';
import type {
  EvaluationCriterionResponse,
  EvaluationCriterionUpdateItem,
  EvaluationsListResponse,
  EvaluationDetailResponse,
  EvaluationCreate,
  EvaluationUpdate,
  DocumentResponse,
  RequirementItem,
  ExtractRequirementsRequest,
  AnalysisJobResponse,
  EvaluationResultsResponse,
  Schemas,
} from '@/lib/types';

type VendorCreate = Schemas['VendorCreate'];
type VendorUpdate = Schemas['VendorUpdate'];
type VendorResponse = Schemas['VendorResponse'];

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export interface UserProfile {
  id?: string;
  uid?: string;
  email: string;
  display_name: string;
  role?: UserRole;
}

export interface UserProfileUpdatePayload {
  display_name?: string;
  role?: UserRole;
}

export class ApiHttpError extends Error {
  public status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiHttpError';
    this.status = status;
  }
}

export class ApiValidationError extends ApiHttpError {
  public fieldErrors: Record<string, string>;
  public generalErrors: string[];

  constructor(
    message: string,
    fieldErrors: Record<string, string> = {},
    generalErrors: string[] = []
  ) {
    super(message, 422);
    this.name = 'ApiValidationError';
    this.fieldErrors = fieldErrors;
    this.generalErrors = generalErrors;
  }
}

export function extractValidationErrors(data: unknown): {
  fieldErrors: Record<string, string>;
  generalErrors: string[];
} {
  const fieldErrors: Record<string, string> = {};
  const generalErrors: string[] = [];

  if (!data || typeof data !== 'object') {
    return { fieldErrors, generalErrors };
  }

  const payload = data as Record<string, unknown>;
  const detail = payload.detail !== undefined ? payload.detail : data;

  if (typeof detail === 'string') {
    generalErrors.push(detail);
    const lower = detail.toLowerCase();
    if (lower.includes('weight')) fieldErrors['weight'] = detail;
    if (lower.includes('name')) fieldErrors['name'] = detail;
    if (lower.includes('guidance')) fieldErrors['guidance'] = detail;
    if (lower.includes('vendor')) fieldErrors['vendor_names'] = detail;
    if (lower.includes('title')) fieldErrors['title'] = detail;
    if (lower.includes('category')) fieldErrors['category'] = detail;
    if (lower.includes('code')) fieldErrors['code'] = detail;
    if (lower.includes('text')) fieldErrors['text'] = detail;
  } else if (Array.isArray(detail)) {
    for (const item of detail) {
      if (typeof item === 'string') {
        generalErrors.push(item);
      } else if (item && typeof item === 'object') {
        const itemObj = item as Record<string, unknown>;
        const msg = String(itemObj.msg || itemObj.message || JSON.stringify(item));
        if (Array.isArray(itemObj.loc) && itemObj.loc.length > 0) {
          const locParts = itemObj.loc.filter((p) => p !== 'body');
          const fieldPath = locParts.join('.');
          if (fieldPath) {
            fieldErrors[fieldPath] = msg;
          }
          const lastPart = locParts[locParts.length - 1];
          if (lastPart && typeof lastPart === 'string') {
            if (!fieldErrors[lastPart]) {
              fieldErrors[lastPart] = msg;
            }
          }
        } else {
          generalErrors.push(msg);
        }
      }
    }
  }

  return { fieldErrors, generalErrors };
}

class ApiClient {
  private async getAuthHeader(): Promise<HeadersInit> {
    const user = auth.currentUser;
    if (user) {
      const token = await user.getIdToken();
      return {
        Authorization: `Bearer ${token}`,
      };
    }
    return {};
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 204) {
      return undefined as unknown as T;
    }

    if (!response.ok) {
      let errorBody: unknown = null;
      try {
        errorBody = await response.json();
      } catch {
        // Not JSON
      }

      if (response.status === 422) {
        const { fieldErrors, generalErrors } = extractValidationErrors(errorBody);
        const firstMsg =
          generalErrors[0] ||
          Object.values(fieldErrors)[0] ||
          'Validation failed (422)';
        throw new ApiValidationError(firstMsg, fieldErrors, generalErrors);
      }

      const errorObj = errorBody as { detail?: unknown } | null;
      const detailMsg = errorObj?.detail
        ? (typeof errorObj.detail === 'string'
            ? errorObj.detail
            : JSON.stringify(errorObj.detail))
        : `${response.status} ${response.statusText}`;
      throw new ApiHttpError(detailMsg, response.status);
    }

    return response.json();
  }

  // --- Profile ---
  async getMe(): Promise<UserProfile> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/me`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });
    return this.handleResponse<UserProfile>(response);
  }

  async updateMe(data: UserProfileUpdatePayload): Promise<UserProfile> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/me`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(data),
    });
    return this.handleResponse<UserProfile>(response);
  }

  // --- Criteria ---
  async getCriteria(): Promise<EvaluationCriterionResponse[]> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/criteria`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });
    return this.handleResponse<EvaluationCriterionResponse[]>(response);
  }

  async updateCriteria(
    payload: EvaluationCriterionUpdateItem[]
  ): Promise<EvaluationCriterionResponse[]> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/criteria`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(payload),
    });
    return this.handleResponse<EvaluationCriterionResponse[]>(response);
  }

  // --- Evaluations ---
  async listEvaluations(): Promise<EvaluationsListResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/evaluations`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });
    return this.handleResponse<EvaluationsListResponse>(response);
  }

  async createEvaluation(payload: EvaluationCreate): Promise<EvaluationDetailResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/evaluations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(payload),
    });
    return this.handleResponse<EvaluationDetailResponse>(response);
  }

  async getEvaluation(id: string): Promise<EvaluationDetailResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/evaluations/${id}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });
    return this.handleResponse<EvaluationDetailResponse>(response);
  }

  async updateEvaluation(
    id: string,
    payload: EvaluationUpdate
  ): Promise<EvaluationDetailResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/evaluations/${id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(payload),
    });
    return this.handleResponse<EvaluationDetailResponse>(response);
  }

  async deleteEvaluation(id: string): Promise<void> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/evaluations/${id}`, {
      method: 'DELETE',
      headers,
    });
    return this.handleResponse<void>(response);
  }

  // --- Vendors ---
  async addVendor(evaluationId: string, payload: VendorCreate): Promise<VendorResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/evaluations/${evaluationId}/vendors`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(payload),
    });
    return this.handleResponse<VendorResponse>(response);
  }

  async renameVendor(
    evaluationId: string,
    vendorId: string,
    payload: VendorUpdate
  ): Promise<VendorResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/vendors/${vendorId}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
        body: JSON.stringify(payload),
      }
    );
    return this.handleResponse<VendorResponse>(response);
  }

  async deleteVendor(evaluationId: string, vendorId: string): Promise<void> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/vendors/${vendorId}`,
      {
        method: 'DELETE',
        headers,
      }
    );
    return this.handleResponse<void>(response);
  }

  // --- Documents ---
  async uploadDocument(
    evaluationId: string,
    file: File,
    kind: 'requirements' | 'proposal' | string,
    vendorId?: string | null
  ): Promise<DocumentResponse> {
    const headers = await this.getAuthHeader();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('kind', kind);
    if (vendorId) {
      formData.append('vendor_id', vendorId);
    }

    const response = await fetch(`${BASE_URL}/api/evaluations/${evaluationId}/documents`, {
      method: 'POST',
      headers: {
        ...headers,
      },
      body: formData,
    });
    return this.handleResponse<DocumentResponse>(response);
  }

  async deleteDocument(evaluationId: string, docId: string): Promise<void> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/documents/${docId}`,
      {
        method: 'DELETE',
        headers,
      }
    );
    return this.handleResponse<void>(response);
  }

  // --- Requirements ---
  async getRequirements(evaluationId: string): Promise<RequirementItem[]> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/requirements`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
      }
    );
    return this.handleResponse<RequirementItem[]>(response);
  }

  async replaceRequirements(
    evaluationId: string,
    payload: RequirementItem[]
  ): Promise<RequirementItem[]> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/requirements`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
        body: JSON.stringify(payload),
      }
    );
    return this.handleResponse<RequirementItem[]>(response);
  }

  async extractRequirements(
    evaluationId: string,
    payload?: ExtractRequirementsRequest
  ): Promise<AnalysisJobResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/extract`,
      payload !== undefined
        ? {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...headers,
            },
            body: JSON.stringify(payload),
          }
        : {
            method: 'POST',
            headers: {
              ...headers,
            },
          }
    );
    return this.handleResponse<AnalysisJobResponse>(response);
  }

  // --- Latest Job ---
  async getLatestJob(evaluationId: string): Promise<AnalysisJobResponse | null> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/jobs/latest`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
      }
    );
    return this.handleResponse<AnalysisJobResponse | null>(response);
  }

  // --- Results ---
  async getResults(evaluationId: string): Promise<EvaluationResultsResponse> {
    const headers = await this.getAuthHeader();
    const response = await fetch(
      `${BASE_URL}/api/evaluations/${evaluationId}/results`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...headers,
        },
      }
    );
    return this.handleResponse<EvaluationResultsResponse>(response);
  }
}

export const apiClient = new ApiClient();
