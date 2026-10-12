import { auth } from '@/lib/firebase';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export interface UserProfile {
  uid: string;
  email: string;
  display_name: string;
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
}

export const apiClient = new ApiClient();
