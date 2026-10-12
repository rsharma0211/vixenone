import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  User,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile as updateFirebaseProfile,
  signInWithPopup,
  signOut as firebaseSignOut,
} from 'firebase/auth';
import { auth, googleProvider, initFirebaseAuth } from '@/lib/firebase';
import { apiClient, UserProfile } from '@/lib/api/client';
import { UserRole } from '@/lib/auth/roles';

interface AuthContextValue {
  user: User | null;
  profile: UserProfile | null;
  initials: string;
  loading: boolean;
  signInWithEmail: (email: string, pass: string) => Promise<void>;
  signUpWithEmail: (
    email: string,
    pass: string,
    displayName: string,
    role: UserRole
  ) => Promise<UserProfile>;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<UserProfile | null>;
  setProfile: React.Dispatch<React.SetStateAction<UserProfile | null>>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function getInitials(name?: string | null): string {
  if (!name || !name.trim()) return 'U';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0].substring(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchProfile = useCallback(async (firebaseUser: User): Promise<UserProfile> => {
    try {
      const userProfile = await apiClient.getMe();
      setProfile(userProfile);
      return userProfile;
    } catch {
      // Fallback to Firebase user info if backend fails momentarily
      const fallback: UserProfile = {
        uid: firebaseUser.uid,
        email: firebaseUser.email || '',
        display_name: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'User',
        role: 'facilities_manager',
      };
      setProfile(fallback);
      return fallback;
    }
  }, []);

  useEffect(() => {
    initFirebaseAuth();

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        await fetchProfile(firebaseUser);
      } else {
        setProfile(null);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, [fetchProfile]);

  const signInWithEmail = async (email: string, pass: string) => {
    await signInWithEmailAndPassword(auth, email, pass);
  };

  const signUpWithEmail = async (
    email: string,
    pass: string,
    displayName: string,
    role: UserRole
  ): Promise<UserProfile> => {
    let currentUser = auth.currentUser;
    if (!currentUser || currentUser.email !== email) {
      const cred = await createUserWithEmailAndPassword(auth, email, pass);
      currentUser = cred.user;
    }
    if (displayName && currentUser) {
      await updateFirebaseProfile(currentUser, { displayName });
    }
    const updated = await apiClient.updateMe({
      display_name: displayName,
      role: role,
    });
    setProfile(updated);
    return updated;
  };

  const signInWithGoogle = async () => {
    await signInWithPopup(auth, googleProvider);
  };

  const signOut = async () => {
    await firebaseSignOut(auth);
    setProfile(null);
  };

  const refreshProfile = useCallback(async (): Promise<UserProfile | null> => {
    if (auth.currentUser) {
      return await fetchProfile(auth.currentUser);
    }
    return null;
  }, [fetchProfile]);

  const initials = getInitials(profile?.display_name || user?.displayName);

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        initials,
        loading,
        signInWithEmail,
        signUpWithEmail,
        signInWithGoogle,
        signOut,
        refreshProfile,
        setProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

