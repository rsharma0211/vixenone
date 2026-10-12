export type UserRole = 'facilities_manager' | 'procurement' | 'approver';

export const ROLE_LABELS: Record<UserRole, string> = {
  facilities_manager: 'Facilities manager',
  procurement: 'Procurement',
  approver: 'Approver',
};

export const USER_ROLES: UserRole[] = [
  'facilities_manager',
  'procurement',
  'approver',
];
