import { auth } from '@/lib/firebase';
import { UserRole } from '@/lib/auth/roles';

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

  async getMe(): Promise<UserProfile> {
    const headers = await this.getAuthHeader();
    const response = await fetch(`${BASE_URL}/api/me`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch /api/me: ${response.status} ${response.statusText}`);
    }

    return response.json();
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

    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          detail = typeof errorJson.detail === 'string'
            ? errorJson.detail
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // fallback to default detail
      }
      throw new Error(`Failed to update profile: ${detail}`);
    }

    return response.json();
  }
}

export const apiClient = new ApiClient();

